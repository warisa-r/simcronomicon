import numpy as np
from scipy.integrate import solve_ivp
import tempfile
import os
import pytest
from ..test_helper import default_test_step_events

from simcronomicon import Town, TownParameters, Simulation
from simcronomicon.infection_models import StepEvent, EventType
from simcronomicon.infection_models.SEIR_model import SEIRModel, SEIRModelParameters, FolkSEIR


class TestSEIRModel:
    def test_invalid_seir_model_parameters(self):
        # beta out of range
        with pytest.raises(TypeError, match="beta must be a float between 0 and 1 \\(exclusive\\)!"):
            SEIRModelParameters(
                max_energy=5, beta=1.2, sigma=6, gamma=5, xi=200
            )

        # beta negative
        with pytest.raises(TypeError, match="beta must be a float between 0 and 1 \\(exclusive\\)!"):
            SEIRModelParameters(
                max_energy=5, beta=-0.1, sigma=6, gamma=5, xi=200
            )

        # sigma not positive integer
        with pytest.raises(TypeError, match="sigma must be a positive integer since it is a value that described duration, got 0"):
            SEIRModelParameters(
                max_energy=5, beta=0.4, sigma=0, gamma=5, xi=200
            )

        # gamma not positive integer
        with pytest.raises(TypeError, match="gamma must be a positive integer since it is a value that described duration, got -2"):
            SEIRModelParameters(
                max_energy=5, beta=0.4, sigma=6, gamma=-2, xi=200
            )

        # xi not positive integer
        with pytest.raises(TypeError, match="xi must be a positive integer since it is a value that described duration, got 0"):
            SEIRModelParameters(
                max_energy=5, beta=0.4, sigma=6, gamma=5, xi=0
            )

    def test_seir_abm_vs_ode_error(self):
        # ODE solution
        model_params = SEIRModelParameters(
            max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200)

        def rhs_func(t, y):
            S, E, I, R = y
            N = S + E + I + R
            rhs = np.zeros(4)
            rhs[0] = -model_params.beta * S * I / N + 1/model_params.xi * R
            rhs[1] = model_params.beta * S * I / N - 1 / model_params.sigma * E
            rhs[2] = 1/model_params.sigma * E - 1/model_params.gamma * I
            rhs[3] = 1/model_params.gamma * I - 1/model_params.xi * R
            return rhs

        t_end = 70  # Number of steps before termination for the simulation of the default seed
        t_span = (0, t_end)
        y0 = [0.99, 0, 0.01, 0]  # 1000 pop, 10 infected, 990 susceptible
        t_eval = np.arange(0, t_end + 1)

        sol = solve_ivp(
            rhs_func,
            t_span,
            y0,
            method='RK45',
            t_eval=t_eval
        )

        # Perform ABM simulation
        total_pop = 1000
        town_params = TownParameters(total_pop, 10)
        town_graph_path = "test/test_data/aachen_dom_500m.graphmlz"
        town_config_path = "test/test_data/aachen_dom_500m_config.json"
        town = Town.from_files(
            config_path=town_config_path,
            town_graph_path=town_graph_path,
            town_params=town_params
        )
        model = SEIRModel(
            model_params, default_test_step_events(FolkSEIR))
        sim = Simulation(town, model, t_end)
        with tempfile.TemporaryDirectory() as tmpdir:
            h5_path = os.path.join(tmpdir, "abm_vs_ode_test.h5")
            sim.run(hdf5_path=h5_path, silent=True)

            # Extract ABM results
            import h5py
            with h5py.File(h5_path, "r") as h5file:
                summary = h5file["status_summary/summary"][:]
                abm_S = summary['S'] / total_pop
                abm_E = summary['E'] / total_pop
                abm_I = summary['I'] / total_pop
                abm_R = summary['R'] / total_pop

            # Align and compare
            ode_S = sol.y[0]
            ode_E = sol.y[1]
            ode_I = sol.y[2]
            ode_R = sol.y[3]

            # Compute average per time step 2-norm error for each compartment over all time points
            err_S = np.linalg.norm(abm_S - ode_S) / t_end
            err_E = np.linalg.norm(abm_E - ode_E) / t_end
            err_I = np.linalg.norm(abm_I - ode_I) / t_end
            err_R = np.linalg.norm(abm_R - ode_R) / t_end

            assert err_S < 0.05, f"Susceptible compartment error too high: {err_S:.4f}"
            assert err_E < 0.05, f"Exposed compartment error too high: {err_E:.4f}"
            assert err_I < 0.05, f"Infectious compartment error too high: {err_I:.4f}"
            assert err_R < 0.05, f"Recovered compartment error too high: {err_R:.4f}"
