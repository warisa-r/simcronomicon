Advanced Step Events and Movement Patterns
==========================================

This tutorial covers how to create custom step events and design realistic movement patterns for your simulations. Step events control when, where, and how agents move and interact during each simulation day.

**We recommend that along with reading this, 
you should look at the tutorial `disease_spread_mobility.ipynb`` to see how StepEvent looks like in action**

Understanding Step Events
-------------------------

Step events are the building blocks of agent behavior in simcronomicon. They define:

- **When** agents perform activities (event sequence)
- **Where** agents go (place types and distances)  
- **How** agents choose destinations (probability functions)
- **What** agents do when they arrive (interaction functions)

Basic Step Event Creation
-------------------------

.. code-block:: python

   import simcronomicon as scon

   # Simple end-of-day event (SEND_HOME)
   # This event exists by default at the end of step_events list without your input.
   sleep_event = scon.StepEvent(
       name="end_day",
       folk_action=scon.FolkSEIR.sleep
   )

   # Basic movement event (DISPERSE)
   work_event = scon.StepEvent(
       name="work_commute",
       folk_action=scon.FolkSEIR.interact,
       event_type=scon.EventType.DISPERSE,
       max_distance=15000,  # 15km max travel
       place_types=['workplace']
   )

Important: Automatic End-of-Day Event
-------------------------------------

**You never need to manually add a sleep/end-of-day event to your step events list.**

The simcronomicon framework automatically appends an "end_day" event to your step events sequence. This event:

- Calls the `sleep()` method for all agents
- Sends all agents back to their home addresses
- Resets agent energy for the next day
- Handles end-of-day status transitions

.. code-block:: python

   # DON'T do this - the end_day event is added automatically!
   step_events = [
       scon.StepEvent("work", scon.FolkSEIR.interact, ...),
       scon.StepEvent("shopping", scon.FolkSEIR.interact, ...),
       # scon.StepEvent("end_day", scon.FolkSEIR.sleep)  # ← NOT NEEDED!
   ]

   # DO this - just define your activity events
   step_events = [
       scon.StepEvent("work", scon.FolkSEIR.interact, ...),
       scon.StepEvent("shopping", scon.FolkSEIR.interact, ...)
       # End-of-day automatically added by the model
   ]

This automatic behavior ensures that:

- Agents always return home at day's end
- Energy is properly reset for the next simulation day
- You can focus on defining meaningful daily activities
- The simulation maintains proper day/night cycles

Event Types Explained
---------------------

**SEND_HOME Events**
  - All agents return directly to their home addresses
  - No distance limitations or place type filtering
  - Used for: end-of-day, emergency evacuations, curfews

**DISPERSE Events**
  - Agents move to locations within specified constraints
  - Enables agent interactions at destinations
  - Used for: work, shopping, social activities

Built-in Probability Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We have 2 built-in functions to simulate agent movement patterns:

**Log-Normal Mobility**
Models realistic human travel patterns based on research literature. Best for:
- Work commutes and regular activities
- Shopping and errands  
- Healthcare visits
- Any activity with preferred typical distances

.. code-block:: python

   # Log-normal mobility with intuitive parameters
   shopping_event = scon.StepEvent(
       name="shopping",
       folk_action=scon.FolkSEIR.interact,
       event_type=scon.EventType.DISPERSE,
       max_distance=8000,
       place_types=['commercial'],
       probability_func=lambda distances, agent: scon.log_normal_mobility(
           distances, agent, median_distance=2000, sigma=1.2)
   )

**Energy-Dependent Exponential Mobility**
Models agent movement based on current energy levels. Best for:
- Social activities after work
- Leisure activities  
- Any energy-dependent behavior

.. code-block:: python

   # Energy-dependent mobility with distance scaling
   social_event = scon.StepEvent(
       name="evening_social",
       folk_action=scon.FolkSEIR.interact,
       event_type=scon.EventType.DISPERSE,
       max_distance=15000,
       place_types=['commercial', 'entertainment'],
       probability_func=lambda distances, agent: scon.energy_exponential_mobility(
           distances, agent, distance_scale=2000)
   )

**Parameter Guidelines:**

*Log-Normal Mobility:*
- `median_distance`: 400m (local), 1100m (neighborhood), 3000m (city-wide), 8000m (regional)
- `sigma`: 0.8 (consistent), 1.0 (moderate), 1.5 (variable)

*Energy Exponential Mobility:*
- `distance_scale`: 200 (very local), 1000 (moderate), 3000 (wide range)

Creating Custom Probability Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

But maybe you might want to use other types of function to define the probability of an agent going somewhere that is dependent with
the distances. You can define them yourselves!

Your probability function must:

1. Accept exactly 2 non-default arguments: `(distances, agent)`
2. Return probabilities between 0 and 1  
3. Probabilities should sum to 1. This means you must normalize the probabilities!
4. Handle numpy arrays for distances
5. Be robust to edge cases (empty arrays, zero distances)

Here is an example of how you can define your own simple probability function:

.. code-block:: python

    def distance_preference_mobility(distances, agent, preference="nearby"):
        import numpy as np
        distances = np.array(distances)
        
        if preference == "nearby":
            # Exponential decay - prefer closer locations
            probs = np.exp(-distances / 2000)  # 2km characteristic distance
        elif preference == "far":
            # Prefer moderate to far distances
            probs = distances / np.max(distances) if len(distances) > 1 else [1.0]
        else:
            # Uniform - all distances equally likely
            probs = np.ones_like(distances)

   # Use custom function
   exploration_event = scon.StepEvent(
       name="exploration",
       folk_action=scon.FolkSEIR.interact, 
       event_type=scon.EventType.DISPERSE,
       max_distance=20000,
       place_types=['commercial', 'religious', 'education'],
       probability_func=lambda dists: distance_preference(dists, "far")
   )

Agent-Dependent Probability Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The power of the 2-parameter system is enabling agent-specific behavior. For example, if you have an SEIR model,
you can make assumption about agent's mobility dependence with their status:

.. code-block:: python

   def status_based_mobility(distances, agent):
       """
       Movement patterns that depend on agent health status.
       """
       import numpy as np
       distances = np.array(distances)
       
       # Quarantined agents cannot move (handled elsewhere)
       # Sick agents prefer shorter distances
       if hasattr(agent, 'status'):
           if agent.status == 'I':  # Infectious - stay closer to home
               probs = np.exp(-distances / 1000)  # 1km characteristic distance
           elif agent.status == 'R':  # Recovered - normal mobility
               probs = np.exp(-distances / 3000)  # 3km characteristic distance
           else:  # Susceptible - slightly more adventurous
               probs = np.exp(-distances / 4000)  # 4km characteristic distance
       else:
           # Default behavior for other statuses
           probs = np.exp(-distances / 2000)
       
       return probs / probs.sum() if probs.sum() > 0 else np.ones_like(probs) / len(probs)


Complete Example: Daily Routine
-------------------------------

.. code-block:: python

   # Define a realistic daily schedule with varied movement patterns
   def create_daily_events():
       return [
           # Morning commute - log-normal for realistic work travel
           scon.StepEvent(
               "morning_commute",
               scon.FolkSEIR.interact,
               scon.EventType.DISPERSE,
               max_distance=20000,
               place_types=['workplace', 'education'],
               probability_func=lambda distances, agent: scon.log_normal_mobility(
                   distances, agent, median_distance=5000, sigma=1.0)
           ),
           
           # Lunch break - energy-dependent for tired workers
           scon.StepEvent(
               "lunch_break", 
               scon.FolkSEIR.interact,
               scon.EventType.DISPERSE,
               max_distance=3000,
               place_types=['commercial'],
               probability_func=lambda distances, agent: scon.energy_exponential_mobility(
                   distances, agent, distance_scale=800)
           ),
           
           # Evening activities - custom preference function
           scon.StepEvent(
               "evening_social",
               scon.FolkSEIR.interact,
               scon.EventType.DISPERSE, 
               max_distance=15000,
               place_types=['commercial', 'religious', 'entertainment'],
               probability_func=lambda distances, agent: distance_preference_mobility(
                   distances, agent, "far")
           ),
       ]

   # Use in simulation
   step_events = create_daily_events()
   model = scon.SEIRModel(model_params, step_events)

Tips for Effective Step Events
------------------------------

**Event Timing**
  - Order events logically (commute → work → lunch → home)
  - Consider realistic time constraints for each activity

**Distance Constraints**
  - Match `max_distance` to activity type (nearby shopping vs. long commutes)
  - Consider transportation modes in your model area

**Place Type Selection**
  - Be specific: `['workplace']` vs. `['commercial', 'workplace']`
  - Ensure your town has the required place types

**Probability Function Parameters**
  - **Log-normal median_distance**: Set to typical travel distance for the activity
  - **Log-normal sigma**: Lower for consistent behavior, higher for varied patterns
  - **Energy exponential distance_scale**: Lower for local activities, higher for wide-range movement
  - Test with sample distances before using in simulation

**Parameter Testing Example**

.. code-block:: python

   # Test your probability functions with sample data
   import numpy as np
   
   class TestAgent:
       def __init__(self, energy=5, max_energy=10):
           self.energy = energy
           self.max_energy = max_energy
   
   test_distances = np.array([100, 500, 1000, 2000, 5000])
   test_agent = TestAgent()
   
   # Test log-normal mobility
   log_probs = scon.log_normal_mobility(test_distances, test_agent, 
                                       median_distance=1500, sigma=1.0)
   print(f"Log-normal probabilities: {log_probs}")
   
   # Test energy exponential mobility  
   energy_probs = scon.energy_exponential_mobility(test_distances, test_agent,
                                                  distance_scale=1000)
   print(f"Energy exponential probabilities: {energy_probs}")

Debugging Step Events
---------------------

.. code-block:: python

   # Test your probability function
   test_distances = [100, 500, 1000, 5000, 10000]
   test_probs = distance_preference(test_distances, "nearby")
   print(f"Distances: {test_distances}")
   print(f"Probabilities: {test_probs}")
   print(f"Sum: {sum(test_probs)}")  # Should be close to 1.0

   # Validate step events before simulation
   events = create_daily_events()
   for event in events:
       print(f"Event: {event.name}")
       print(f"  Type: {event.event_type}")
       print(f"  Max distance: {event.max_distance}m")
       print(f"  Place types: {event.place_types}")

Next Steps
----------

- Experiment with different probability functions for the same activity
- Create event sequences that reflect real-world daily patterns
- Combine step events with advanced model features (vaccination, quarantine)
- Consider seasonal or policy-driven changes to movement patterns

For more complex scenarios, see the SEIQRDV advanced features tutorial and the full API documentation.