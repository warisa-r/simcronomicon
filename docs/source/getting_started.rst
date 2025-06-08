Getting Started with simcronomicon
==================================

Welcome to **simcronomicon**! This guide will help you get started with the main features of the package, including building a town, defining disease spread models, running simulations, and visualizing results.

Installation
------------

Install simcronomicon and its dependencies by cloning the repository and install locally:

.. code-block:: bash

   git clone https://github.com/yourusername/simcronomicon.git
   cd simcronomicon
   pip install -e .

Basic Workflow
--------------

1. **Create or load a town network**
2. **Define step events and a compartmental model**
3. **Run a simulation**
4. **Visualize the results**

---

Building or Loading a Town
--------------------------

You can create a town from OpenStreetMap data or load a pre-built town from files.

**Load from files:**

.. code-block:: python

   import simcronomicon as scon

   town_params = scon.TownParameters(num_pop=1000, num_init_spreader=10)
   town_graph_path = "../test/test_data/aachen_dom_500m.graphmlz"
   town_metadata_path = "../test/test_data/aachen_dom_500m_metadata.json"
   town = scon.Town.from_files(
       metadata_path=town_metadata_path,
       town_graph_path=town_graph_path,
       town_params=town_params
   )

**Create from a geographic point:**

.. code-block:: python

   town = scon.Town.from_point(
       point=[50.7753, 6.0839],  # Aachen Dom
       dist=1000,
       town_params=town_params,
       file_prefix="aachen_dom",
       save_dir="./data"
   )

---

Visualizing the Town
--------------------

By calling the function `visualize_place_types_from_graphml`, you can see the classification of `place_types` of the location you are interested in.
It is very important to note that unclassified nodes or the grey nodes that are tagged `other` will not be processed in the simulation.

.. code-block:: python

   scon.visualize_place_types_from_graphml(town_graph_path, town_metadata_path)

---

Defining Step Events and a Model
--------------------------------

Step events control agent movement and interactions. You can use defaults or define your own.
Here, we define such that people in our simulation always go out and greet their neighbors and go to work
afterwards. In these event steps, if the agents have enough energy, they will go to the destined location with our specified `place_types`.

.. code-block:: python

   step_events = [
       scon.StepEvent(
           "greet_neighbors",
           scon.FolkSEIR.interact,
           scon.EventType.DISPERSE,
           5000,
           ['accommodation']),
       scon.StepEvent(
           "chore",
           scon.FolkSEIR.interact,
           scon.EventType.DISPERSE,
           19000,
           [
               'commercial',
               'workplace',
               'education',
               'religious'
           ],
           scon.log_normal_probabilities
       )
   ]

Then,  they will `interact` with their environments and other agents in the same
location node. These interactions are what trigger the spread!

Here is the codeblock of the interaction function in `FolkSEIR` for you to see that an agent can contract a disease
exactly through attending these events. (And their energy also decreases!)

.. code-block:: python

    def interact(
                self,
                folks_here,
                current_place_type,
                status_dict_t,
                model_params,
                dice):
            # When a susceptible person comes into contact with an infectious person,
            # they have a likelihood to become exposed to the disease
            if self.status == 'S' and self.inverse_bernoulli(
                    folks_here, model_params.beta, ['I']) > dice:
                self.convert('E', status_dict_t)

            self.energy -= 1

After these events are done, all the agents will go to sleep. This is the end of 1 simulation time step.
Note that some status transitions that are time-sensitive are triggered when `sleep` is activated.
Here is how the sleep function looks like for SEIR model so that you can see that an agent will transition
from being 'E' or exposed to 'I' or infectious if an amount of incubation time has passed.

.. code-block:: python
    def sleep(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        super().sleep()
        if self.status == 'E' and self.status_step_streak == model_params.sigma:
            self.convert('I', status_dict_t)

After defining what an agent will go through in each day, you have to also define the way the disease "work".
This is through defining proper model parameters. Here, `beta` governs how contagious the disease is,
`sigma` is the incubation period, and `gamma` is the time one needs to recover from being infectious to immune.

.. code-block:: python

   model_params = scon.SEIRModelParameters(
       max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200)
   model = scon.SEIRModel(model_params, step_events)

---

Running a Simulation
--------------------

This step is pretty straightforward. After the town, model, and all their parameters have been defined, we run the simulation
with the desired maximum time steps. Note that the simulation always terminates automatically when there exists no more spread carrier
in it anymore.

.. code-block:: python

   sim = scon.Simulation(town, model, 100)
   sim.run()

After the simulation finish running, an output file `simulation_output.h5` will be generated in the following structure:

.. code-block:: text

            simulation_output.h5
            ├── metadata
            │   ├── simulation_metadata   (JSON-encoded simulation metadata)
            │   └── town_metadata         (JSON-encoded town metadata)
            ├── status_summary
            │   └── summary               (dataset: structured array with timestep, current_event, and statuses)
            └── individual_logs
                └── log                   (dataset: structured array with timestep, event, folk_id, status, address)

Visualizing Simulation Results
-----------------------------

For visualization, we provide 2 functions to see how your spread develops.

1. Plot the compartment status summary:

.. code-block:: python

   scon.plot_status_summary_from_hdf5("simulation_output.h5")

2. Visualize agent locations on the map:

.. code-block:: python

   scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)

---

Comparing with ODE Solution (SEIR Example)
------------------------------------------

You can compare your simulation to a standard ODE solution:

.. code-block:: python

   import numpy as np
   from scipy.integrate import solve_ivp
   import matplotlib.pyplot as plt

   def rhs_func(t, y):
       S, E, I, R = y
       N = S + E + I + R
       rhs = np.zeros(4)
       rhs[0] = -model_params.beta * S * I / N + 1/model_params.xi * R
       rhs[1] = model_params.beta * S * I / N - 1 / model_params.sigma * E
       rhs[2] = 1/model_params.sigma * E - 1/model_params.gamma * I
       rhs[3] = 1/model_params.gamma * I - 1/model_params.xi * R
       return rhs

   t_end = 82
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

---

Next Steps
----------

- Explore other models: SEIQRDV, SEIsIrR, or define your own by subclassing `AbstractCompartmentalModel`.
- Customize step events for your scenario.
- See the API documentation for advanced usage.

For more details, see the full documentation and examples in the `examples/` folder.