"""
Tests for `simcronomicon` module.
"""
import pytest

# Import all the necessary packages for testing
import networkx as nx
import matplotlib.pyplot as plt
import random

import simcronomicon as scon

class TestTown(object):

    @classmethod
    def setup_class(cls):
        G = scon.create_town_graph(20, 0.3)
        cls.town = scon.Town(G, 0.5, 10)

    def test_town(self):
        assert len(self.town.town_graph.nodes()) == 20 and self.town.town_graph.nodes[random.randint(0, 19)]['folk'] == []
        self.town.draw_town()

        # Check if something was drawn on the figure
        fig = plt.gcf()
        assert len(fig.get_axes()) > 0 or len(fig.get_children()) > 0

        plt.close(fig)

    @classmethod
    def teardown_class(cls):
        pass

class TestFolk(object):
    @classmethod
    def setup_class(cls):
        cls.folk1 = scon.Folk(1, 'Ir')
        cls.folk2 = scon.Folk(2, 'Is')
        cls.folk3 = scon.Folk(3, 'E')
        cls.folk4 = scon.Folk(4, 'S')
        cls.folk5 = scon.Folk(5, 'R')
    def test_folk_actions(self):
        scale_tipper = 1e-4
        status_dict_t = {'S': 1, 'Is': 1, 'Ir': 1, 'R': 1, 'E': 1}
        params = scon.SimulationParameters(0.4, 0.5, 0.5, 0.4, 0.7, 0.5, 0.8, 0.3)
        # Test interaction between town folks

        # Test Rule 1 and if status_dict is updated after conversion
        self.folk1.interact(self.folk4, status_dict_t, params, params.Ir2S + scale_tipper)
        assert status_dict_t == {'S': 2, 'Is': 1, 'Ir': 0, 'R': 1, 'E': 1}
        assert self.folk1.status == 'S'

        # Test Rule 2
        self.folk2.interact(self.folk4, status_dict_t, params, params.Is2S + scale_tipper)
        assert self.folk2.status == 'S'
        self.folk2.status = 'Is' # Reset
        self.folk2.interact(self.folk4, status_dict_t, params, params.Is2E + scale_tipper)
        assert self.folk2.status == 'E'

        # Test Rule 3
        self.folk3.interact(self.folk4, status_dict_t, params, params.E2S + scale_tipper)
        assert self.folk3.status == 'S'
        self.folk3.status = 'E' # Reset
        self.folk3.interact(self.folk5, status_dict_t, params, params.E2R + scale_tipper)
        assert self.folk3.status == 'R'
        self.folk3.status = 'E'

        # Test Rule 4.1 and social energy diminishing mechanism
        initial_energy = self.folk4.social_energy
        selected_folk = random.choice([self.folk3, self.folk5])
        self.folk4.interact(selected_folk, status_dict_t, params, params.S2R + scale_tipper)
        assert initial_energy == self.folk4.social_energy + 1
        assert self.folk4.status == 'R'
        self.folk4.status = 'S' # Reset

        # Test Rule 4.2 and sleeping
        self.folk4.spreader_streak = params.mem_span
        self.folk4.sleep(status_dict_t, params, params.forget - scale_tipper)
        assert self.folk4.status == 'R' and self.folk4.spreader_streak == 0
        self.folk4.status = 'S' # Reset
        self.folk4.sleep(status_dict_t, params, params.forget + scale_tipper)
        assert self.folk4.status == 'R' and self.folk4.spreader_streak == 0
        self.folk4.status = 'S' # Reset
        # Check if the spreader streak is updated otherwise and if the social energy has been resetted
        self.folk4.social_energy = 0
        self.folk4.sleep(status_dict_t, params, params.forget - scale_tipper)
        assert self.folk4.social_energy >= 4 and self.folk4.status == 'S' and self.folk4.spreader_streak == 1


    @classmethod
    def teardown_class(cls):
        pass