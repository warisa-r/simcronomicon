import numpy as np
import simcronomicon as scon
from scipy.integrate import solve_ivp
import tempfile
import os
import pytest
from ..test_helper import default_test_step_events
from simcronomicon import Town, TownParameters, Simulation
from simcronomicon.infection_models import StepEvent, EventType
from simcronomicon.infection_models.SEIsIrR_model import SEIsIrRModel, SEIsIrRModelParameters, FolkSEIsIrR


class TestSEIsIrRModel:
    def test_invalid_seisir_model_parameters(self):
        # gamma not a float or int
        with pytest.raises(TypeError, match="gamma must be a float or int"):
            SEIsIrRModelParameters(
                max_energy=4, literacy=0.7, gamma="bad", alpha=0.5, lam=0.5, phi=0.5, theta=0.7, mu=0.62, eta1=0.1, eta2=0.1
            )

        # alpha out of range
        with pytest.raises(TypeError, match="alpha must be a float or int"):
            SEIsIrRModelParameters(
                max_energy=4, literacy=0.7, gamma=0.9, alpha="bad", lam=0.5, phi=0.5, theta=0.7, mu=0.62, eta1=0.1, eta2=0.1
            )

        # lam negative
        with pytest.raises(TypeError, match="lam must be a float or int"):
            SEIsIrRModelParameters(
                max_energy=4, literacy=0.7, gamma=0.9, alpha=0.5, lam="bad", phi=0.5, theta=0.7, mu=0.62, eta1=0.1, eta2=0.1
            )

        # mem_span not int > 1
        with pytest.raises(TypeError, match="mem_span must be an integer greater or equal to 1, got 1.03"):
            SEIsIrRModelParameters(
                max_energy=4, literacy=0.7, gamma=0.9, alpha=0.5, lam=0.5, phi=0.5, theta=0.7, mu=0.62, eta1=0.1, eta2=0.1, mem_span=1.03
            )

    def test_SEIsIrR_abm_vs_ode_error(self):
        # ODE solution
        model_params = SEIsIrRModelParameters(
            4, 0.7, 0.9, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)

        def rhs_func(t, y):
            S, E, Is, Ir, R = y
            rhs = np.zeros(5)

            rhs[0] = (
                S * (model_params.mu * Is + Ir) * model_params.gamma *
                model_params.alpha * model_params.lam
                + S * E * model_params.E2S
                - S * (R + S + E) * model_params.S2R
                - S * model_params.forget
            )
            rhs[1] = (
                Is * S * model_params.gamma *
                (1 - model_params.gamma) * model_params.alpha * model_params.lam
                - S * E * model_params.E2S - R * E * model_params.E2R
            )

            rhs[2] = (
                -Is * S * (model_params.gamma * model_params.alpha * model_params.lam * model_params.mu +
                           model_params.gamma * (1-model_params.gamma) * model_params.alpha * model_params.lam)
            )
            rhs[3] = -Ir * S * model_params.gamma * \
                model_params.alpha * model_params.lam
            rhs[4] = S * (R + S + E) * model_params.S2R + S * \
                model_params.forget + R * E * model_params.E2R
            return rhs

        t_end = 12  # Number of steps before termination for the simulation of the default seed
        t_span = (0, t_end)
        # 10 spreader, 690 Steady ignorant, 300 Radical ignorant
        # The ODE is adapted from the original paper due to lack of information regarding average degree of the homogeneous networks
        # , therefore, some coefficients have been dropped
        # This results in a system that is no longer based on density
        # We have to use this scaling instead to get a sensible result
        # (yield similar result and trends to the reference literature numerical result)
        y0 = [0.1, 0, 6.9, 3.0, 0]
        t_eval = np.arange(0, t_end + 1)

        sol = solve_ivp(
            rhs_func,
            t_span,
            y0,
            method='RK45',
            t_eval=t_eval
        )

        # Perform ABM simulation
        total_pop = 2000
        town_params = TownParameters(total_pop, 20)
        town_graph_path = "test/test_data/aachen_dom_500m.graphmlz"
        town_config_path = "test/test_data/aachen_dom_500m_config.json"
        town = Town.from_files(
            config_path=town_config_path,
            town_graph_path=town_graph_path,
            town_params=town_params
        )
        model = SEIsIrRModel(
            model_params, default_test_step_events(FolkSEIsIrR))
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
                abm_Is = summary['Is'] / total_pop
                abm_Ir = summary['Ir'] / total_pop
                abm_R = summary['R'] / total_pop

            # Normalize, align and compare
            ode_S = sol.y[0] / 10
            ode_E = sol.y[1] / 10
            ode_Is = sol.y[2] / 10
            ode_Ir = sol.y[3] / 10
            ode_R = sol.y[4] / 10

            # Compute average per time step 2-norm error for each compartment over all time points
            err_S = np.linalg.norm(abm_S - ode_S) / t_end
            err_E = np.linalg.norm(abm_E - ode_E) / t_end
            err_Is = np.linalg.norm(abm_Is - ode_Is) / t_end
            err_Ir = np.linalg.norm(abm_Ir - ode_Ir) / t_end
            err_R = np.linalg.norm(abm_R - ode_R) / t_end

            assert err_S < 0.05, f"Spreader compartment error too high: {err_S:.4f}"
            assert err_E < 0.05, f"Exposed compartment error too high: {err_E:.4f}"
            assert err_Is < 0.05, f"Steady ignorant compartment error too high: {err_Is:.4f}"
            assert err_Ir < 0.05, f"Radical ignorant compartment error too high: {err_Is:.4f}"
            assert err_R < 0.05, f"Stifler compartment error too high: {err_R:.4f}"
