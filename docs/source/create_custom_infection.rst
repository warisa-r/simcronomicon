Creating Custom Infection Models: Building an SIR Model
============================================================

This tutorial demonstrates how to create custom infection models in simcronomicon by implementing the classic 
**SIR (Susceptible-Infectious-Recovered)** model from scratch. You'll learn the essential components needed to 
build any infection model and understand the inheritance structure that makes simcronomicon extensible.

Understanding the SIR Model
---------------------------

The SIR model is the simplest epidemic model, dividing the population into three compartments:

**S - Susceptible**
   Healthy individuals who can become infected.

**I - Infectious** 
   Individuals who can transmit the disease to susceptible people.

**R - Recovered**
   Individuals who have recovered and gained immunity.

**Disease Flow**: S → I → R (unidirectional)

Why Build SIR When SEIR Exists?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While simcronomicon includes a more complex SEIR model, building SIR teaches you:

- **Model Architecture**: Understanding the inheritance hierarchy
- **Parameter Design**: How to define model-specific parameters  
- **Agent Behavior**: Implementing custom disease progression logic
- **Validation**: Ensuring your model works correctly

This knowledge enables you to create any infection model (SIRD, SEIQR, etc.) for your specific research needs.

Step 1: Define Model Parameters
-------------------------------

Every infection model needs a parameters class that inherits from ``AbstractModelParameters``:

.. code-block:: python

   # File: sir_model.py
   from simcronomicon.infection_models.abstract_model import AbstractModelParameters

   class SIRModelParameters(AbstractModelParameters):
       """
       Parameters for the SIR infection model.
       
       Parameters
       ----------
       max_energy : int
           Maximum daily energy for agents (affects movement patterns)
       beta : float
           Transmission rate - probability of infection per contact
       gamma : float
           Recovery rate - days until recovery from infectious status
       """
       
       def __init__(self, max_energy, beta, gamma):
           super().__init__(max_energy)
           
           # Validate parameters
           assert isinstance(beta, (int, float)) and 0 <= beta <= 1, \
               "beta must be a number between 0 and 1"
           assert isinstance(gamma, (int, float)) and gamma > 0, \
               "gamma must be a positive number"
           
           self.beta = beta
           self.gamma = gamma
       
       def to_config_dict(self):
           """Convert parameters to dictionary for saving/loading simulations."""
           return {
               'max_energy': self.max_energy,
               'beta': self.beta,
               'gamma': self.gamma,
               'model_type': 'SIR'
           }

**Key Design Principles:**

- **Validation**: Always validate parameter types and ranges
- **Documentation**: Clear docstrings explain each parameter's meaning
- **Metadata**: The ``to_config_dict()`` method enables simulation persistence

Step 2: Create the Agent Class  
------------------------------

The agent class defines how individuals behave and transition between disease states:

.. code-block:: python

   from simcronomicon.infection_models.abstract_model import AbstractFolk

   class FolkSIR(AbstractFolk):
       """
       SIR agent with disease-specific behaviors.
       
       Inherits all basic agent functionality from AbstractFolk and adds
       SIR-specific interaction and status transition logic.
       """
       
       def interact(self, folks_here, current_place_type, status_dict_t, model_params, dice):
           """
           Handle agent interactions at a location, including disease transmission.
           
           Parameters
           ----------
           folks_here : list of FolkSIR
               All agents at this location
           current_place_type : str
               Type of location (e.g., 'commercial', 'accommodation')
           status_dict_t : dict
               Current status counts for the simulation
           model_params : SIRModelParameters
               Model configuration parameters
           dice : float
               Random number between 0 and 1 for stochastic decisions
           """
           # Only susceptible agents can become infected
           if self.status == 'S':
               # Check if any infectious people are present
               num_contact = len(
                [folk for folk in folks_here if folk != self and folk.status in ['I']])
               
                # conversion_prob * I / N is the non-linear term that defines conversion
                # This inverse bernoulli function is an interpretation of the term
                # in agent-based modeling
                transmission_prob = self.inverse_bernoulli(
                       num_contact, conversion_prob / len(folks_here))
                
                # Attempt infection
                if transmission_prob > dice:
                       self.convert('I', status_dict_t)
           
           # Reduce energy from social interaction
           if self.energy > 0:
               self.energy -= 1

       def sleep(self, status_dict_t, model_params):
           """
           End-of-day processing: energy reset and disease progression.
           
           Parameters
           ----------
           status_dict_t : dict
               Current status counts for the simulation
           model_params : SIRModelParameters
               Model configuration parameters
           """
           # Call parent sleep method (resets energy, increments status_step_streak)
           super().sleep()
           
           # Handle disease progression based on time in status
           if self.status == 'I' and self.status_step_streak >= model_params.gamma:
               # Infectious agents recover after gamma days
               self.convert('R', status_dict_t)

**Key Agent Concepts:**

- **Interaction Logic**: Only susceptible agents can become infected
- **Inverse Bernoulli**: Handles multiple infectious contacts realistically  
- **Time-Based Transitions**: Status changes based on ``status_step_streak``
- **Energy Management**: Social interactions consume energy

Step 3: Implement the SIR Model
-------------------------------

Custom models need to override the ``initialize_sim_population`` method to handle their specific status assignments and initial conditions:

.. code-block:: python

   class SIRModel(AbstractInfectionModel):
       """SIR infection model implementation."""
       
       def __init__(self, model_params, step_events=None):
           # Define model-specific attributes BEFORE calling super().__init__
           self.infected_statuses = ['I']  # Only infectious status
           self.all_statuses = ['S', 'I', 'R']  # All possible statuses
           self.folk_class = FolkSIR  # Agent class to use
           self.step_events = step_events  # Custom or default events
           
           # Initialize parent class (validates our definitions)
           super().__init__(model_params)
       
       def initialize_sim_population(self, town):
           import random as rd
           
           # Get basic population parameters from parent
           num_pop, num_init_spreader, num_init_spreader_rd, folks, household_node_indices, assignments = super().initialize_sim_population(town)
           
           # Randomly assign initial spreaders (not on specified nodes)
           for i in range(num_init_spreader_rd):
               node = rd.choice(town.accommodation_node_ids)
               assignments.append((node, 'I'))  # Infectious status
           
           # Assign the rest as susceptible
           for i in range(num_pop - num_init_spreader):
               node = rd.choice(town.accommodation_node_ids)
               assignments.append((node, 'S'))  # Susceptible status
           
           # Assign initial spreaders to specified nodes (if any)
           for node in town.town_params.spreader_initial_nodes:
               assignments.append((node, 'I'))
           
           # Create folks and update graph/node info
           for i, (node, status) in enumerate(assignments):
               folk = self.create_folk(i, node, self.model_params.max_energy, status)
               folks.append(folk)
               town.town_graph.nodes[node]["folks"].append(folk)
               
               # Track household nodes (nodes with 2+ people)
               if len(town.town_graph.nodes[node]["folks"]) == 2:
                   household_node_indices.add(node)
           
           # Create initial status dictionary for timestep 0
           status_dict_t0 = {
               'current_event': None,
               'timestep': 0,
               'S': num_pop - num_init_spreader,  # Susceptible count
               'I': num_init_spreader,            # Infectious count  
               'R': 0                             # Recovered count (starts at 0)
           }
           
           return folks, household_node_indices, status_dict_t0

**Key Implementation Points:**

- **Call Parent Method**: Use ``super().initialize_sim_population(town)`` to get base setup
- **Status Assignment**: Assign initial statuses based on your model's compartments
- **Node Assignment**: Distribute agents across accommodation nodes in the town
- **Status Dictionary**: Initialize counts for all possible statuses at timestep 0
- **Household Tracking**: Update household indices for nodes with multiple residents

Step 4: Test Your SIR Model
---------------------------

Create a simple test script to validate your implementation:

.. code-block:: python

   # File: test_sir_model.py
   import simcronomicon as scon
   from sir_model import SIRModel, SIRModelParameters

   def test_sir_model():
       """Test basic SIR model functionality."""
       
       # Create a simple town
       point = (50.7753, 6.0839)  # Aachen coordinates
       town_params = TownParameters(100, 5)  # 100 people, 5 initial infected
       town = Town.from_point(point, 500, "test_sir", town_params)
       
       # Configure SIR model
       sir_params = SIRModelParameters(
           max_energy=5,
           beta=0.3,      # 30% transmission probability
           gamma=7        # Recovery after 7 days
       )
       
       # Create model and simulation
       sir_model = SIRModel(sir_params)
       simulation = Simulation(town, sir_model, timesteps=50)
       
       # Run simulation
       print("Running SIR simulation...")
       simulation.run()
       
       # Analyze results
       print("SIR simulation completed successfully!")
       
       # Visualize results
       plot_status_summary_from_hdf5("simulation_output.h5")
       
       return True

   if __name__ == "__main__":
       test_sir_model()

Step 5: Compare with Mathematical SIR
------------------------------------

Validate your agent-based model against the classic SIR differential equations:

.. code-block:: python

   import numpy as np
   from scipy.integrate import solve_ivp
   import matplotlib.pyplot as plt

   def compare_sir_models(sir_params, population_size=100):
       """Compare agent-based SIR with ODE solution."""
       
       # ODE system for SIR
       def sir_ode(t, y):
           S, I, R = y
           N = S + I + R
           dS_dt = -sir_params.beta * S * I / N
           dI_dt = sir_params.beta * S * I / N - I / sir_params.gamma
           dR_dt = I / sir_params.gamma
           return [dS_dt, dI_dt, dR_dt]
       
       # Initial conditions (normalized)
       S0 = 0.95  # 95% susceptible
       I0 = 0.05  # 5% infectious
       R0 = 0.00  # 0% recovered
       
       # Solve ODE
       t_span = (0, 50)
       t_eval = np.arange(0, 51)
       solution = solve_ivp(sir_ode, t_span, [S0, I0, R0], t_eval=t_eval)
       
       # Plot comparison
       plt.figure(figsize=(12, 5))
       
       # ODE solution
       plt.subplot(1, 2, 1)
       plt.plot(solution.t, solution.y[0], 'b-', label='Susceptible')
       plt.plot(solution.t, solution.y[1], 'r-', label='Infectious') 
       plt.plot(solution.t, solution.y[2], 'g-', label='Recovered')
       plt.xlabel('Time (days)')
       plt.ylabel('Proportion')
       plt.title('SIR ODE Model')
       plt.legend()
       plt.grid(True)
       
       # Agent-based results (load from your simulation)
       plt.subplot(1, 2, 2)
       # Add code to plot your simulation results here
       plt.title('Agent-Based SIR Model')
       
       plt.tight_layout()
       plt.show()
       
       print("📊 Model comparison complete!")
       print(f"   Beta (transmission rate): {sir_params.beta}")
       print(f"   Gamma (recovery time): {sir_params.gamma} days")
       print(f"   Basic reproduction number R₀: {sir_params.beta * sir_params.gamma:.2f}")

Advanced Features
-----------------

Once your basic SIR model works, you can extend it with advanced features:

Custom Movement Patterns
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Add custom step events for different behaviors
   sir_step_events = [
       StepEvent(
           "morning_commute",
           FolkSIR.interact,
           EventType.DISPERSE,
           10000,  # Travel up to 10km
           ['workplace', 'education'],
           log_normal_mobility  # Distance-based probability
       ),
       StepEvent(
           "evening_social",
           FolkSIR.interact,
           EventType.DISPERSE,
           5000,
           ['commercial', 'religious']
       )
   ]
   
   sir_model = SIRModel(sir_params, step_events=sir_step_events)

Behavioral Interventions
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class FolkSIRWithMasks(FolkSIR):
       """SIR agents with mask-wearing behavior."""
       
       def __init__(self, *args, **kwargs):
           super().__init__(*args, **kwargs)
           self.wearing_mask = False
           self.mask_effectiveness = 0.5  # 50% transmission reduction
       
       def interact(self, folks_here, current_place_type, status_dict_t, model_params, dice):
           # Modify transmission probability based on mask wearing
           if self.status == 'S':
               num_contact = len(
                [folk for folk in folks_here if folk != self and folk.status in ['I']])
               
                # conversion_prob * I / N is the non-linear term that defines conversion
                # This inverse bernoulli function is an interpretation of the term
                # in agent-based modeling
                base_prob = self.inverse_bernoulli(
                       num_contact, conversion_prob / len(folks_here))
                   
                # Reduce transmission if either person wears a mask
                if self.wearing_mask or any(folk.wearing_mask for folk in infectious_folks):
                   base_prob *= (1 - self.mask_effectiveness)
                   
                if base_prob > dice:
                   self.convert('I', status_dict_t)
           
           if self.energy > 0:
               self.energy -= 1

Validation and Testing
----------------------

Always validate your custom model:

**Unit Tests**
   Test individual components (parameter validation, agent transitions)

**Integration Tests** 
   Verify the complete model runs without errors

**Mathematical Validation**
   Compare with known analytical solutions when possible

**Sensitivity Analysis**
   Test how parameter changes affect outcomes

**Edge Cases**
   Test extreme parameter values and unusual scenarios

.. code-block:: python

   def validate_sir_model():
       """Comprehensive SIR model validation."""
       
       # Test 1: Parameter validation
       try:
           SIRModelParameters(max_energy=5, beta=1.5, gamma=7)  # Should fail
           assert False, "Should have caught invalid beta"
       except AssertionError:
           print("Parameter validation working")
       
       # Test 2: Status transitions
       agent = FolkSIR(id=1, home_address=0, max_energy=5, status='S')
       status_dict = {'S': 100, 'I': 0, 'R': 0}
       
       agent.convert('I', status_dict)
       assert agent.status == 'I' and agent.status_step_streak == 0
       print("Status transitions working")
       
       # Test 3: Disease progression
       params = SIRModelParameters(max_energy=5, beta=0.3, gamma=3)
       agent.status_step_streak = 3  # At recovery threshold
       agent.sleep(status_dict, params)
       
       if agent.status_step_streak >= params.gamma:
           agent.convert('R', status_dict)
       assert agent.status == 'R'
       print("Disease progression working")
       
       print("All validation tests passed!")

Best Practices
--------------

When creating custom infection models:

**1. Start Simple**
   Begin with basic functionality, then add complexity incrementally

**2. Validate Early**
   Test each component before building the complete model

**3. Document Everything**
   Clear docstrings and comments make models maintainable

**4. Follow Conventions**
   Use consistent naming and structure with existing simcronomicon models

**5. Test Thoroughly**
   Validate against mathematical models when possible

**6. Consider Performance**
   Profile your model with large populations to identify bottlenecks

Common Pitfalls
---------------

**Incorrect Inheritance Order**
   Always define model attributes BEFORE calling ``super().__init__()``

**Missing Status Validation**
   Ensure ``all_statuses`` includes every possible agent status

**Energy Management**
   Don't forget to decrement energy during interactions

**Status Transition Logic**
   Use ``status_step_streak`` correctly for time-based transitions

**Parameter Validation**
   Always validate parameter ranges and types

Next Steps
----------

Now that you can create custom infection models, explore:

- **SIRD Model**: Add death compartment to your SIR model
- **Age-Structured Models**: Different parameters for age groups
- **Spatial Models**: Location-dependent transmission rates
- **Multi-Strain Models**: Competing variants with different characteristics
- **Economic Models**: Incorporate economic factors and interventions

The simcronomicon framework makes it straightforward to implement any infection model structure. 
Your SIR implementation provides the foundation for understanding how to build increasingly sophisticated epidemic 
models tailored to your specific research questions.