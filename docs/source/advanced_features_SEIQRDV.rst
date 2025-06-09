Advanced Simulation Features: SEIQRDV Model
===========================================

This tutorial covers the advanced features that are used by our most advanced model `SEIQRDV_model`, 
including agent priority behaviors, population dynamics, and the vaccination queueing system. 
These features make the SEIQRDV model particularly suitable for modeling complex epidemic scenarios with healthcare interventions.

Overview of SEIQRDV Model
-------------------------

The SEIQRDV model extends the basic SEIR framework with:

- **Quarantine (Q)**: Symptomatic agents movement restriction
- **Death (D)**: Disease-related mortality
- **Vaccination (V)**: Protective immunity through vaccination

Key advanced features:

1. **Priority Place System**: Agents can prioritize visiting specific place types
2. **Non-Conservative Population**: Birth/migration and natural death dynamics
3. **Vaccination Queueing**: Realistic healthcare capacity constraints

Setting Up the Model
--------------------

Like what we did with SEIR model before, we start with setting up the town and our simulation initial condition.
Then we define the model parameters.

.. code-block:: python

   import simcronomicon as scon

   # Load a town with healthcare facilities
   town_params = scon.TownParameters(2000, 10)
   town = scon.Town.from_files(
       metadata_path="town_metadata.json",
       town_graph_path="town_graph.graphmlz",
       town_params=town_params
   )

   # SEIQRDV model with vaccination and population dynamics
   model_params = scon.SEIQRDVModelParameters(
       max_energy=5,
       lam_cap=0.01,      # 1% population growth rate
       beta=0.4,          # Transmission probability
       alpha=0.1,         # Vaccination desire rate
       gamma=4,           # Incubation period
       delta=5,           # Days until quarantine
       lam=7,             # Recovery time in quarantine
       rho=7,             # Time to death in quarantine
       kappa=0.2,         # Disease mortality rate
       mu=0.001,          # Natural death rate
       hospital_capacity=50  # Vaccines per event per facility
   )

Priority Place System
---------------------

The priority place system allows agents to seek out specific types of locations based on their needs.

How It Works
~~~~~~~~~~~~

When an agent wants to get vaccinated:

.. code-block:: python

    # In the sleep() method, susceptible agents may decide to seek vaccination
    if self.status == 'S' and model_params.alpha > dice:
        self.want_vaccine = True

    if self.want_vaccine:
            self.priority_place_type.append('healthcare_facility')

**Key Features:**

- **Dynamic Priority**: Agents add place types to their priority list based on needs
- **Movement Influence**: The movement system preferentially moves agents to priority places
- **Multiple Priorities**: Agents can have multiple place types in their priority list
- **Most Convenient Movement**: Agents will move to the priority place type that is closest to them

Activation of Priority Place in the Simulation Flow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is how priority place feature is implemented in `sim.py`.

.. code-block:: python

    # If the agent has prioritized place types to go to
    # Find the closest node with one of those place types,
    # regardless of max_distance
    min_dist = float('inf')
    chosen_node = None
    chosen_place_type = None
    for node in self.town.town_graph.nodes:
        node_place_type = self.town.town_graph.nodes[node]['place_type']
        if node_place_type in person.priority_place_type:
            if self.town.town_graph.has_edge(person.address, node):
                dist = self.town.town_graph[person.address][node]['weight']
            else:
                continue
            if dist < min_dist:
                min_dist = dist
                chosen_node = node
                chosen_place_type = node_place_type


After they are located at the place they prioritized to go, that place will no longer be their priority.
In this model, even if the place is full and the agent cannot get vaccinated, they will no longer have
`healthcare_facility` as their priority place of the day anymore and will leave the healthcare facilities to do other things
and return to get vaccine later if they still want the vaccine.

Vaccination Queueing Mechanism
------------------------------

The vaccination system implements realistic capacity constraints at healthcare facilities.
In the method `interact` of the class `FolkSEIQRDV`, the vaccination mechanism is implemented:

Queue Processing
~~~~~~~~~~~~~~~~

.. code-block:: python

   # In the interact() method at healthcare facilities
   if current_place_type == 'healthcare_facility':
       want_vaccine_list = [folk for folk in folks_here if folk.want_vaccine]
       if self in want_vaccine_list and self.status == 'S':
           idx = want_vaccine_list.index(self)
           if idx < model_params.hospital_capacity:
               self.convert('V', status_dict_t)

**How the Queue Works:**

1. **Gather Agents**: All agents wanting vaccines at the facility are collected
2. **First-Come-First-Served**: Agents are processed in order of arrival
3. **Capacity Limit**: Only up to `hospital_capacity` agents are vaccinated per event
4. **Status Check**: Only susceptible agents can receive effective vaccination

**Important Queue Behavior:**

- **Deferred Reset**: `want_vaccine` is reset to `False` in `sleep()`, not immediately after vaccination, to maintain queue integrity during the event
- **Cross-Event Persistence**: Agents maintain their vaccination desire across multiple days until successfully vaccinated or get confirmed infectious


Non-Conservative Population Dynamics
------------------------------------

Unlike basic epidemic models, SEIQRDV includes population changes through births, migration, and natural deaths.

Natural Deaths
~~~~~~~~~~~~~~

.. code-block:: python

   # In update_population() - natural mortality
   folks_alive = [folk for folk in folks if folk.alive]
   for folk in folks_alive:
       if rd.random() < model_params.mu:
           folk.convert('D', status_dict_t)
           folk.alive = False

Population Growth
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # In update_population() - births and migration
   num_current_folks = len([f for f in folks if f.alive])
   num_possible_new_folks = num_current_folks * model_params.lam_cap
   
   if num_possible_new_folks > 1:
       num_possible_new_folks = round(num_possible_new_folks)
       for i in range(num_possible_new_folks):
           node = rd.choice(town.accommodation_node_ids)
           # New agents can start in any status except Dead or Quarantine
           status = rd.choice([s for s in all_statuses if s not in ('D', 'Q')])
           folk = create_folk(new_id, node, max_energy, status)
           folks.append(folk)

**Population Parameters:**

- **mu (μ)**: Natural death rate (probability per agent per day)
- **lam_cap (λ)**: Birth/migration rate (fraction of population per day)

Example: Population Dynamics Simulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Simulate population changes over time
   step_events = [
       scon.StepEvent(
           "daily_life",
           scon.FolkSEIQRDV.interact,
           scon.EventType.DISPERSE,
           10000,
           ['commercial', 'workplace', 'education', 'healthcare_facility']
       )
   ]

   model_params = scon.SEIQRDVModelParameters(
       max_energy=3,
       lam_cap=0.02,    # 2% growth rate
       beta=0.3,
       alpha=0.15,      # 15% seek vaccination
       gamma=4, delta=5, lam=7, rho=7,
       kappa=0.1,       # 10% disease mortality
       mu=0.005,        # 0.5% natural mortality
       hospital_capacity=30
   )

   model = scon.SEIQRDVModel(model_params, step_events)
   sim = scon.Simulation(town, model, 200)
   sim.run()

Putting It All Together: Complete Example
-----------------------------------------

Here's a complete simulation showcasing all advanced SEIQRDV features:

.. code-block:: python

   import simcronomicon as scon
   import matplotlib.pyplot as plt

   # Setup town and model
   town_params = scon.TownParameters(1500, 5)
   town = scon.Town.from_files(
       metadata_path="town_metadata.json",
       town_graph_path="town_graph.graphmlz", 
       town_params=town_params
   )

   # Complex step events including healthcare visits
   step_events = [
       scon.StepEvent(
           "morning_routine",
           scon.FolkSEIQRDV.interact,
           scon.EventType.DISPERSE,
           6000,
           ['accommodation']
       ),
       scon.StepEvent(
           "daily_activities", 
           scon.FolkSEIQRDV.interact,
           scon.EventType.DISPERSE,
           18000,
           ['commercial', 'workplace', 'education', 'healthcare_facility'],
           scon.log_normal_mobility
       )
   ]

   # Model with realistic parameters
   model_params = scon.SEIQRDVModelParameters(
       max_energy=4,
       lam_cap=0.015,        # 1.5% population growth
       beta=0.35,            # Moderate transmission
       alpha=0.2,            # 20% vaccination seeking
       gamma=4, delta=6, lam=8, rho=8,
       kappa=0.15,           # 15% disease mortality  
       mu=0.002,             # 0.2% natural mortality
       hospital_capacity=40   # Realistic vaccine capacity
   )

   # Run simulation
   model = scon.SEIQRDVModel(model_params, step_events)
   sim = scon.Simulation(town, model, 365)  # One year simulation
   sim.run()

   # Analyze results
   scon.plot_status_summary_from_hdf5("simulation_output.h5")
   scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)

Key Takeaways
-------------

1. **Priority Places**: Enable realistic agent behavior where needs drive movement patterns
2. **Vaccination Queues**: Model healthcare capacity constraints and fair distribution
3. **Population Dynamics**: Capture long-term demographic changes alongside epidemic spread
4. **Integrated System**: All features work together to create realistic epidemic scenarios

These advanced features make the SEIQRDV model particularly powerful for:

- **Policy Analysis**: Testing vaccination strategies under capacity constraints
- **Long-term Studies**: Understanding epidemic evolution with population changes  
- **Healthcare Planning**: Optimizing facility placement and capacity
- **Behavioral Modeling**: Capturing how individual needs affect disease spread

Next Steps
----------

- Experiment with different `alpha` values to see vaccination seeking behavior
- Try varying `hospital_capacity` to model different healthcare scenarios
- Combine with custom step events for specialized vaccination campaigns
- Use the population dynamics to study endemic disease patterns

For more advanced scenarios, see the API documentation for customizing agent behaviors and creating specialized step events.