import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

import simcronomicon as scon

model_params = scon.SEIsIrRModelParameters(
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


t_end = 20  # Number of steps before termination for the simulation of the default seed
t_span = (0, t_end)
# 10 spreader, 690 Steady ignorant, 300 Radical ignorant
# The ODE is adapted from the original paper due to lack of information regarding average degree of the homogeneous networks
# , therefore, some coefficients have been dropped
# This results in a system that is no longer based on density
# We have to use this scaling instead to get a sensible result
# (yield similar result and trends to the literature numerical result)
y0 = [0.1, 0, 6.9, 3.0, 0]
t_eval = np.arange(0, t_end + 1)

sol = solve_ivp(
    rhs_func,
    t_span,
    y0,
    method='RK45',
    t_eval=t_eval
)

# Plot the solution
plt.plot(sol.t, sol.y[0], label='S')
plt.plot(sol.t, sol.y[1], label='E')
plt.plot(sol.t, sol.y[2], label='Is')
plt.plot(sol.t, sol.y[3], label='Ir')
plt.plot(sol.t, sol.y[4], label='R')
plt.xlabel('t')
plt.ylabel('Density')
plt.title('Solution of ODE')
plt.grid()
plt.legend()
plt.show()
