import pytest
import simcronomicon as scon
import h5py
import tempfile
import os
from test.test_helper import MODEL_MATRIX, default_step_events, setup_simulation

class TestSimulationInitializationGeneralized:
    @pytest.mark.parametrize("model_key,spreader_status", [
        ("seir", b'I'),
        ("seisir", b'S'),
        ("seiqrdv", b'I'),
    ])
    def test_initial_spreaders_placement(self, model_key, spreader_status):
        """
        Test that all initial spreaders are placed at the specified nodes (using the HDF5 log).
        Handles the case where nodes can be repeated (multiple spreaders at the same node).
        """
        _, _, _, _, _, _ = MODEL_MATRIX[model_key]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        # Use first 5 accommodation nodes, repeated twice
        town = scon.Town.from_files(
            metadata_path=MODEL_MATRIX[model_key][4],
            town_graph_path=MODEL_MATRIX[model_key][5],
            town_params=town_params
        )
        spreader_nodes = list(town.accommodation_node_ids)[:5] * 2
        town_params.spreader_initial_nodes = spreader_nodes
        sim, town, model = setup_simulation(model_key, town_params)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "out.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                log = h5file["individual_logs/log"][:]
                spreaders = [row for row in log if row['timestep'] == 0 and row['status'] == spreader_status]
                assert len(spreaders) == town_params.num_init_spreader
                spreader_addresses = [row['address'] for row in spreaders]
                assert sorted(spreader_addresses) == sorted(spreader_nodes)

    @pytest.mark.parametrize("model_key", ["seir", "seisir", "seiqrdv"])
    def test_spreader_initial_nodes_assertion(self, model_key):
        _, model_params_class, _, _, metadata_path, graphmlz_path = MODEL_MATRIX[model_key]
        # Case 1: More initial spreader nodes than num_init_spreader (should raise)
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=2)
        town_params.spreader_initial_nodes = [1, 2, 3]
        model_params = model_params_class(**MODEL_MATRIX[model_key][3])
        model = MODEL_MATRIX[model_key][0](model_params)
        town = scon.Town.from_files(metadata_path, graphmlz_path, town_params)
        with pytest.raises(AssertionError):
            model.initialize_sim_population(town)
        # Case 2: num_init_spreader is more than the number of given nodes (should pass)
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=5)
        town_params.spreader_initial_nodes = [1, 2]
        model = MODEL_MATRIX[model_key][0](model_params)
        town = scon.Town.from_files(metadata_path, graphmlz_path, town_params)
        model.initialize_sim_population(town)

class TestStepEventFunctionality:
    @pytest.mark.parametrize("model_key", ["seir", "seisir"])
    def test_disperse_and_end_day_events(self, model_key):
        _, _, folk_class, _, _, _ = MODEL_MATRIX[model_key]
        town_params = scon.TownParameters(num_pop=5, num_init_spreader=1)
        step_events = [
            scon.StepEvent(
                "go_to_work",
                folk_class.interact,
                scon.EventType.DISPERSE,
                10000,
                ['workplace']
            )
        ]
        sim, town, _ = setup_simulation(model_key, town_params, step_events=step_events, timesteps=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "stepevent_test.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                log = h5file["individual_logs/log"][:]
                # Check 'go_to_work' event
                go_to_work_rows = log[(log['timestep'] == 1) & (log['event'] == b"go_to_work")]
                for row in go_to_work_rows:
                    folk_id = row['folk_id']
                    address = row['address']
                    home_addr = next(folk.home_address for folk in sim.folks if folk.id == folk_id)
                    place_type = town.town_graph.nodes[address]['place_type']
                    assert address == home_addr or place_type == 'workplace', \
                        f"Folk {folk_id} at address {address} (type {place_type}) is not at home or workplace during go_to_work"
                # Check 'end_day' event that automatically gets appended regardless of the StepEvents input from the user
                end_day_rows = log[(log['timestep'] == 1) & (log['event'] == b"end_day")]
                for row in end_day_rows:
                    folk_id = row['folk_id']
                    address = row['address']
                    home_addr = next(folk.home_address for folk in sim.folks if folk.id == folk_id)
                    assert address == home_addr, f"Folk {folk_id} not at home at end_day (address {address}, home {home_addr})"

# For SEIQRDV, the functionality of priority place is tested in its own dedicated tests,
# since agents may prioritize 'healthcare_facility' and bypass typical destinations like 'workplace'.

class TestSimulationUpdate:
    @classmethod
    def setup_class(cls):
        cls.model_keys = ["seir", "seisir", "seiqrdv"]

    @pytest.mark.parametrize("model_key", ["seir", "seisir", "seiqrdv"])
    def test_population_conservation(self, model_key):
        _, _, folk_class, _, _, _ = MODEL_MATRIX[model_key]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        step_events = default_step_events(folk_class)
        sim, town, _ = setup_simulation(model_key, town_params, step_events=step_events, timesteps=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_cons_test.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                for row in summary:
                    total = sum(row[name] for name in row.dtype.names if name not in ("timestep", "current_event"))
                    assert total == 100, f"Population not conserved at timestep {row['timestep']}: got {total}, expected 100"

    def test_population_migration_and_death(self):
        # Only SEIQRDV truly updates population size after each day
        model_key = "seiqrdv"
        _, model_params_class, folk_class, extra_params, metadata_path, graphmlz_path = MODEL_MATRIX[model_key]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        step_events = default_step_events(folk_class)
        # Test migration (lam_cap=1, mu=0)
        params = dict(extra_params)
        params['lam_cap'] = 1
        params['mu'] = 0
        sim, town, _ = setup_simulation(model_key, town_params, step_events=step_events, timesteps=2, override_params=params)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_migration_test.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                step1 = summary[-2]
                step2 = summary[-1]
                total1 = sum(step1[name] for name in step1.dtype.names if name not in ("timestep", "current_event", "D"))
                total2 = sum(step2[name] for name in step2.dtype.names if name not in ("timestep", "current_event", "D"))
                assert total1 == 200, f"Population should be doubled at timestep {step1['timestep']}: got {total1}, expected 200"
                assert total2 == total1 * 2, f"Population should be doubled at timestep {step2['timestep']}: got {total2}, expected {total1 * 2}"
        # Test death (lam_cap=0, mu=1)
        params['lam_cap'] = 0
        params['mu'] = 1
        sim, town, _ = setup_simulation(model_key, town_params, step_events=step_events, timesteps=1, override_params=params)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_death_test.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                last_step = summary[-1]
                death_last = last_step["D"]
                assert death_last == 100, f"Population should be all dead at timestep {last_step['timestep']}: got {death_last}, expected 100"
                other_statuses = ["S", "E", "I", "Q", "R", "V"]
                for status in other_statuses:
                    assert last_step[status] == 0, "Population of other statuses should be equal to 0"

class TestSimulationResults:
    @classmethod
    def setup_class(cls):
        cls.model_matrix = [
            (
                "seir",
                {"S": 80, "E": 0, "I": 0, "R": 20}
            ),
            (
                "seisir",
                {"S": 0, "E": 0, "Is": 44, "Ir": 45, "R": 11}
            ),
            (
                "seiqrdv",
                {"S": 0, "E": 0, "I": 0, "Q": 0, "R": 2, "D": 20, "V": 78}
            ),
        ]

    def assert_h5_structure(self, h5_path):
        with h5py.File(h5_path, "r") as h5file:
            assert "metadata" in h5file, "'metadata' group missing in HDF5 file"
            assert "status_summary" in h5file, "'status_summary' group missing in HDF5 file"
            assert "individual_logs" in h5file, "'individual_logs' group missing in HDF5 file"
            assert "simulation_metadata" in h5file["metadata"], "'simulation_metadata' missing in metadata group"
            assert "town_metadata" in h5file["metadata"], "'town_metadata' missing in metadata group"
            assert "summary" in h5file["status_summary"], "'summary' missing in status_summary group"
            assert "log" in h5file["individual_logs"], "'log' missing in individual_logs group"

    @pytest.mark.parametrize("model_key,expected_status", [
        ("seir", {"S": 33, "E": 1, "I": 2, "R": 64}),
        ("seisir", {"S": 0, "E": 0, "Is": 45, "Ir": 44, "R": 11}),
        ("seiqrdv", {"S": 0, "E": 0, "I": 0, "Q": 0, "R": 3, "D": 19, "V": 78}),
    ])
    def test_status_summary_last_step(self, model_key, expected_status):
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        folk_class = MODEL_MATRIX[model_key][2]
        step_events = default_step_events(folk_class)
        sim, town, _ = setup_simulation(model_key, town_params, step_events=step_events, timesteps=50, seed=True, override_params=None)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "out.h5")
            sim.run(hdf5_path=h5_path)
            self.assert_h5_structure(h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                last_step = summary[-1]
                for status, expected_value in expected_status.items():
                    assert last_step[status] == expected_value, f"{status} mismatch: got {last_step[status]}, expected {expected_value}"