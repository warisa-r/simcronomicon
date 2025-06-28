import pytest
import os
import shutil
import pyproj
import numpy as np
import tempfile

import osmnx as ox

from simcronomicon import Town, TownParameters
from test.test_helper import (
    POINT_DOM, POINT_UNIKLINIK, COORDS_THERESIENKIRCHE, COORDS_HAUSARZT, COORDS_SUPERC,
    get_nearest_node, get_shortest_path_length, DEFAULT_TOWN_PARAMS
)


class TestTownParameters:

    @pytest.mark.parametrize(
        "num_pop, num_init_spreader, spreader_nodes, expected_nodes",
        [
            (1000, 10, [], []),
            (1000, 3, [5, 12, 47], [5, 12, 47]),
            (1000, 5, [10, 25], [10, 25]),  # Partial specification
            (100, 4, [7, 7, 15, 15], [7, 7, 15, 15]),  # Duplicates
            (100, 2, ["1", "2"], ["1", "2"]),  # String convertible
            (100, 3, [1, "2", 3.0], [1, "2", 3.0]),  # Mixed types
            (100, 2, [-1, -5], [-1, -5]),  # Negative node IDs
        ]
    )
    def test_valid_parameters(self, num_pop, num_init_spreader, spreader_nodes, expected_nodes):
        params = TownParameters(
            num_pop=num_pop,
            num_init_spreader=num_init_spreader,
            spreader_initial_nodes=spreader_nodes
        )
        assert params.num_pop == num_pop
        assert params.num_init_spreader == num_init_spreader
        assert params.spreader_initial_nodes == expected_nodes

    @pytest.mark.parametrize(
        "kwargs, error, match",
        [
            # Type Errors
            ({"num_pop": "1000", "num_init_spreader": 10},
             TypeError, "num_pop must be an integer"),
            ({"num_pop": 1000, "num_init_spreader": 10.5},
             TypeError, "num_init_spreader must be an integer"),
            ({"num_pop": 1000, "num_init_spreader": 2, "spreader_initial_nodes": (
                1, 2)}, TypeError, "spreader_initial_nodes must be a list"),

            # Value Errors for num_pop
            ({"num_pop": 0, "num_init_spreader": 1},
             ValueError, "num_pop must be positive, got 0"),
            ({"num_pop": -5, "num_init_spreader": 1},
             ValueError, "num_pop must be positive, got -5"),

            # Value Errors for num_init_spreader - FIXED: Match actual error messages
            ({"num_pop": 100, "num_init_spreader": 0}, ValueError,
             "num_init_spreader must be positive, got 0"),
            ({"num_pop": 100, "num_init_spreader": -1}, ValueError,
             "num_init_spreader must be positive, got -1"),
            ({"num_pop": 100, "num_init_spreader": 150}, ValueError,
             "num_init_spreader \\(150\\) cannot exceed num_pop \\(100\\)"),

            # Too many spreader locations - 4 locations for 2 spreaders should fail
            ({"num_pop": 100, "num_init_spreader": 2, "spreader_initial_nodes": [
             1, 2, 3, 4]}, ValueError, "There cannot be more locations"),
        ]
    )
    def test_invalid_parameters(self, kwargs, error, match):
        with pytest.raises(error, match=match):
            TownParameters(**kwargs)


class TestTown:
    def setup_method(self):
        ox.settings.use_cache = False
        self._cleanup_all_files()

    def teardown_method(self):
        self._cleanup_all_files()

    def _cleanup_all_files(self):
        # OSMnx cache cleanup
        cache_dirs = [
            os.path.expanduser("~/.osmnx"),
            "cache"
        ]
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)

        # Default town files cleanup
        default_files = [
            "town_graph.graphmlz",
            "town_graph_config.json"
        ]
        for filename in default_files:
            if os.path.exists(filename):
                os.remove(filename)
                print(f"Cleaned up: {filename}")

    def test_town_invalid_inputs(self):
        # Case 1: classify_place_func is not a function
        with pytest.raises(TypeError, match="`classify_place_func` must be a function."):
            Town.from_point(
                POINT_DOM, 500, DEFAULT_TOWN_PARAMS,
                classify_place_func="not_a_function",
                all_place_types=["accommodation", "workplace"]
            )

        # Case 2: custom classify_place_func but all_place_types is None
        def dummy_classify(row):
            return "workplace"

        with pytest.raises(ValueError, match="If you pass a custom `classify_place_func`, you must also provide `all_place_types`."):
            Town.from_point(
                POINT_DOM, 500, DEFAULT_TOWN_PARAMS,
                classify_place_func=dummy_classify,
                all_place_types=None
            )

        # Case 3: custom classify_place_func but "accommodation" missing in all_place_types
        with pytest.raises(ValueError, match="Your `all_place_types` must include 'accommodation' type buildings."):
            Town.from_point(
                POINT_DOM, 500, DEFAULT_TOWN_PARAMS,
                classify_place_func=dummy_classify,
                all_place_types=["workplace", "education"]
            )

        # Edge Case 1: point is not a tuple/list
        with pytest.raises(ValueError, match="`point` must be a list or tuple in the format \\[latitude, longitude\\]."):
            Town.from_point(
                "not_a_tuple", 500, DEFAULT_TOWN_PARAMS
            )

        # Edge Case 2: point is not valid lat/lon
        with pytest.raises(ValueError, match="`point` values must represent valid latitude and longitude coordinates."):
            Town.from_point(
                (200, 500), 500, DEFAULT_TOWN_PARAMS
            )

        # Edge Case 3: "No relevant nodes remain after filtering. The resulting town graph would be empty."
        with pytest.raises(ValueError, match="No relevant nodes remain after filtering. The resulting town graph would be empty."):
            # Use point a bit further off from Dom and decrease the radius to trigger this error
            Town.from_point((50.7853, 6.0839), 100, DEFAULT_TOWN_PARAMS)

    def test_graphmlz_file_saved_and_overwrite_prompt_and_abort(self):
        import builtins
        with tempfile.TemporaryDirectory() as tmpdir:
            file_prefix = "overwrite_test"
            graphmlz_path = os.path.join(tmpdir, f"{file_prefix}.graphmlz")

            # First save: file should be created
            town = Town.from_point(
                POINT_DOM, 500, DEFAULT_TOWN_PARAMS, file_prefix=file_prefix, save_dir=tmpdir)
            assert os.path.exists(
                graphmlz_path), "GraphMLZ file was not saved in the specified directory"

            # Second save: should prompt for overwrite and handle both 'y' and 'n'
            prompts = []
            printed = []

            # Case 1: User types 'y' (overwrite)
            def fake_input_yes(prompt):
                prompts.append(prompt)
                return "y"

            original_input = builtins.input
            builtins.input = fake_input_yes
            try:
                town2 = Town.from_point(
                    POINT_DOM, 500, DEFAULT_TOWN_PARAMS, file_prefix=file_prefix, save_dir=tmpdir)
            finally:
                builtins.input = original_input

            assert any(
                "already exists. Overwrite?" in p for p in prompts), "Overwrite prompt was not shown for 'y'"
            assert isinstance(
                town2, Town), "Town object was not returned after overwrite"

            # Case 2: User types 'n' (abort)
            prompts.clear()
            printed.clear()

            def fake_input_no(prompt):
                prompts.append(prompt)
                return "n"

            def fake_print(msg):
                printed.append(msg)

            builtins.input = fake_input_no
            original_print = builtins.print
            builtins.print = fake_print
            try:
                town3 = Town.from_point(
                    POINT_DOM, 500, DEFAULT_TOWN_PARAMS, file_prefix=file_prefix, save_dir=tmpdir)
            finally:
                builtins.input = original_input
                builtins.print = original_print

            assert any(
                "already exists. Overwrite?" in p for p in prompts), "Overwrite prompt was not shown for 'n'"
            assert any("aborted" in str(p).lower()
                       for p in printed), "Abort message was not printed"
            assert isinstance(
                town3, Town), "Town object was not returned after abort"

    def test_spreader_initial_nodes_assertion_error(self):
        test_graphmlz = "test/test_data/aachen_dom_500m.graphmlz"
        test_metadata = "test/test_data/aachen_dom_500m_config.json"

        # Set spreader_initial_nodes to include non-existent nodes (350, 750)
        town_params_spreader = TownParameters(100, 4, [1, 350, 750])

        expected_error_msg = "Some spreader_initial_nodes do not exist in the town graph: \\[350, 750\\]"

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match=expected_error_msg):
                Town.from_point(
                    POINT_DOM, 500, town_params_spreader, save_dir=tmpdir)

        # from_files test remains the same (doesn't create new files)
        with pytest.raises(ValueError, match=expected_error_msg):
            Town.from_files(
                config_path=test_metadata,
                town_graph_path=test_graphmlz,
                town_params=town_params_spreader
            )

    def test_healthcare_presence_and_all_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            town_dom = Town.from_point(
                POINT_DOM, 500, DEFAULT_TOWN_PARAMS, file_prefix="dom", save_dir=tmpdir)
            town_uniklinik = Town.from_point(
                POINT_UNIKLINIK, 500, DEFAULT_TOWN_PARAMS, file_prefix="uniklinik", save_dir=tmpdir)

            assert 'healthcare_facility' not in town_dom.found_place_types, \
                "Expected the area within 0.5km from Aachener Dom to have no healthcare_facility."
            assert 'healthcare_facility' in town_uniklinik.found_place_types, \
                "Expected the area within 0.5km from Uniklinik to have healthcare_facility"

            assert town_dom.all_place_types == town_uniklinik.all_place_types, \
                "Expected both towns to have the same all_place_types list"

    def test_superc_is_classified_as_education(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            town = Town.from_point(
                POINT_DOM, 750, DEFAULT_TOWN_PARAMS, file_prefix="dom_750m", save_dir=tmpdir)

            # Project lat/lon to same CRS as town graph
            wgs84 = pyproj.CRS("EPSG:4326")
            target_crs = pyproj.CRS(town.epsg_code)
            transformer = pyproj.Transformer.from_crs(
                wgs84, target_crs, always_xy=True)
            x_proj, y_proj = transformer.transform(
                COORDS_SUPERC[1], COORDS_SUPERC[0])

            # Find closest node by Euclidean distance in CRS
            min_dist = float("inf")
            closest_node_id = None

            for node_id, data in town.town_graph.nodes(data=True):
                dx = data['x'] - x_proj
                dy = data['y'] - y_proj
                dist = dx * dx + dy * dy  # squared distance for speed
                if dist < min_dist:
                    min_dist = dist
                    closest_node_id = node_id

            assert closest_node_id is not None, "No closest node found."
            place_type = town.town_graph.nodes[closest_node_id].get(
                "place_type")
            assert place_type == "education", f"Expected 'education', got '{place_type}'"

            # Confirm that the actual coordinate of super C centroid is not far
            actual_x = town.town_graph.nodes[closest_node_id]["x"]
            actual_y = town.town_graph.nodes[closest_node_id]["y"]
            euclidean_distance = np.sqrt(
                (actual_x - x_proj)**2 + (actual_y - y_proj)**2)
            assert euclidean_distance < 50, f"Too far from SuperC (~{euclidean_distance:.2f} m)"

    def test_distance_to_landmarks_dom(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # We have to construct with from_point since we always want to make sure that
            # our algorithm of shortest path construction works with the most recent
            # open street map information
            town_2000 = Town.from_point(
                POINT_DOM, 2000, DEFAULT_TOWN_PARAMS, file_prefix="dom_2000m", save_dir=tmpdir)
            town_750 = Town.from_point(
                POINT_DOM, 750, DEFAULT_TOWN_PARAMS, file_prefix="dom_750m", save_dir=tmpdir)

            node_theresienkirche_2000 = get_nearest_node(
                town_2000, COORDS_THERESIENKIRCHE)
            node_hausarzt_2000 = get_nearest_node(town_2000, COORDS_HAUSARZT)
            node_superC_2000 = get_nearest_node(town_2000, COORDS_SUPERC)
            node_theresienkirche_750 = get_nearest_node(
                town_750, COORDS_THERESIENKIRCHE)
            node_hausarzt_750 = get_nearest_node(town_750, COORDS_HAUSARZT)
            node_superC_750 = get_nearest_node(town_750, COORDS_SUPERC)

            # Expected distances (meters)
            expected_theresienkirche = 335
            expected_hausarzt = 1245
            tolerance = 50

            # Calculate distances
            dist_theresienkirche_2000 = get_shortest_path_length(
                town_2000, node_superC_2000, node_theresienkirche_2000)
            dist_theresienkirche_750 = get_shortest_path_length(
                town_750, node_superC_750, node_theresienkirche_750)
            dist_hausarzt_2000 = get_shortest_path_length(
                town_2000, node_superC_2000, node_hausarzt_2000)
            dist_hausarzt_750 = get_shortest_path_length(
                town_750, node_superC_750, node_hausarzt_750)

            # Assert that 2000m town gives shorter or equal distances than 750m town
            assert dist_theresienkirche_2000 <= dist_theresienkirche_750, "Distance to Theresienkirche should be shorter in 2000m town"
            assert dist_hausarzt_2000 <= dist_hausarzt_750, "Distance to Hausarzt should be shorter in 2000m town"

            # Assert that distances do not deviate from expected values by more than 50m
            assert abs(dist_theresienkirche_2000 - expected_theresienkirche) < tolerance, \
                f"Distance to Theresienkirche deviates by more than {tolerance}m (got {dist_theresienkirche_2000:.2f}m)"
            assert abs(dist_hausarzt_2000 - expected_hausarzt) < tolerance, \
                f"Distance to Hausarzt deviates by more than {tolerance}m (got {dist_hausarzt_2000:.2f}m)"

    def test_save_to_files(self):
        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a town using from_point
            original_town = Town.from_point(
                POINT_DOM, 500, DEFAULT_TOWN_PARAMS, file_prefix="original", save_dir=tmpdir)

            # Modify some node attributes (first accommodation node)
            first_node = original_town.accommodation_node_ids[0]
            original_town.town_graph.nodes[first_node]["custom_node_attr"] = 123
            original_town.town_graph.nodes[first_node]["modified"] = True

            # Swap place types of two nodes if we have different types
            place_types = list(original_town.found_place_types)
            if len(place_types) >= 2 and "accommodation" in place_types:
                other_type = next(
                    pt for pt in place_types if pt != "accommodation")

                # Find one node of each type
                acc_node = original_town.accommodation_node_ids[0]
                other_nodes = [n for n, d in original_town.town_graph.nodes(data=True)
                               if d.get("place_type") == other_type]

                if other_nodes:
                    other_node = other_nodes[0]
                    # Swap place types
                    original_place_types = {
                        acc_node: original_town.town_graph.nodes[acc_node]["place_type"],
                        other_node: original_town.town_graph.nodes[other_node]["place_type"]
                    }
                    original_town.town_graph.nodes[acc_node]["place_type"] = other_type
                    original_town.town_graph.nodes[other_node]["place_type"] = "accommodation"

                    # Update accommodation_node_ids
                    original_town.accommodation_node_ids.remove(acc_node)
                    original_town.accommodation_node_ids.append(other_node)

            # Set a specific file prefix for save_to_files
            custom_prefix = os.path.join(tmpdir, "custom_town")

            # Save the town using save_to_files
            graphml_path, config_path = original_town.save_to_files(
                custom_prefix)

            # Test loading the saved files
            loaded_town = Town.from_files(
                config_path=config_path,
                town_graph_path=graphml_path,
                town_params=DEFAULT_TOWN_PARAMS
            )

            # Verify basic structure
            assert len(loaded_town.town_graph.nodes) == len(
                original_town.town_graph.nodes)
            assert len(loaded_town.town_graph.edges) == len(
                original_town.town_graph.edges)

            # Check node attribute modifications were preserved
            assert "custom_node_attr" in loaded_town.town_graph.nodes[first_node]
            assert loaded_town.town_graph.nodes[first_node]["custom_node_attr"] == 123
            assert loaded_town.town_graph.nodes[first_node]["modified"] == True

            # Check place type swapping if we did it
            if 'original_place_types' in locals():
                for node, original_type in original_place_types.items():
                    assert loaded_town.town_graph.nodes[node]["place_type"] != original_type

            # Verify accommodation_node_ids reflect our changes
            assert set(loaded_town.accommodation_node_ids) == set(
                original_town.accommodation_node_ids)
