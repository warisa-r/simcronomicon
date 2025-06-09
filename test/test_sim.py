import pytest
import simcronomicon as scon
import h5py
import tempfile
import os
from test.test_helper import MODEL_MATRIX, default_test_step_events, setup_simulation


class TestSimulationInitializationGeneralized:
    @pytest.mark.parametrize("model_key,spreader_status", [
        ("seir", b'I'),
        ("seisir", b'S'),
        ("seiqrdv", b'I'),
    ])
    def test_initial_spreaders_placement(self, model_key, spreader_status):
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
        sim, town, _ = setup_simulation(model_key, town_params)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "out.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                log = h5file["individual_logs/log"][:]
                spreaders = [row for row in log if row['timestep']
                             == 0 and row['status'] == spreader_status]
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

    @pytest.mark.parametrize("model_key", ["seiqrdv"])
    def test_missing_required_place_type(self, model_key):
        # Use test data that does NOT contain 'healthcare_facility' in found_place_types
        metadata_path = "test/test_data/aachen_dom_500m_metadata.json"
        graphmlz_path = "test/test_data/aachen_dom_500m.graphmlz"
        town_params = scon.TownParameters(num_pop=10, num_init_spreader=1)
        town = scon.Town.from_files(metadata_path, graphmlz_path, town_params)
        model_params_class = MODEL_MATRIX[model_key][1]
        model_params = model_params_class(**MODEL_MATRIX[model_key][3])
        model = MODEL_MATRIX[model_key][0](model_params)
        # Should raise ValueError due to missing 'healthcare_facility'
        with pytest.raises(ValueError, match="Missing required place types"):
            scon.Simulation(town, model, timesteps=1)


class TestStepEventFunctionality:
    def test_step_event_invalid_parameters(self):
        # Test SEND_HOME with probability_func (should raise ValueError)
        with pytest.raises(ValueError, match="You cannot define a mobility probability function for an event that does not disperse people"):
            scon.StepEvent(
                "invalid_send_home",
                lambda folk: None,
                scon.EventType.SEND_HOME,
                probability_func=lambda x: 0.5
            )

        # Test non-callable probability_func (should raise ValueError)
        with pytest.raises(ValueError, match="probability_func must be a callable function"):
            scon.StepEvent(
                "invalid_prob_func",
                lambda folk: None,
                scon.EventType.DISPERSE,
                probability_func="not_a_function"
            )

        with pytest.raises(ValueError, match=r"Could not inspect probability_func signature: probability_func must have exactly 2 non-default arguments, got 1\. Expected signature: func\(distances, agent, \*\*kwargs\)"):
            scon.StepEvent(
                "invalid_prob_func_without_folk",
                lambda folk: None,
                scon.EventType.DISPERSE,
                probability_func=lambda x: 0.5
            )

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
        sim, town, _ = setup_simulation(
            model_key, town_params, step_events=step_events, timesteps=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "stepevent_test.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                log = h5file["individual_logs/log"][:]
                # Check 'go_to_work' event
                go_to_work_rows = log[(log['timestep'] == 1) & (
                    log['event'] == b"go_to_work")]
                for row in go_to_work_rows:
                    folk_id = row['folk_id']
                    address = row['address']
                    home_addr = next(
                        folk.home_address for folk in sim.folks if folk.id == folk_id)
                    place_type = town.town_graph.nodes[address]['place_type']
                    assert address == home_addr or place_type == 'workplace', \
                        f"AbstractFolk {folk_id} at address {address} (type {place_type}) is not at home or workplace during go_to_work"
                # Check 'end_day' event that automatically gets appended regardless of the StepEvents input from the user
                end_day_rows = log[(log['timestep'] == 1) &
                                   (log['event'] == b"end_day")]
                for row in end_day_rows:
                    folk_id = row['folk_id']
                    address = row['address']
                    home_addr = next(
                        folk.home_address for folk in sim.folks if folk.id == folk_id)
                    assert address == home_addr, f"AbstractFolk {folk_id} not at home at end_day (address {address}, home {home_addr})"

# For SEIQRDV, the functionality of priority place is tested in its own dedicated tests,
# since agents may prioritize 'healthcare_facility' and bypass typical destinations like 'workplace'.


class TestSimulationUpdate:
    @pytest.mark.parametrize("model_key", ["seir", "seisir", "seiqrdv"])
    def test_population_conservation(self, model_key):
        _, _, _, _, _, _ = MODEL_MATRIX[model_key]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        sim, _, _ = setup_simulation(model_key, town_params, timesteps=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_cons_test.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                for row in summary:
                    total = sum(row[name] for name in row.dtype.names if name not in (
                        "timestep", "current_event"))
                    assert total == 100, f"Population not conserved at timestep {row['timestep']}: got {total}, expected 100"

    def test_population_migration_and_death(self):
        # Only SEIQRDV truly updates population size after each day
        model_key = "seiqrdv"
        _, _, _, extra_params, _, _ = MODEL_MATRIX[model_key]
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        # Test migration (lam_cap=1, mu=0)
        params = dict(extra_params)
        params['lam_cap'] = 1
        params['mu'] = 0
        sim, town, _ = setup_simulation(
            model_key, town_params, timesteps=2, override_params=params)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_migration_test.h5")
            sim.run(hdf5_path=h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                step1 = summary[-2]
                step2 = summary[-1]
                total1 = sum(step1[name] for name in step1.dtype.names if name not in (
                    "timestep", "current_event", "D"))
                total2 = sum(step2[name] for name in step2.dtype.names if name not in (
                    "timestep", "current_event", "D"))
                assert total1 == 200, f"Population should be doubled at timestep {step1['timestep']}: got {total1}, expected 200"
                assert total2 == total1 * \
                    2, f"Population should be doubled at timestep {step2['timestep']}: got {total2}, expected {total1 * 2}"
        # Test death (lam_cap=0, mu=1)
        params['lam_cap'] = 0
        params['mu'] = 1
        sim, town, _ = setup_simulation(
            model_key, town_params, timesteps=1, override_params=params)
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
        ("seir", {"S": 89, "E": 3, "I": 3, "R": 5}),
        ("seisir", {"S": 0, "E": 0, "Is": 43, "Ir": 41, "R": 16}),
        ("seiqrdv", {"S": 0, "E": 0, "I": 0,
         "Q": 0, "R": 4, "D": 20, "V": 76}),
    ])
    def test_status_summary_last_step(self, model_key, expected_status):
        town_params = scon.TownParameters(num_pop=100, num_init_spreader=10)
        folk_class = MODEL_MATRIX[model_key][2]
        step_events = default_test_step_events(folk_class)
        sim, _, _ = setup_simulation(
            model_key, town_params, step_events=step_events, timesteps=50, seed=True, override_params=None)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "out.h5")
            sim.run(hdf5_path=h5_path)
            self.assert_h5_structure(h5_path)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                last_step = summary[-1]
                for status, expected_value in expected_status.items():
                    assert last_step[status] == expected_value, f"{status} mismatch: got {last_step[status]}, expected {expected_value}"
