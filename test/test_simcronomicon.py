"""
Tests for `simcronomicon` module.
"""
import pytest

# Import all the necessary packages for testing
import matplotlib.pyplot as plt

import simcronomicon as scon


class TestSimcronomicon(object):

    @classmethod
    def setup_class(cls):
        cls.town = scon.create_town(10, 0.5)

    def test_town(self):
        scon.draw_town(self.town)
        assert len(plt.gcf().get_axes()) > 0

    @classmethod
    def teardown_class(cls):
        pass
