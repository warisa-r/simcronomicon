"""
Tests for `simcronomicon.town` module.
"""
import pytest
import os
import shutil
import pyproj
import numpy as np
import tempfile
from scipy.spatial import KDTree
from pyproj import Transformer

# Import all the necessary packages for testing
import networkx as nx
import osmnx as ox

import simcronomicon as scon

class TestTown(object):
    def setup_method(self):
        # Disable OSMnx cache for tests
        ox.settings.use_cache = False
        # Remove OSMnx cache directory if it exists
        cache_dir = os.path.expanduser("~/.osmnx")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        # Remove any custom cache or temp files the code might create
        if os.path.exists("cache"):
            shutil.rmtree("cache")

    def teardown_method(self):
        # Repeat cleanup after each test
        cache_dir = os.path.expanduser("~/.osmnx")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        if os.path.exists("cache"):
            shutil.rmtree("cache")

    def test_graphmlz_file_saved_and_overwrite_prompt(self):
        import builtins

        point_dom = 50.7753, 6.0839
        town_params = scon.TownParameters(100, 10)
        with tempfile.TemporaryDirectory() as tmpdir:
            file_prefix = "overwrite_test"
            graphmlz_path = os.path.join(tmpdir, f"{file_prefix}.graphmlz")

            # First save: file should be created
            town = scon.Town.from_point(point_dom, 500, town_params, file_prefix=file_prefix, save_dir=tmpdir)
            assert os.path.exists(graphmlz_path), "GraphMLZ file was not saved in the specified directory"

            # Second save: should prompt for overwrite
            prompts = []
            def fake_input(prompt):
                prompts.append(prompt)
                return "y"  # Simulate user typing 'y' to overwrite

            # Patch input to simulate user confirmation
            original_input = builtins.input
            builtins.input = fake_input
            try:
                town2 = scon.Town.from_point(point_dom, 500, town_params, file_prefix=file_prefix, save_dir=tmpdir)
            finally:
                builtins.input = original_input

            # Check that the prompt was shown
            assert any("already exists. Overwrite?" in p for p in prompts), "Overwrite prompt was not shown"

    def test_spreader_initial_nodes_assertion_error(self):
        """
        Edge case: Both from_point and from_files should raise an AssertionError
        if town_params.spreader_initial_nodes contains nodes not in the graph.
        """
        test_graphmlz = "test/test_data/aachen_dom_500m.graphmlz"
        test_metadata = "test/test_data/aachen_dom_500m_metadata.json"
        town_params = scon.TownParameters(100, 10)
        # Set spreader_initial_nodes to include a non-existent node (10000)
        town_params.spreader_initial_nodes = [1, 10000]
        point_dom = 50.7753, 6.0839

        # from_point should raise AssertionError
        with pytest.raises(AssertionError):
            scon.Town.from_point(point_dom, 500, town_params)

        # from_files should raise AssertionError
        with pytest.raises(AssertionError):
            scon.Town.from_files(
                metadata_path=test_metadata,
                town_graph_path=test_graphmlz,
                town_params=town_params
        )

    def test_healthcare_presence_and_all_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            point_dom = 50.7753, 6.0839
            point_uniklinik = 50.77583, 6.045277
            town_params = scon.TownParameters(100, 10)

            town_dom = scon.Town.from_point(point_dom, 500, town_params, file_prefix="dom", save_dir=tmpdir)
            town_uniklinik = scon.Town.from_point(point_uniklinik, 500, town_params, file_prefix="uniklinik", save_dir=tmpdir)

            assert 'healthcare_facility' not in town_dom.found_place_types, \
                "Expected the area within 0.5km from Aachener Dom to have no healthcare_facility."
            assert 'healthcare_facility' in town_uniklinik.found_place_types, \
                "Expected the area within 0.5km from Uniklinik to have healthcare_facility"

            assert town_dom.all_place_types == town_uniklinik.all_place_types, \
                "Expected both towns to have the same all_place_types list"

    def test_superc_is_classified_as_education(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            superc_latlon = (50.77828, 6.078571)
            point_dom = 50.7753, 6.0839
            town_params = scon.TownParameters(100, 10)
            town = scon.Town.from_point(point_dom, 750, town_params, file_prefix="dom_750m", save_dir=tmpdir)

            # Project lat/lon to same CRS as town graph
            wgs84 = pyproj.CRS("EPSG:4326")
            target_crs = pyproj.CRS(town.epsg_code)
            transformer = pyproj.Transformer.from_crs(wgs84, target_crs, always_xy=True)
            x_proj, y_proj = transformer.transform(superc_latlon[1], superc_latlon[0])

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
            place_type = town.town_graph.nodes[closest_node_id].get("place_type")
            assert place_type == "education", f"Expected 'education', got '{place_type}'"

            # Confirm that the actual coordinate of super C centroid is not far
            actual_x = town.town_graph.nodes[closest_node_id]["x"]
            actual_y = town.town_graph.nodes[closest_node_id]["y"]
            euclidean_distance = np.sqrt((actual_x - x_proj)**2 + (actual_y - y_proj)**2)
            assert euclidean_distance < 50, f"Too far from SuperC (~{euclidean_distance:.2f} m)"

    def test_distance_to_landmarks_dom(self):

        # Coordinates of landmarks
        coords_theresienkirche = (50.77809, 6.081859)  # Theresienkirche
        coords_hausarzt = (50.76943, 6.081437)         # Hausarzt
        coords_superC = (50.77828, 6.078571)           # SuperC 
        point_dom = 50.7753, 6.0839

        town_params_2000 = scon.TownParameters(100, 10)
        town_params_750 = scon.TownParameters(100, 10)
        with tempfile.TemporaryDirectory() as tmpdir:
            town_2000 = scon.Town.from_point(point_dom, 2000, town_params_2000, file_prefix="dom_2000m", save_dir=tmpdir)
            town_750 = scon.Town.from_point(point_dom, 750, town_params_750, file_prefix="dom_750m", save_dir=tmpdir)

            # Helper to get node nearest to a coordinate
            def get_nearest_node(town, coords):
                lat, lon = coords
                # Transform lat/lon to projected x/y coordinates
                transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{town.epsg_code}", always_xy=True)
                x, y = transformer.transform(lon, lat)

                # Find the closest node in the graph using Euclidean distance
                min_dist = float("inf")
                closest_node = None
                for node, data in town.town_graph.nodes(data=True):
                    dx = float(data["x"]) - x
                    dy = float(data["y"]) - y
                    dist = dx ** 2 + dy ** 2  # squared distance
                    if dist < min_dist:
                        min_dist = dist
                        closest_node = node
                return closest_node
            # Helper to get shortest path distance between two nodes
            def get_shortest_path_length(town, node_a, node_b):
                G = town.town_graph
                assert nx.has_path(G, node_a, node_b), \
                    "A path between Super C and the destinations (Theresienkirche/ Hausarzt) isn't found!"
                return nx.shortest_path_length(G, node_a, node_b, weight="weight")
                
            node_theresienkirche_2000 = get_nearest_node(town_2000, coords_theresienkirche)
            node_hausarzt_2000 = get_nearest_node(town_2000, coords_hausarzt)
            node_superC_2000 = get_nearest_node(town_2000, coords_superC)
            node_theresienkirche_750 = get_nearest_node(town_750, coords_theresienkirche)
            node_hausarzt_750 = get_nearest_node(town_750, coords_hausarzt)
            node_superC_750 = get_nearest_node(town_750, coords_superC)

            # Expected distances (meters)
            expected_theresienkirche = 335
            expected_hausarzt = 1245
            tolerance = 50

            # Calculate distances
            dist_theresienkirche_2000 = get_shortest_path_length(town_2000, node_superC_2000, node_theresienkirche_2000)
            dist_theresienkirche_750 = get_shortest_path_length(town_750, node_superC_750, node_theresienkirche_750)
            dist_hausarzt_2000 = get_shortest_path_length(town_2000, node_superC_2000, node_hausarzt_2000)
            dist_hausarzt_750 = get_shortest_path_length(town_750, node_superC_750, node_hausarzt_750)

            # Assert that 2000m town gives shorter or equal distances than 750m town
            assert dist_theresienkirche_2000 <= dist_theresienkirche_750, "Distance to Theresienkirche should be shorter in 2000m town"
            assert dist_hausarzt_2000 <= dist_hausarzt_750, "Distance to Hausarzt should be shorter in 2000m town"

            # Assert that distances do not deviate from expected values by more than 50m
            assert abs(dist_theresienkirche_2000 - expected_theresienkirche) < tolerance, \
                f"Distance to Theresienkirche deviates by more than {tolerance}m (got {dist_theresienkirche_2000:.2f}m)"
            assert abs(dist_hausarzt_2000 - expected_hausarzt) < tolerance, \
                f"Distance to Hausarzt deviates by more than {tolerance}m (got {dist_hausarzt_2000:.2f}m)"