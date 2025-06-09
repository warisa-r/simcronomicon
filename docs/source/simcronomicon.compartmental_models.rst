simcronomicon.compartmental_models package
==========================================

Core Building Blocks
--------------------

The most important building blocks for defining compartmental models in simcronomicon are the **abstract model classes** and the **step event system**.

- **Abstract Models**  
  The `abstract_model` module provides the abstract base classes that define the required structure and interface for all compartmental models. Every specific model (such as SEIR, SEIQRDV, etc.) is built on top of these abstract classes, specifying their own rules for agent status transitions and model-specific logic. If you want to create a new model, you will subclass these abstract classes and implement your own conversion rules and behaviors.

- **Step Events**  
  The `step_event` module defines the event system that controls agent activities and movement during each simulation step. Step events are a key user input to each model: you can use the default events provided in the abstract model, or define your own custom events. The sequence and logic of step events dictate how agents move, interact, and progress through the simulation.

Together, these modules form the foundation for all other compartmental models in simcronomicon. Understanding and extending them is essential for advanced model customization.

Submodules
----------

simcronomicon.compartmental_models.abstract_model module
--------------------------------------------------------

.. automodule:: simcronomicon.compartmental_models.abstract_model
   :members:
   :show-inheritance:
   :undoc-members:

simcronomicon.compartmental_models.step_event module
----------------------------------------------------

.. automodule:: simcronomicon.compartmental_models.step_event
   :members:
   :show-inheritance:
   :undoc-members:

simcronomicon.compartmental_models.SEIQRDV_model module
-------------------------------------------------------

.. automodule:: simcronomicon.compartmental_models.SEIQRDV_model
   :members:
   :show-inheritance:
   :undoc-members:

simcronomicon.compartmental_models.SEIR_model module
----------------------------------------------------

.. automodule:: simcronomicon.compartmental_models.SEIR_model
   :members:
   :show-inheritance:
   :undoc-members:

simcronomicon.compartmental_models.SEIsIrR_model module
-------------------------------------------------------

.. automodule:: simcronomicon.compartmental_models.SEIsIrR_model
   :members:
   :show-inheritance:
   :undoc-members:

Define Your Own Model
---------------------

You can create your own compartmental model by subclassing `AbstractCompartmentalModel` and following the structure of the provided models.

.. note::
   Add your new model module here for documentation!