import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

import simcronomicon as scon

# The incoming population rate must be devided by four and added as influx to every RHS that isnt immobile
model_params = scon.SEIQRDVModelParameters(
    max_energy=2, lam_cap=0.01, beta=0.7, alpha=0.1, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0.002, hospital_capacity=100)

def rhs_func(t, y):
    S, E, I, Q, R, D, V = y
    N = S + E + I + Q + R + V
    rhs = np.zeros(7)

    rhs[0] = model_params.lam_cap / 5 * N + model_params.beta * S * I / N - model_params.alpha * S - model_params.mu * S 
    rhs[1] = model_params.lam_cap / 5 * N + model_params.beta * S * I / N - 1/model_params.gamma * E - model_params.mu * E
    rhs[2] = model_params.lam_cap / 5 * N + 1/model_params.gamma * E - 1/model_params.delta * I - model_params.mu * I
    rhs[3] = 1 / model_params.delta * I - (1-model_params.kappa)/ model_params.lam * Q - model_params.kappa / model_params.rho * Q - model_params.mu * Q
    rhs[4] = model_params.lam_cap / 5 * N + (1-model_params.kappa)/ model_params.lam * Q - model_params.mu * R
    rhs[5] = model_params.kappa / model_params.rho * Q
    rhs[6] = model_params.lam_cap / 5 * N + model_params.alpha * S - model_params.mu * V
    return rhs

t_end = 100  # Number of steps before termination for the simulation of the default seed
t_span = (0, t_end)
y0 = [2000, 0, 20, 0, 0, 0, 0]
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
plt.plot(sol.t, sol.y[2], label='I')
plt.plot(sol.t, sol.y[3], label='Q')
plt.plot(sol.t, sol.y[4], label='R')
plt.plot(sol.t, sol.y[5], label='D')
plt.plot(sol.t, sol.y[6], label='V')
plt.xlabel('t')
plt.ylabel('Density')
plt.title('Solution of ODE')
plt.grid()
plt.legend()
plt.show()
