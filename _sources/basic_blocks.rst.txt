Understanding Agent Behavior and Simulation Flow
================================================

This section explains the fundamental building blocks of how individual agents work and how multiple agents interact in the simulation environment. Understanding these core concepts will help you grasp the advanced features covered in later tutorials.
We will go through the code in the library so that you can understand better how this library works!
But if you are not planning to write a custom model of your own, it might not be necessary to go through this section!

The Agent (Folk) Architecture
-----------------------------

Individual Agent Attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every agent in simcronomicon has several key attributes that govern their behavior:

.. code-block:: python

   # Example of a basic agent
   agent = FolkSEIR(
       id=42,                    # Unique identifier
       home_address=156,         # Node ID of their home
       max_energy=5,            # Maximum daily energy
       status='S'               # Disease status (S, E, I, R, etc.)
   )
   
   # Key behavioral attributes:
   print(f"Current energy: {agent.energy}")              # 0-5 (random daily start)
   print(f"Current location: {agent.address}")           # Current node ID
   print(f"Days in status: {agent.status_step_streak}")  # Time tracking
   print(f"Movement restricted: {agent.movement_restricted}")  # Quarantine flag

**Energy System**: The Foundation of Movement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most important concept is the **energy system**. Each agent has:

- **max_energy**: Maximum energy points (e.g., 5)
- **energy**: Current energy (randomly reset each morning between 0 and max_energy)

Energy determines movement capability and action capability of an agent. If an agent has 0 energy,
they cannot move or participate in any interaction with other agents.

This creates realistic daily patterns where:
- Some agents are more active (higher starting energy)
- Agents become less active as the day progresses
- Energy resets each night during sleep

Daily Agent Lifecycle
---------------------

Each simulation day follows this pattern for every agent:

Morning: Energy Reset
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def sleep(self):
       self.status_step_streak += 1  # Track time in current status
       self.energy = random.randint(0, self.max_energy)  # Reset energy

Day: Event Participation
~~~~~~~~~~~~~~~~~~~~~~~~

For each step event in the day:

1. **Movement Decision**: Can the agent move?

.. code-block:: python

   if agent.movement_restricted == False and agent.alive and agent.energy > 0:
       # Agent can participate in this event
       # ...

2. **Location Selection**: Where does the agent go?

.. code-block:: python

   # Find valid destinations within travel distance
   candidates = [node for node in town_graph.nodes 
                 if distance_to_node <= event.max_distance 
                 and node.place_type in event.place_types]
   
   # Move to chosen location
   agent.address = chosen_location

3. **Interaction**: What happens at the location? The simplest answer is, the agent has a likelihood of getting infected!
This is govern by very simple block of if else condition and a touch of randomness:

.. code-block:: python

   def interact(self, folks_here, current_place_type, status_dict_t, model_params, dice):
       # Disease transmission logic
       if self.status == 'S' and any(folk.status == 'I' for folk in folks_here):
           if transmission_probability > dice:
               self.convert('E', status_dict_t)  # Become exposed
       
       self.energy -= 1  # Lose energy from interaction

**Mathematical Foundation: Inverse Bernoulli Probability**

The inverse Bernoulli function bridges the gap between continuous ODE dynamics and discrete agent interactions:

.. code-block:: python

   def inverse_bernoulli(self, folks_here, conversion_prob, infectious_statuses):
       num_infectious = len([folk for folk in folks_here 
                            if folk != self and folk.status in infectious_statuses])
       
       # Key formula: P(infection) = 1 - (1 - β/N)^k
       contact_prob = conversion_prob / len(folks_here)  # β/N
       return 1 - (1 - contact_prob) ** num_infectious  # 1 - (1 - β/N)^k

**Why This Formula Works:**

- **β/N**: Base transmission probability scaled by location density
- **k**: Number of infectious people present (multiple exposure opportunities)  
- **1 - (1 - β/N)^k**: Probability of at least one successful transmission

**Real-World Examples:**

.. code-block:: python

   # Scenario 1: Small household (β=0.4)
   # 1 infectious person, 5 total people
   P = 1 - (1 - 0.4/5)^1 = 0.08 (8% infection risk)
   
   # Scenario 2: Crowded restaurant  
   # 3 infectious people, 30 total people
   P = 1 - (1 - 0.4/30)^3 = 0.039 (3.9% infection risk)
   
   # Scenario 3: Large event
   # 10 infectious people, 100 total people  
   P = 1 - (1 - 0.4/100)^10 = 0.039 (3.9% infection risk)

**Key Insights:**

- **Location matters**: Smaller venues (higher β/N) create higher per-contact risk
- **Multiple contacts**: More infectious people increases overall risk non-linearly
- **Crowd dilution**: Larger crowds can actually reduce individual infection risk
- **ODE compatibility**: As population grows, results converge to traditional SEIR equations

This mathematical foundation ensures that our agent-based results align with classical epidemiological 
theory while capturing the spatial heterogeneity that makes simcronomicon powerful for policy analysis.

Evening: Status Transitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most important concept for disease progression is **status_step_streak** - this tracks how many days an agent has been in their current status:

.. code-block:: python

   def sleep(self, ...):
       super().sleep()  # Reset energy and increment status streak
       
       # Time-based disease progression using status_step_streak
       if self.status == 'E' and self.status_step_streak == model_params.sigma:
           self.convert('I', status_dict_t)  # Exposed → Infectious after incubation period
       elif self.status == 'I' and self.status_step_streak == model_params.gamma:
           self.convert('R', status_dict_t)  # Infectious → Recovered after infectious period

**Example Disease Progression Timeline:**

.. code-block:: python

   # Day 1: Agent becomes exposed
   agent.status = 'E'
   agent.status_step_streak = 0
   
   # Day 2-3: Still incubating (sigma = 3 days)
   agent.status_step_streak = 1, then 2
   
   # Day 4: Becomes infectious 
   if agent.status_step_streak == 3:  # sigma = 3
       agent.convert('I', status_dict_t) # Convert and reset counter for new status
   
   # Day 5-11: Infectious period (gamma = 7 days)
   agent.status_step_streak = 1, 2, 3, 4, 5, 6
   
   # Day 12: Recovers
   if agent.status_step_streak == 7:  # gamma = 7
       agent.convert('R', status_dict_t) # Convert and reset counter for new status

**Key Points:**
- `status_step_streak` increments every night during `sleep()`
- When it reaches the model parameter threshold, status changes occur
- The counter resets to 0 when an agent changes status
- Different statuses have different duration parameters (sigma, gamma, etc.)

This creates predictable disease timelines: exposed agents become infectious after exactly `sigma` days, 
and infectious agents recover after exactly `gamma` days, mimicking real epidemiological patterns.

Simulation Orchestra: How Multiple Agents Coordinate
----------------------------------------------------

The main simulation loop in ``sim.py`` coordinates thousands of agents:

Step 1: Reset Locations
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Clear all locations
   for node in town_graph.nodes:
       node["folks"] = []  # Empty all locations

Step 2: Agent Movement (DISPERSE Events)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def _disperse_for_event(self, step_event):
       for person in self.folks:
           if person.movement_restricted == False and person.alive and person.energy > 0:
               # Find valid destinations
               candidates = [node for node in reachable_nodes 
                           if node.place_type in step_event.place_types]
               
               # Choose destination (uniform random or custom probability function)
               if step_event.probability_func:
                   distances = [distance_to_node for node in candidates]
                   probs = step_event.probability_func(distances, person)
                   new_location = np.random.choice(candidates, p=probs)
               else:
                   new_location = random.choice(candidates)
               
               # Move agent
               person.address = new_location
           
           # Add agent to their chosen location
           town_graph.nodes[person.address]["folks"].append(person)

Step 3: Interactions at Each Location
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Process each active location
   for node in active_locations:
       folks_here = town_graph.nodes[node]["folks"]
       place_type = town_graph.nodes[node]["place_type"]
       
       # Each agent interacts with environment and others
       for agent in folks_here:
           if agent.alive and agent.energy > 0:
               agent.interact(folks_here, place_type, status_dict, model_params, random.random())

Step 4: Return Home (SEND_HOME Events)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # End of day: everyone goes home
   for agent in self.folks:
       agent.address = agent.home_address
       agent.sleep(...)  # Reset energy, handle status transitions

Key Simulation Concepts
-----------------------

**Energy-Driven Participation**
   Only agents with energy > 0 can move and interact. This creates natural activity patterns and prevents unrealistic behavior.

**Location-Based Interactions**
   Agents only interact with others at the same location node. Disease spreads through shared physical spaces.

**Time-Dependent Transitions**
   Status changes happen during ``sleep()`` based on how long an agent has been in their current status.

**Movement Restrictions**
   Quarantined agents (``movement_restricted = True``) stay home but can still interact with visiting agents (delivery, family).

**Stochastic Behavior**
   Random elements (energy levels, movement choices, disease transmission) create realistic population-level patterns from simple rules.

Understanding Movement Patterns
-------------------------------

The basic movement system uses uniform random selection:

.. code-block:: python

   # Basic movement: choose randomly among valid destinations
   valid_destinations = [node for node in town if meets_criteria(node)]
   chosen_destination = random.choice(valid_destinations)

But you can customize this with probability functions of your own, which is the topic of the next tutorial!

Next Steps
----------

Now that you understand how individual agents work and how the simulation coordinates multiple agents, you're ready to explore:

- **Advanced Step Events and Movement Patterns**: Customize agent movement with sophisticated probability functions
- **SEIQRDV Model Features**: Understand complex disease models with vaccination (priority place system) and quarantine
- **Custom Model Development**: Create your own compartmental models and agent behaviors

The key insight is that complex population-level patterns emerge from simple agent-level rules. By understanding energy, 
movement, interactions, and status transitions, you can design realistic epidemic simulations and analyze intervention strategies.