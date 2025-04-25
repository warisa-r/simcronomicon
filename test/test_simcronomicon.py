"""
Tests for `simcronomicon` module.
"""
import pytest

# Import all the necessary packages for testing
import networkx as nx
import matplotlib.pyplot as plt

import simcronomicon as scon

class TestTown(object):

    @classmethod
    def setup_class(cls):
        G = scon.create_town_graph(20, 0.3)
        cls.town = scon.Town(G, 10, 0.5)

    def test_town(self):
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
        #cls.folk = scon.Folk(G, 10, 0.5)
        pass
    def test_town(self):
        pass
    @classmethod
    def teardown_class(cls):
        pass