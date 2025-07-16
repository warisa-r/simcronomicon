simcronomicon documentation
===========================

Welcome to simcronomicon!
=========================

Welcome to the documentation of simcronomicon, an agent-based network modelling with OpenStreetMap data.

What is agent-based modeling?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Agent-based modelling is a stochastic model to simulate interactions between agents and the environment from basic interaction rules.
A normal agent-based modelling begins with programming the way an agent behaves. For example, you might want any agent in the simulation
who lives in Aachen to go to the university everyday and interact with 2 other agents who are at the same place as them randomly.
If one of the agents are infectious, the other agents interacted with them have a likelihood of becoming infectious too.

This can be easily progammed and controlled! But to facilitate multiple agents and keeping track of the way agents move, interact,
become infectious and recover is not an easy task. That's why `simcronomicon` is here!
 
We recommend you to start with reading `Getting Started`. The next tutorial in `Understanding Agent Behavior and Simulation Flow`
will help you in understanding how agents behave and how the software processes the simulation.

Then, in order to understand the agent's movement in the simulation better
and to customize it, proceed with `Advanced Step Events and Movement Patterns`. 
After understanding the basic blocks of the simulation,
you should read `Advanced Simulation Features: SEIQRDV Model`, to understand all the features in our agent-based network software.

.. toctree::
   :maxdepth: 1
   :caption: Contents:
   
   getting_started
   basic_blocks
   advanced_features_movement
   advanced_features_SEIQRDV
   create_custom_infection
   simcronomicon