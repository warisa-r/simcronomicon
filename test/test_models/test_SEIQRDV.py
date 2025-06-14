import numpy as np
import simcronomicon as scon
import h5py
from scipy.integrate import solve_ivp
import tempfile
import os
import pytest
from ..test_helper import default_test_step_events


class TestSEIQRDVModel:
    @classmethod
    def setup_class(cls):
        cls.town_graph_path = "test/test_data/uniklinik_500m.graphmlz"
        cls.town_config_path = "test/test_data/uniklinik_500m_config.json"

    def test_invalid_seiqrdv_model_parameters(self):
        # lam_cap out of range
        with pytest.raises(TypeError, match="lam_cap must be a float between 0 and 1!"):
            scon.SEIQRDVModelParameters(
                max_energy=10, lam_cap=1.5, beta=0.1, alpha=0.1, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0.01
            )

        # beta negative
        with pytest.raises(TypeError, match="beta must be a float between 0 and 1!"):
            scon.SEIQRDVModelParameters(
                max_energy=10, lam_cap=0.1, beta=-0.1, alpha=0.1, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0.01
            )

        # gamma not positive integer
        with pytest.raises(TypeError, match="gamma must be a positive integer, got -4"):
            scon.SEIQRDVModelParameters(
                max_energy=10, lam_cap=0.1, beta=0.1, alpha=0.1, gamma=-4, delta=5, lam=7, rho=7, kappa=0.2, mu=0.01
            )

        # hospital_capacity not int or inf
        with pytest.raises(TypeError, match="hospital_capacity must be a positive integer or a value of infinity"):
            scon.SEIQRDVModelParameters(
                max_energy=10, lam_cap=0.1, beta=0.1, alpha=0.1, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0.01, hospital_capacity="a lot"
            )

    def test_seiqrdv_abm_vs_ode_error(self):
        # ODE solution
        model_params = scon.SEIQRDVModelParameters(
            max_energy=2, lam_cap=0.01, beta=0.7, alpha=0.1, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0.002, hospital_capacity=float('Inf')
        )

        def rhs_func(t, y):
            S, E, I, Q, R, D, V = y
            N = S + E + I + Q + R + V
            rhs = np.zeros(7)
            rhs[0] = model_params.lam_cap / 5 * N + model_params.beta * \
                S * I / N - model_params.alpha * S - model_params.mu * S
            rhs[1] = model_params.lam_cap / 5 * N + model_params.beta * \
                S * I / N - 1/model_params.gamma * E - model_params.mu * E
            rhs[2] = model_params.lam_cap / 5 * N + 1/model_params.gamma * \
                E - 1/model_params.delta * I - model_params.mu * I
            rhs[3] = 1 / model_params.delta * I - (1-model_params.kappa) / model_params.lam * \
                Q - model_params.kappa / model_params.rho * Q - model_params.mu * Q
            rhs[4] = model_params.lam_cap / 5 * N + \
                (1-model_params.kappa) / \
                model_params.lam * Q - model_params.mu * R
            rhs[5] = model_params.kappa / model_params.rho * Q
            rhs[6] = model_params.lam_cap / 5 * N + \
                model_params.alpha * S - model_params.mu * V
            return rhs

        t_end = 100
        t_span = (0, t_end)
        y0 = [1980, 0, 20, 0, 0, 0, 0]
        t_eval = np.arange(0, t_end + 1)

        sol = solve_ivp(
            rhs_func,
            t_span,
            y0,
            method='RK45',
            t_eval=t_eval
        )

        # Perform ABM simulation
        town_params = scon.TownParameters(num_pop=2000, num_init_spreader=20)
        town = scon.Town.from_files(
            config_path=self.town_config_path,
            town_graph_path=self.town_graph_path,
            town_params=town_params
        )

        model = scon.SEIQRDVModel(
            model_params, default_test_step_events(scon.FolkSEIQRDV))
        sim = scon.Simulation(town, model, t_end)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "abm_vs_ode_test_seiqrdv.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            # Extract ABM results
            import h5py
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                abm_S = summary['S']
                abm_E = summary['E']
                abm_I = summary['I']
                abm_Q = summary['Q']
                abm_R = summary['R']
                abm_D = summary['D']
                abm_V = summary['V']
                abm_total = abm_S + abm_E + abm_I + abm_Q + abm_R + abm_D + abm_V

            # Normalize ODE results for comparison
            ode_S = sol.y[0]
            ode_E = sol.y[1]
            ode_I = sol.y[2]
            ode_Q = sol.y[3]
            ode_R = sol.y[4]
            ode_D = sol.y[5]
            ode_V = sol.y[6]
            ode_total = ode_S + ode_E + ode_I + ode_Q + ode_R + ode_V

            # Normalize both to initial total population for fair comparison
            abm_S = abm_S / abm_total
            abm_E = abm_E / abm_total
            abm_I = abm_I / abm_total
            abm_Q = abm_Q / abm_total
            abm_R = abm_R / abm_total
            abm_D = abm_D / abm_total
            abm_V = abm_V / abm_total

            ode_S = ode_S / ode_total
            ode_E = ode_E / ode_total
            ode_I = ode_I / ode_total
            ode_Q = ode_Q / ode_total
            ode_R = ode_R / ode_total
            ode_D = ode_D / ode_total
            ode_V = ode_V / ode_total

            # Compute average per time step 2-norm error for each compartment over all time points
            err_S = np.linalg.norm(abm_S - ode_S) / t_end
            err_E = np.linalg.norm(abm_E - ode_E) / t_end
            err_I = np.linalg.norm(abm_I - ode_I) / t_end
            err_Q = np.linalg.norm(abm_Q - ode_Q) / t_end
            err_R = np.linalg.norm(abm_R - ode_R) / t_end
            err_D = np.linalg.norm(abm_D - ode_D) / t_end
            err_V = np.linalg.norm(abm_V - ode_V) / t_end

            assert err_S < 0.03, f"Susceptible compartment error too high: {err_S:.4f}"
            assert err_E < 0.03, f"Exposed compartment error too high: {err_E:.4f}"
            assert err_I < 0.03, f"Infectious compartment error too high: {err_I:.4f}"
            assert err_Q < 0.03, f"Quarantined compartment error too high: {err_Q:.4f}"
            assert err_R < 0.03, f"Recovered compartment error too high: {err_R:.4f}"
            assert err_D < 0.03, f"Dead compartment error too high: {err_D:.4f}"
            assert err_V < 0.03, f"Vaccinated compartment error too high: {err_V:.4f}"

    def test_vaccination(self):
        model_params = scon.SEIQRDVModelParameters(
            max_energy=10, lam_cap=0, beta=0, alpha=1.0, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0, hospital_capacity=float('Inf')
        )

        town_params = scon.TownParameters(num_pop=10, num_init_spreader=1)
        town = scon.Town.from_files(
            config_path=self.town_config_path,
            town_graph_path=self.town_graph_path,
            town_params=town_params
        )

        step_event = scon.StepEvent("chore", scon.FolkSEIQRDV.interact, scon.EventType.DISPERSE, 19000,
                                    ['commercial', 'workplace', 'education', 'religious'])

        model = scon.SEIQRDVModel(
            model_params, step_event)
        sim = scon.Simulation(town, model, 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_vaccination_test.h5")
            sim.run(hdf5_path=h5_path, silent=True)
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                last_step = summary[-1]
                # Since everyone wants vaccines and the hospitle capacity is infinite, they should all get it
                vaccinated_last = last_step["V"]
                assert vaccinated_last == 9, f"Every former susceptible person should be vaccinated at timestep {last_step['timestep']}: got {vaccinated_last}, expected 9"

        model_params = scon.SEIQRDVModelParameters(
            max_energy=10, lam_cap=0, beta=0, alpha=1.0, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0, hospital_capacity=5
        )

        town_params = scon.TownParameters(num_pop=21, num_init_spreader=1)
        town = scon.Town.from_files(
            config_path=self.town_config_path,
            town_graph_path=self.town_graph_path,
            town_params=town_params
        )

        model = scon.SEIQRDVModel(
            model_params, step_event)
        sim = scon.Simulation(town, model, 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "pop_vaccination_cap_test.h5")
            sim.run(hdf5_path=h5_path, silent=True)
            with h5py.File(h5_path, "r") as h5file:
                log = h5file["individual_logs/log"][:]
                # Filter for the first step event where current_event is "greet_neighbors" and timestep == 1
                first_step = log[(log['timestep'] == 1) & (
                    log['event'] == b"chore")]
                # Count number of people at each healthcare node of interest
                node_counts = {node: 0 for node in [26, 32, 40, 53]}
                for row in first_step:
                    # Only susceptible people can want vaccines. In this case there is no transmission
                    # so there will be no unaware infected person who wants vaccination
                    if row['address'] in node_counts and row['status'] != b'I':
                        node_counts[row['address']] += 1
                expected = {26: 3, 32: 1, 40: 10, 53: 4}
                print("Actual node counts at timestep 2, chore:", node_counts)
                for node, count in node_counts.items():
                    assert count == expected[node], f"Node {node} has {count} people, expected {expected[node]}"

                summary = h5file["status_summary/summary"][:]
                next_step = summary[-1]
                # There are 4 healthcare_facility type nodes in the graph
                # In this test case, they got allocated 3, 1, 5, 10
                # Therefore the amount of vaccination they should get is 3 + 1 + 5 + 4 = 13
                vaccinated_last = next_step["V"]
                assert vaccinated_last == 13, f"Every former susceptible person should be vaccinated at timestep {next_step['timestep']}: got {vaccinated_last}, expected 14"

    def test_quarantine_and_dead_address_stable(self):
        # All agents start as spreaders, delta=1 so all go to quarantine after 1 day, no deaths or births
        model_params = scon.SEIQRDVModelParameters(
            max_energy=10, lam_cap=0, beta=0, alpha=0, gamma=4, delta=1, lam=7, rho=2, kappa=1, mu=0, hospital_capacity=5
        )
        town_params = scon.TownParameters(num_pop=10, num_init_spreader=10)
        town = scon.Town.from_files(
            config_path=self.town_config_path,
            town_graph_path=self.town_graph_path,
            town_params=town_params
        )
        model = scon.SEIQRDVModel(
            model_params, default_test_step_events(scon.FolkSEIQRDV))
        sim = scon.Simulation(town, model, 10)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "quarantine_address_stable.h5")
            sim.run(hdf5_path=h5_path, silent=True)
            with h5py.File(h5_path, "r") as h5file:
                log = h5file["individual_logs/log"][:]
                # For each folk, track the address when they first become Q or D
                first_q_address = {}
                first_d_address = {}
                for row in log:
                    folk_id = row['folk_id']
                    timestep = row['timestep']
                    status = row['status']
                    address = row['address']
                    if status == b'Q':
                        if folk_id not in first_q_address:
                            first_q_address[folk_id] = address
                        else:
                            assert address == first_q_address[folk_id], (
                                f"AbstractFolk {folk_id} changed address after quarantine at timestep {timestep}!"
                            )
                    if status == b'D':
                        if folk_id not in first_d_address:
                            first_d_address[folk_id] = address
                        else:
                            assert address == first_d_address[folk_id], (
                                f"AbstractFolk {folk_id} changed address after death at timestep {timestep}!"
                            )
