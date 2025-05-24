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

    @classmethod
    def teardown_class(cls):
        for prefix in ["dom", "uniklinik"]:
            for fname in ["town_graph_metadata.json", "town_graph.graphmlz"]:
                fpath = f"{prefix}_{fname}"
                if os.path.exists(fpath):
                    os.remove(fpath)

        if os.path.exists("cache"):
            shutil.rmtree("cache")