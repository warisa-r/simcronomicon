Advanced Step Events and Movement Patterns
==========================================

This tutorial covers how to create custom step events and design realistic movement patterns for your simulations. Step events control when, where, and how agents move and interact during each simulation day.

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
--------------------

**SEND_HOME Events**
  - All agents return directly to their home addresses
  - No distance limitations or place type filtering
  - Used for: end-of-day, emergency evacuations, curfews

**DISPERSE Events**
  - Agents move to locations within specified constraints
  - Enables agent interactions at destinations
  - Used for: work, shopping, social activities

Custom Movement Patterns
------------------------

The real power of step events comes from custom probability functions that model realistic human mobility.
We have 1 built-in function to simulate the movement of the agent for you.

Built-in Probability Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Log-normal mobility (models real human movement patterns)
   shopping_event = scon.StepEvent(
       name="shopping",
       folk_action=scon.FolkSEIR.interact,
       event_type=scon.EventType.DISPERSE,
       max_distance=8000,
       place_types=['commercial'],
       probability_func=scon.log_normal_probabilities
   )

Creating Custom Probability Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

But maybe you might want to use other types of function to define the probability of an agent going somewhere that is dependent with
the distances. You can define them yourselves!

Your probability function must:

1. Accept a list/array of distances (in meters)
2. Return probabilities between 0 and 1
3. Probabilities should sum to 1 (will be normalized automatically)

Here is an example of how you can define your own probability function:

.. code-block:: python

   def distance_preference(distances, preference="nearby"):
       """
       Custom probability function based on distance preference.
       
       Parameters
       ----------
       distances : array-like
           Distances to potential destinations in meters
       preference : str
           "nearby" for short distances, "far" for long distances
       """
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
       
       # Normalize to sum to 1
       return probs / np.sum(probs) if np.sum(probs) > 0 else probs

   # Use custom function
   exploration_event = scon.StepEvent(
       name="exploration",
       folk_action=scon.FolkSEIR.interact, 
       event_type=scon.EventType.DISPERSE,
       max_distance=20000,
       place_types=['commercial', 'religious', 'education'],
       probability_func=lambda dists: distance_preference(dists, "far")
   )

Complete Example: Daily Routine
-------------------------------

.. code-block:: python

   # Define a realistic daily schedule with varied movement patterns
   def create_daily_events():
       return [
           # Morning commute - moderate distance, work focus
           scon.StepEvent(
               "morning_commute",
               scon.FolkSEIR.interact,
               scon.EventType.DISPERSE,
               max_distance=20000,
               place_types=['workplace', 'education'],
               probability_func=scon.log_normal_probabilities
           ),
           
           # Lunch break - nearby commercial areas
           scon.StepEvent(
               "lunch_break", 
               scon.FolkSEIR.interact,
               scon.EventType.DISPERSE,
               max_distance=3000,
               place_types=['commercial'],
               probability_func=lambda d: distance_preference(d, "nearby")
           ),
           
           # Evening activities - varied distances and places
           scon.StepEvent(
               "evening_social",
               scon.FolkSEIR.interact,
               scon.EventType.DISPERSE, 
               max_distance=15000,
               place_types=['commercial', 'religious', 'entertainment'],
               probability_func=lambda d: distance_preference(d, "far")
           ),
           
       ]

   # Use in simulation
   step_events = create_daily_events()
   model = scon.SEIRModel(model_params, step_events)

Tips for Effective Step Events
-----------------------------

**Event Timing**
  - Order events logically (commute → work → lunch → home)
  - Consider realistic time constraints for each activity

**Distance Constraints**
  - Match `max_distance` to activity type (nearby shopping vs. long commutes)
  - Consider transportation modes in your model area

**Place Type Selection**
  - Be specific: `['workplace']` vs. `['commercial', 'workplace']`
  - Ensure your town has the required place types

**Probability Functions**
  - Test with sample distances before using in simulation
  - Consider how movement patterns affect disease spread
  - Balance realism with computational efficiency

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