import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

import simcronomicon as scon
model_params = scon.SEIRModelParameters(max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200)
def rhs_func(t, y):
    S, E, I, R = y
    N = S+ E+ I + R
    rhs = np.zeros(4)
    rhs[0] = -model_params.beta * S * I / N + 1/model_params.xi * R
    rhs[1] = model_params.beta * S * I / N - 1 / model_params.sigma * E
    rhs[2] = 1/model_params.sigma * E  - 1/model_params.gamma * I
    rhs[3] = 1/model_params.gamma * I - 1/model_params.xi * R
    return rhs

def infection_gone_event(t, y):
    # Event triggers when E + I < 1
    return y[1] + y[2] - 1

infection_gone_event.terminal = True
infection_gone_event.direction = -1

# Time span and initial condition
t_end = 100
t_span = (0, t_end)
y0 = [0.99, 0, 0.01, 0]

# Time points where the solution is computed
t_eval = np.linspace(0, t_end, t_end * 3)

# Solve the ODE
sol = solve_ivp(
    rhs_func,
    t_span,
    y0,
    method='RK45',
    t_eval=t_eval,
    events=infection_gone_event
)

# Plot the solution
plt.plot(sol.t, sol.y[0], label='S')
plt.plot(sol.t, sol.y[1], label='E')
plt.plot(sol.t, sol.y[2], label='I')
plt.plot(sol.t, sol.y[3], label='R')
plt.xlabel('t')
plt.ylabel('Density')
plt.title('Solution of ODE')
plt.grid()
plt.legend()
plt.show()