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
        point = 50.7753, 6.0839
        # Set up a random town parameter
        cls.town_params = scon.TownParameters(0.7, 2, 2000, 10)
        cls.town = scon.Town.from_point(point, 2000, cls.town_params)
        cls.town = 

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
        initial_energy = self.folk4.social_energy
        a = self.folk4.inverse_bernoulli(folks_here, params.S2R, ['S', 'E', 'R'])
        self.folk4.interact(folks_here, status_dict_t, params, a - scale_tipper)
        assert initial_energy == self.folk4.social_energy + 1
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