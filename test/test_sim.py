"""
Tests for `simcronomicon.sim` module.
"""

import pytest
import simcronomicon as scon
import h5py
import tempfile
import os

class TestSimulationInitializationGeneralized:
    @classmethod
    def setup_class(cls):
        cls.model_matrix = [
            (scon.SEIRModel, scon.SEIRModelParameters, b'I', dict(max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200), "test/test_data/aachen_dom_500m_metadata.json", "test/test_data/aachen_dom_500m.graphmlz"),
            (scon.SEIsIrRModel, scon.SEIsIrRModelParameters, b'S', dict(max_energy=5, literacy=0.5, gamma=0.5, alpha=0.5, lam=0.5, phi=0.5, theta=0.5, mu=0.5, eta1=0.5, eta2=0.5, mem_span=10), "test/test_data/aachen_dom_500m_metadata.json", "test/test_data/aachen_dom_500m.graphmlz"),
            (scon.SEIQRDVModel, scon.SEIQRDVModelParameters, b'I', dict(max_energy=5, lam_cap=0.01, beta=0.4, alpha=0.5, gamma=3, delta=2, lam=4, rho=5, kappa=0.2, mu=0.01, hospital_capacity=100), "test/test_data/uniklinik_500m_metadata.json", "test/test_data/uniklinik_500m.graphmlz"),
        ]

    @pytest.mark.parametrize("model_idx", [0, 1, 2])
    def test_initial_spreaders_placement(self, model_idx):
        """
        Test that all initial spreaders are placed at the specified nodes (using the HDF5 log).
        Handles the case where nodes can be repeated (multiple spreaders at the same node).
        """
        model_class, model_params_class, spreader_status, extra_params, metadata_path, graphmlz_path = self.model_matrix[model_idx]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        town = scon.Town.from_files(
            metadata_path=metadata_path,
            town_graph_path=graphmlz_path,
            town_params=town_params
        )
        spreader_nodes = list(town.accommodation_node_ids)[:5] * 2
        town_params.spreader_initial_nodes = spreader_nodes
        model_params = model_params_class(**extra_params)
        model = model_class(model_params)
        sim = scon.Simulation(town, model, 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "out.h5")
            sim.run(save_result=True, hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                log = h5file["individual_logs/log"][:]
                spreaders = [row for row in log if row['timestep'] == 0 and row['status'] == spreader_status]
                num_spreaders = len(spreaders)
                assert num_spreaders == town_params.num_init_spreader
                spreader_addresses = [row['address'] for row in spreaders]
                assert sorted(spreader_addresses) == sorted(spreader_nodes)

    @pytest.mark.parametrize("model_idx", [0, 1, 2])
    def test_spreader_initial_nodes_assertion(self, model_idx):
        """
        Test assertion error when the number of initial spreader nodes is greater than num_init_spreader,
        and when num_init_spreader is more than the number of given nodes (should pass).
        """
        model_class, model_params_class, _, extra_params, metadata_path, graphmlz_path = self.model_matrix[model_idx]
        # Case 1: More initial spreader nodes than num_init_spreader (should raise)
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=2)
        town_params.spreader_initial_nodes = [1, 2, 3]
        model_params = model_params_class(**extra_params)
        model = model_class(model_params)
        town = scon.Town.from_files(
            metadata_path=metadata_path,
            town_graph_path=graphmlz_path,
            town_params=town_params
        )
        with pytest.raises(AssertionError):
            model.initialize_sim_population(town)

        # Case 2: num_init_spreader is more than the number of given nodes (should pass)
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=5)
        town_params.spreader_initial_nodes = [1, 2]
        model = model_class(model_params)
        town = scon.Town.from_files(
            metadata_path=metadata_path,
            town_graph_path=graphmlz_path,
            town_params=town_params
        )
        model.initialize_sim_population(town)