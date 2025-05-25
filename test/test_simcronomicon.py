"""
Tests for `simcronomicon` module.
"""
import pytest
import os
import shutil
import pyproj
import numpy as np

# Import all the necessary packages for testing
import networkx as nx
import matplotlib.pyplot as plt
import random

import simcronomicon as scon

class TestTown(object):

    @classmethod
    def setup_class(cls):
        cls.point_dom = 50.7753, 6.0839
        cls.point_uniklinik = 50.77583, 6.045277
        cls.town_params = scon.TownParameters(100, 10)

        cls.town_dom = scon.Town.from_point(cls.point_dom, 500, cls.town_params)
        cls.files_dom = [
            "town_graph_metadata.json",
            "town_graph.graphmlz"
        ]
        for file in cls.files_dom:
            os.rename(file, f"dom_{file}")

        cls.town_uniklinik = scon.Town.from_point(cls.point_uniklinik, 500, cls.town_params)
        cls.files_uniklinik = [
            "town_graph_metadata.json",
            "town_graph.graphmlz"
        ]
        for file in cls.files_uniklinik:
            os.rename(file, f"uniklinik_{file}")

    def test_healthcare_presence_and_all_types(self):
        assert 'healthcare_facility' not in self.town_dom.found_place_types, \
            "Expected DOM area to have no healthcare_facility"
        assert 'healthcare_facility' in self.town_uniklinik.found_place_types, \
            "Expected UNIKLINIK area to have healthcare_facility"

        assert self.town_dom.all_place_types == self.town_uniklinik.all_place_types, \
            "Expected both towns to have the same all_place_types list"

    def test_superc_is_classified_as_education(self):
        superc_latlon = (50.77828, 6.078571)
        dom_750m_graph_path = "test/test_data/town_graph_aachen_dom_750m.graphmlz"
        dom_750m_metadatata_path = "test/test_data/town_graph_metadata_aachen_dom_750m.json"
        town = scon.Town.from_files(metadata_path=dom_750m_metadatata_path, town_graph_path= dom_750m_graph_path, town_params= self.town_params)

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
        """
        Test that the distance from the center of a large (2000m) DOM town to Theresienkirche and Hausarzt
        is shorter than from a small (750m) DOM town, and that the distances do not deviate from expected values by more than 50m.
        """
        from scipy.spatial import KDTree

        # Coordinates of landmarks
        coords_theresienkirche = (50.77828, 6.078571)  # Theresienkirche
        coords_hausarzt = (50.76943, 6.081437)         # Hausarzt

        # Build two towns: one with 2000m, one with 750m
        town_params_2000 = scon.TownParameters(100, 10)
        town_2000 = scon.Town.from_point(self.point_dom, 2000, town_params_2000)
        town_params_750 = scon.TownParameters(100, 10)
        town_750 = scon.Town.from_point(self.point_dom, 750, town_params_750)

        # Helper to get node nearest to a coordinate
        def get_nearest_node(town, coords):
            df = town.df_places
            coords_arr = df[["lat", "lon"]].to_numpy()
            kdtree = KDTree(coords_arr)
            node_ids = df["node_id"].to_numpy()
            _, idx = kdtree.query(coords)
            return int(node_ids[idx])

        node_theresienkirche_2000 = get_nearest_node(town_2000, coords_theresienkirche)
        node_hausarzt_2000 = get_nearest_node(town_2000, coords_hausarzt)
        node_theresienkirche_750 = get_nearest_node(town_750, coords_theresienkirche)
        node_hausarzt_750 = get_nearest_node(town_750, coords_hausarzt)

        # Helper to get shortest path distance between two nodes
        def get_shortest_path_length(town, node_a, node_b):
            G = town.town_graph
            assert nx.has_path(G, node_a, node_b), \
                "A path between Super C and the destinations (Theresienkirche/ Hausarzt) isn't found!"
            return nx.shortest_path_length(G, node_a, node_b, weight="weight")

        # Expected distances (meters)
        expected_theresienkirche = 335
        expected_hausarzt = 1245
        tolerance = 50

        # Calculate distances
        dist_theresienkirche_2000 = get_shortest_path_length(town_2000, town_2000.center_node, node_theresienkirche_2000)
        dist_theresienkirche_750 = get_shortest_path_length(town_750, town_750.center_node, node_theresienkirche_750)
        dist_hausarzt_2000 = get_shortest_path_length(town_2000, town_2000.center_node, node_hausarzt_2000)
        dist_hausarzt_750 = get_shortest_path_length(town_750, town_750.center_node, node_hausarzt_750)

        # Assert that 2000m town gives shorter or equal distances than 750m town
        # since with more streets included, a shorter or equal path is expected to be found.
        assert dist_theresienkirche_2000 <= dist_theresienkirche_750, "Distance to Theresienkirche should be shorter in 2000m town"
        assert dist_hausarzt_2000 <= dist_hausarzt_750, "Distance to Hausarzt should be shorter in 2000m town"

        # Assert that distances do not deviate from expected values by more than 50m
        assert abs(dist_theresienkirche_2000 - expected_theresienkirche) < tolerance, \
            f"Distance to Theresienkirche deviates by more than {tolerance}m (got {dist_theresienkirche_2000:.2f}m)"
        assert abs(dist_hausarzt_2000 - expected_hausarzt) < tolerance, \
            f"Distance to Hausarzt deviates by more than {tolerance}m (got {dist_hausarzt_2000:.2f}m)"
    @classmethod
    def teardown_class(cls):
        for prefix in ["dom", "uniklinik"]:
            for fname in ["town_graph_metadata.json", "town_graph.graphmlz"]:
                fpath = f"{prefix}_{fname}"
                if os.path.exists(fpath):
                    os.remove(fpath)

        if os.path.exists("cache"):
            shutil.rmtree("cache")