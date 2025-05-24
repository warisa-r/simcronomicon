"""
Tests for `simcronomicon` module.
"""
import pytest
import os
import shutil

# Import all the necessary packages for testing
import networkx as nx
import matplotlib.pyplot as plt
import random

import simcronomicon as scon

class TestTown(object):

    @classmethod
    def setup_class(cls):
        point = 50.7753, 6.0839
        # Set up a random town parameter
        cls.town_config_file_lists = [
            "town_graph_metadata.json",
            "town_graph.graphml",
            "raw_projected_graph.graphml"
        ]
        cls.town_params = scon.TownParameters(0.7, 2, 2000, 10)

        cls.town_from_files = scon.Town.from_files(metadata_path="test/test_data/town_graph_metadata_aachen.json",
                                        town_graph_path="test/test_data/town_graph_aachen.graphml",
                                        projected_graph_path="test/test_data/raw_projected_graph_aachen.graphml",
                                        town_params=cls.town_params
                                        )
        cls.town_from_point = scon.Town.from_point(point, 2000, cls.town_params)
        
    def test_node_and_edge_counts_match(self):
        assert len(self.town_from_files.G_projected.nodes) == len(self.town_from_point.G_projected.nodes), \
            f"Mismatch in G_projected node count: {len(self.town_from_files.G_projected.nodes)} != {len(self.town_from_point.G_projected.nodes)}"
        
        assert len(self.town_from_files.G_projected.edges) == len(self.town_from_point.G_projected.edges), \
            f"Mismatch in G_projected edge count: {len(self.town_from_files.G_projected.edges)} != {len(self.town_from_point.G_projected.edges)}"
        
        assert len(self.town_from_files.town_graph.nodes) == len(self.town_from_point.town_graph.nodes), \
            f"Mismatch in town_graph node count: {len(self.town_from_files.town_graph.nodes)} != {len(self.town_from_point.town_graph.nodes)}"
        
        assert len(self.town_from_files.town_graph.edges) == len(self.town_from_point.town_graph.edges), \
            f"Mismatch in town_graph edge count: {len(self.town_from_files.town_graph.edges)} != {len(self.town_from_point.town_graph.edges)}"
    
    def test_random_node_match(self):
        # Check that the attributes of the graphs generated from a given point is equal to the
        # pre-existing town graph

        # Start with checking a random node in the projected graphs
        node = random.choice(list(self.town_from_files.G_projected.nodes))
        attrs1 = self.town_from_files.G_projected.nodes[node]
        attrs2 = self.town_from_point.G_projected.nodes[node]

        for key in attrs1:
            v1 = attrs1[key]
            v2 = attrs2.get(key)

            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                assert round(v1, 3) == round(v2, 3), f"Mismatch at node {node}, key '{key}': {v1} != {v2} in the projected graphs."
            else:
                assert v1 == v2, f"Mismatch at node {node}, key '{key}': {v1} != {v2} in the projected graphs."

        # Check that this node connects to the same neighbors in both graphs
        neighbors1 = set(self.town_from_files.G_projected.neighbors(node))
        neighbors2 = set(self.town_from_point.G_projected.neighbors(node))

        assert neighbors1 == neighbors2, \
            f"Mismatch in neighbors of node {node}: {neighbors1} != {neighbors2} in the projected graphs."

        # Then check a randome node in the simple town graphs
        node = random.choice(list(self.town_from_files.town_graph.nodes))
        attrs1 = self.town_from_files.town_graph.nodes[node]
        attrs2 = self.town_from_point.town_graph.nodes[node]

        for key in attrs1:
            v1 = attrs1[key]
            v2 = attrs2.get(key)

            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                assert round(v1, 3) == round(v2, 3), f"Mismatch at node {node}, key '{key}': {v1} != {v2} in the town graphs."
            else:
                assert v1 == v2, f"Mismatch at node {node}, key '{key}': {v1} != {v2} in the town graphs."

        # Check that this node connects to the same neighbors in both graphs
        neighbors1 = set(self.town_from_files.town_graph.neighbors(node))
        neighbors2 = set(self.town_from_point.town_graph.neighbors(node))

        assert neighbors1 == neighbors2, \
            f"Mismatch in neighbors of node {node}: {neighbors1} != {neighbors2} in the town graphs."

    def test_random_edge_attributes_match(self):
        # Like random node test, we start with the projected graphs first
        edge = random.choice(list(self.town_from_files.G_projected.edges))

        attrs1 = self.town_from_files.G_projected.edges[edge]
        attrs2 = self.town_from_point.G_projected.edges[edge]

        for key in attrs1:
            v1 = attrs1[key]
            v2 = attrs2.get(key)

            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                assert round(v1, 3) == round(v2, 3), f"Mismatch at edge {edge}, key '{key}': {v1} != {v2} in the projected graphs."
            else:
                assert v1 == v2, f"Mismatch at edge {edge}, key '{key}': {v1} != {v2} in the projected graphs."

        # Now, check a random edge in the town graphs
        edge = random.choice(list(self.town_from_files.town_graph.edges))

        attrs1 = self.town_from_files.town_graph.edges[edge]
        attrs2 = self.town_from_point.town_graph.edges[edge]

        for key in attrs1:
            v1 = attrs1[key]
            v2 = attrs2.get(key)

            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                assert round(v1, 3) == round(v2, 3), f"Mismatch at edge {edge}, key '{key}': {v1} != {v2} in the town graphs."
            else:
                assert v1 == v2, f"Mismatch at edge {edge}, key '{key}': {v1} != {v2} in the town graphs."
    def test_save_files_exist(self):
        # Check that all the graph and metadata files produce from from_point exist
        for file in self.town_config_file_lists:
            assert os.path.exists(file), f"File {file} does not exist."

    @classmethod
    def teardown_class(cls):
        for file in cls.town_config_file_lists:
            if os.path.exists(file):
                os.remove(file)

        if os.path.exists("cache"):
            shutil.rmtree("cache")

class TestFolk(object):
    @classmethod
    def setup_class(cls):
        #TODO: Test this
        cls.folk1 = scon.Folk(1, 'Ir')
        cls.folk2 = scon.Folk(2, 'Is')
        cls.folk3 = scon.Folk(3, 'E')
        cls.folk4 = scon.Folk(4, 'S')
        cls.folk5 = scon.Folk(5, 'R')
    def test_folk_actions(self):
        scale_tipper = 1e-4
        status_dict_t = {'S': 1, 'Is': 1, 'Ir': 1, 'R': 1, 'E': 1}
        params = scon.SEIsIrRModelParameters(0.3, 0.5, 0.5, 0.4, 0.7, 0.2, 0.8, 0.3)

        folks_here = [self.folk1, self.folk2, self.folk3, self.folk4, self.folk5]
        # Test interaction between town folks

        # Test Rule 1 and if status_dict is updated after conversion
        a = self.folk1.inverse_bernoulli(folks_here, params.Ir2S, ['S'])
        self.folk1.interact(folks_here, status_dict_t, params, a - scale_tipper)
        assert self.folk1.status == 'S'
        assert status_dict_t == {'S': 2, 'Is': 1, 'Ir': 0, 'R': 1, 'E': 1}
        

        # Test Rule 2
        a1 = self.folk2.inverse_bernoulli(folks_here, params.Is2S, ['S'])
        a2 = self.folk2.inverse_bernoulli(folks_here, params.Is2E, ['S'])
        self.folk2.interact(folks_here, status_dict_t, params, a1 - scale_tipper)
        assert self.folk2.status == 'S'
        self.folk2.status = 'Is' # Reset
        self.folk2.interact(folks_here, status_dict_t, params, a2 - scale_tipper)
        assert self.folk2.status == 'E'

        # Test Rule 3
        a1 = self.folk3.inverse_bernoulli(folks_here, params.E2S, ['S'])
        a2 = self.folk3.inverse_bernoulli(folks_here, params.E2R, ['R'])
        self.folk3.interact(folks_here, status_dict_t, params, a1 - scale_tipper)
        assert self.folk3.status == 'S'
        self.folk3.status = 'E' # Reset
        self.folk3.interact(folks_here, status_dict_t, params, a2 - scale_tipper)
        assert self.folk3.status == 'R'
        self.folk3.status = 'E'

        # Test Rule 4.1 and social energy diminishing mechanism
        initial_energy = self.folk4.energy
        a = self.folk4.inverse_bernoulli(folks_here, params.S2R, ['S', 'E', 'R'])
        self.folk4.interact(folks_here, status_dict_t, params, a - scale_tipper)
        assert initial_energy == self.folk4.energy + 1
        assert self.folk4.status == 'R'
        self.folk4.status = 'S' # Reset

        # Test Rule 4.2 and sleeping
        self.folk4.spreader_streak = params.mem_span
        self.folk4.sleep(status_dict_t, params, params.forget + scale_tipper)
        assert self.folk4.status == 'R' and self.folk4.spreader_streak == 0
        self.folk4.status = 'S' # Reset
        self.folk4.sleep(status_dict_t, params, params.forget - scale_tipper)
        assert self.folk4.status == 'R' and self.folk4.spreader_streak == 0
        self.folk4.status = 'S' # Reset
        # Check if the spreader streak is updated
        self.folk4.sleep(status_dict_t, params, params.forget + scale_tipper)
        assert self.folk4.status == 'S' and self.folk4.spreader_streak == 1


    @classmethod
    def teardown_class(cls):
        pass

#TODO: Test that we check that there exists a place in the given map that has the priority place classification -> 500m from the same point
# Testdata have this info doesnt have hospitals
"""
    sim.run(True)
  File "C:\Users\user\Documents\School\Sem6\SCE\simcronomicon\simcronomicon\sim.py", line 229, in run
    status_row, indiv_rows = self.step(save_result=True)
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\user\Documents\School\Sem6\SCE\simcronomicon\simcronomicon\sim.py", line 136, in step
    self.execute_event(step_event)
  File "C:\Users\user\Documents\School\Sem6\SCE\simcronomicon\simcronomicon\sim.py", line 116, in execute_event
    self.disperse_for_event(step_event)
  File "C:\Users\user\Documents\School\Sem6\SCE\simcronomicon\simcronomicon\sim.py", line 80, in disperse_for_event
    person.priority_place_type.remove(chosen_place_type)
ValueError: list.remove(x): x not in list
"""

# TODO: Test all three models by seeing the last frame t = ... ensure no infected and all status are the same num
#