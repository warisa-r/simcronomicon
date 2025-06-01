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
            (scon.SEIRModel, scon.SEIRModelParameters, b'I', dict(max_energy=5, beta=0.4, sigma=6, gamma=5,
             xi=200), "test/test_data/aachen_dom_500m_metadata.json", "test/test_data/aachen_dom_500m.graphmlz"),
            (scon.SEIsIrRModel, scon.SEIsIrRModelParameters, b'S', dict(max_energy=5, literacy=0.5, gamma=0.5, alpha=0.5, lam=0.5, phi=0.5, theta=0.5,
             mu=0.5, eta1=0.5, eta2=0.5, mem_span=10), "test/test_data/aachen_dom_500m_metadata.json", "test/test_data/aachen_dom_500m.graphmlz"),
            (scon.SEIQRDVModel, scon.SEIQRDVModelParameters, b'I', dict(max_energy=5, lam_cap=0.01, beta=0.4, alpha=0.5, gamma=3, delta=2, lam=4, rho=5,
             kappa=0.2, mu=0.01, hospital_capacity=100), "test/test_data/uniklinik_500m_metadata.json", "test/test_data/uniklinik_500m.graphmlz"),
        ]

    @pytest.mark.parametrize("model_idx", [0, 1, 2])
    def test_initial_spreaders_placement(self, model_idx):
        """
        Test that all initial spreaders are placed at the specified nodes (using the HDF5 log).
        Handles the case where nodes can be repeated (multiple spreaders at the same node).
        """
        model_class, model_params_class, spreader_status, extra_params, metadata_path, graphmlz_path = self.model_matrix[
            model_idx]
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
                spreaders = [row for row in log if row['timestep']
                             == 0 and row['status'] == spreader_status]
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
        model_class, model_params_class, _, extra_params, metadata_path, graphmlz_path = self.model_matrix[
            model_idx]
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


class TestSimulationUpdate:
    @classmethod
    def setup_class(cls):
        # (model_class, model_params_class, folk_class, extra_params, metadata_path, graphmlz_path, expected_status_dict)
        cls.model_matrix = [
            (
                scon.SEIRModel,
                scon.SEIRModelParameters,
                scon.FolkSEIR,
                dict(max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200),
                "test/test_data/aachen_dom_500m_metadata.json",
                "test/test_data/aachen_dom_500m.graphmlz",
            ),
            (
                scon.SEIsIrRModel,
                scon.SEIsIrRModelParameters,
                scon.FolkSEIsIrR,
                dict(max_energy=5, literacy=0.5, gamma=0.5, alpha=0.5, lam=0.5,
                     phi=0.5, theta=0.5, mu=0.5, eta1=0.5, eta2=0.5, mem_span=10),
                "test/test_data/aachen_dom_500m_metadata.json",
                "test/test_data/aachen_dom_500m.graphmlz",
            ),
            (
                scon.SEIQRDVModel,
                scon.SEIQRDVModelParameters,
                scon.FolkSEIQRDV,
                dict(max_energy=5, lam_cap=0, beta=0.4, alpha=0.5, gamma=3,
                     delta=2, lam=4, rho=5, kappa=0.2, mu=0.1, hospital_capacity=100),
                "test/test_data/uniklinik_500m_metadata.json",
                "test/test_data/uniklinik_500m.graphmlz",
            ),
        ]

    @pytest.mark.parametrize("model_idx", [0, 1, 2])
    def test_population_conservation(self, model_idx):
        model_class, model_params_class, folk_class, extra_params, metadata_path, graphmlz_path = self.model_matrix[
            model_idx]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        town = scon.Town.from_files(
            metadata_path=metadata_path,
            town_graph_path=graphmlz_path,
            town_params=town_params
        )
        step_events = [
            scon.StepEvent(
                "greet_neighbors",
                folk_class.interact,
                scon.EventType.DISPERSE,
                5000,
                ['accommodation']),
            scon.StepEvent(
                "chore",
                folk_class.interact,
                scon.EventType.DISPERSE,
                19000,
                [
                    'commercial',
                    'workplace',
                    'education',
                    'religious'
                ],
                scon.log_normal_probabilities)
        ]
        model_params = model_params_class(**extra_params)
        model = model_class(model_params, step_events=step_events)
        sim = scon.Simulation(town, model, timesteps=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_cons_test.h5")
            sim.run(save_result=True, hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                # For each timestep, sum all status columns except 'timestep' and 'current_event'
                for row in summary:
                    # Only sum integer columns (statuses)
                    total = sum(row[name] for name in row.dtype.names if name not in (
                        "timestep", "current_event"))
                    assert total == 100, f"Population not conserved at timestep {row['timestep']}: got {total}, expected 100"

    def test_population_migration_and_death(self):
        # Since SEIQRDV is the only class that truly update population status and size after each day has passed
        # It is the representative model for testing the update_population functionality of the software
        self.model_matrix[2][4]
        model_class, model_params_class, folk_class, extra_params, metadata_path, graphmlz_path = self.model_matrix[
            2]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        town = scon.Town.from_files(
            metadata_path=metadata_path,
            town_graph_path=graphmlz_path,
            town_params=town_params
        )
        step_events = [
            scon.StepEvent(
                "greet_neighbors",
                folk_class.interact,
                scon.EventType.DISPERSE,
                5000,
                ['accommodation']),
            scon.StepEvent(
                "chore",
                folk_class.interact,
                scon.EventType.DISPERSE,
                19000,
                [
                    'commercial',
                    'workplace',
                    'education',
                    'religious'
                ],
                scon.log_normal_probabilities)
        ]
        params = dict(extra_params)
        params['lam_cap'] = 1
        params['mu'] = 0
        model_params = model_params_class(**params)
        model = model_class(model_params, step_events=step_events)
        sim = scon.Simulation(town, model, timesteps=2)

        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_migration_test.h5")
            sim.run(save_result=True, hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                step1 = summary[-2]
                step2 = summary[-1]
                # Expect living population to double for the first step where nobody has died yet
                total1 = sum(step1[name] for name in step1.dtype.names if name not in (
                    "timestep", "current_event", "D"))
                total2 = sum(step2[name] for name in step2.dtype.names if name not in (
                    "timestep", "current_event", "D"))
                assert total1 == 200, f"Population should be doubled at timestep {step1['timestep']}: got {total1}, expected 200"
                assert total2 == total1 * \
                    2, f"Population should be doubled at timestep {step2['timestep']}: got {total2}, expected {total1 * 2}"

        params['lam_cap'] = 0
        params['mu'] = 1
        model_params = model_params_class(**params)
        model = model_class(model_params, step_events=step_events)
        sim = scon.Simulation(town, model, timesteps=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_death_test.h5")
            sim.run(save_result=True, hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                last_step = summary[-1]
                # Expect living population to double for the first step where nobody has died yet
                death_last = last_step["D"]
                assert death_last == 100, f"Population should be all be dead at timestep {last_step['timestep']}: got {death_last}, expected 100"
                other_statuses = ["S", "E", "I", "Q", "R", "V"]
                for status in other_statuses:
                    assert last_step[status] == 0, "Population of other statuses should be equal to 0"


class TestSimulationResults:
    @classmethod
    #TODO: Update these numbers as things changed
    def setup_class(cls):
        # (model_class, model_params_class, folk_class, extra_params, metadata_path, graphmlz_path, expected_status_dict)
        cls.model_matrix = [
            (
                scon.SEIRModel,
                scon.SEIRModelParameters,
                scon.FolkSEIR,
                dict(max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200),
                "test/test_data/aachen_dom_500m_metadata.json",
                "test/test_data/aachen_dom_500m.graphmlz",
                {"S": 68, "E": 0, "I": 0, "R": 32}
            ),
            (
                scon.SEIsIrRModel,
                scon.SEIsIrRModelParameters,
                scon.FolkSEIsIrR,
                dict(max_energy=5, literacy=0.5, gamma=0.5, alpha=0.5, lam=0.5,
                     phi=0.5, theta=0.5, mu=0.5, eta1=0.5, eta2=0.5, mem_span=10),
                "test/test_data/aachen_dom_500m_metadata.json",
                "test/test_data/aachen_dom_500m.graphmlz",
                {"S": 0, "E": 0, "Is": 45, "Ir": 43, "R": 12}
            ),
            (
                scon.SEIQRDVModel,
                scon.SEIQRDVModelParameters,
                scon.FolkSEIQRDV,
                dict(max_energy=5, lam_cap=0.01, beta=0.4, alpha=0.5, gamma=3,
                     delta=2, lam=4, rho=5, kappa=0.2, mu=0.01, hospital_capacity=100),
                "test/test_data/uniklinik_500m_metadata.json",
                "test/test_data/uniklinik_500m.graphmlz",
                {"S": 0, "E": 0, "I": 0, "Q": 0, "R": 2, "D": 20, "V": 78}
            ),
        ]

    def assert_h5_structure(self, h5_path):
        # Ensure that the output file is properly saved
        with h5py.File(h5_path, "r") as h5file:
            assert "metadata" in h5file, "'metadata' group missing in HDF5 file"
            assert "status_summary" in h5file, "'status_summary' group missing in HDF5 file"
            assert "individual_logs" in h5file, "'individual_logs' group missing in HDF5 file"
            assert "simulation_metadata" in h5file["metadata"], "'simulation_metadata' missing in metadata group"
            assert "town_metadata" in h5file["metadata"], "'town_metadata' missing in metadata group"
            assert "summary" in h5file["status_summary"], "'summary' missing in status_summary group"
            assert "log" in h5file["individual_logs"], "'log' missing in individual_logs group"

    @pytest.mark.parametrize("model_idx", [0, 1, 2])
    def test_status_summary_last_step(self, model_idx):
        """
        Test that the status summary at the last timestep matches the expected values.
        """
        model_class, model_params_class, folk_class, extra_params, metadata_path, graphmlz_path, expected_status = self.model_matrix[
            model_idx]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        town = scon.Town.from_files(
            metadata_path=metadata_path,
            town_graph_path=graphmlz_path,
            town_params=town_params
        )
        # Use the correct folk_class for each model's step_events
        step_events = [
            scon.StepEvent(
                "greet_neighbors",
                folk_class.interact,
                scon.EventType.DISPERSE,
                5000,
                ['accommodation']),
            scon.StepEvent(
                "chore",
                folk_class.interact,
                scon.EventType.DISPERSE,
                19000,
                [
                    'commercial',
                    'workplace',
                    'education',
                    'religious'
                ],
                scon.log_normal_probabilities)
        ]
        model_params = model_params_class(**extra_params)
        model = model_class(model_params, step_events=step_events)
        sim = scon.Simulation(town, model, timesteps=50,
                              seed=True, seed_value=123)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "out.h5")
            sim.run(save_result=True, hdf5_path=h5_path)
            self.assert_h5_structure(h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                last_step = summary[-1]
                for status, expected_value in expected_status.items():
                    assert last_step[status] == expected_value, f"{status} mismatch: got {last_step[status]}, expected {expected_value}"
