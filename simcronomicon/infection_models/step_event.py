import inspect
from enum import Enum

import numpy as np


def log_normal_mobility(distances, folk, median_distance=2000, sigma=1.0):
    """
    Return probabilities inversely proportional to log-normal PDF of distances. Log-normal PDF has been studied to model
    the human mobility pattern in this following literature and its predecessor:
    Wang, W., & Osaragi, T. (2024). Lognormal distribution of daily travel time and a utility model for its emergence. 
    Transportation Research Part A: Policy and Practice, 181, 104058. https://doi.org/10.1016/j.tra.2024.104058

    Parameters
    ----------
    median_distance : float
        Median travel distance in meters. This is where the distribution peaks.
        Default 1100m (1.1km) for typical neighborhood activities.
        Common values:
        - 400m → local/walking activities
        - 1100m → neighborhood activities  
        - 3000m → city-wide activities
        - 8000m → regional activities
    sigma : float
        Shape parameter controlling spread around median.
        - sigma=0.5 → narrow distribution, consistent travel patterns
        - sigma=1.0 → moderate distribution (default)
        - sigma=1.5 → wide distribution, highly variable travel patterns
    """
    distances = np.array(distances)
    # Avoid log(0) and negative/zero distances
    distances = np.clip(distances, 1e-6, None)

    # Convert median distance to mu parameter: mu = ln(median)
    mu = np.log(median_distance)

    probs = 1 / (distances * sigma * np.sqrt(2 * np.pi)) * \
        np.exp(- (np.log(distances) - mu) ** 2 / (2 * sigma ** 2))
    probs = np.nan_to_num(probs, nan=0.0, posinf=0.0, neginf=0.0)
    probs = probs / probs.sum() if probs.sum() > 0 else np.ones_like(probs) / len(probs)
    return probs


def energy_exponential_mobility(distances, folk, distance_scale=1000):
    """
    Return probabilities proportional to exponential PDF of distances. With lam = inverse of normalized energy
    as a rate parameter - higher energy = lower decay rate = more willing to travel far.

    Parameters
    ----------
    distance_scale : float
        Scale factor for distances to control decay rate. Higher values = slower decay.
        Default 1000 means distances are scaled to kilometers.
    """
    distances = np.array(distances)

    # Scale distances to control decay rate
    scaled_distances = distances / distance_scale

    # Higher energy = lower lambda (less decay) = more willing to travel far
    # Lower energy = higher lambda (more decay) = prefer nearby locations
    energy_ratio = folk.energy / folk.max_energy  # 0 to 1
    # This gives lambda from 1.0 (high energy) to 2.0 (no energy)
    lam = 2.0 - energy_ratio

    probs = lam * np.exp(-lam * scaled_distances)

    # Normalize probabilities to sum to 1
    probs = probs / probs.sum() if probs.sum() > 0 else np.ones_like(probs) / len(probs)

    return probs


class EventType(Enum):
    """
    Step events are classified into two types.

    - DISPERSE is the type of event
    that send agents around the town graph to specific locations in a given range and allow them to interact with other agents
    who are in the same nodes..

    - SEND_HOME is the type of event that every agents in the simulation back to their home address without any interaction.
    SEND_HOME can represent the end of the day where everybody go home and sleep or an emergency announcement
    that sends everyone around town straight back home.
    """
    SEND_HOME = "send_home"
    DISPERSE = "disperse"


class StepEvent:
    """
    Defines agent activities and movement patterns during simulation timesteps.

    StepEvent objects represent discrete activities that agents perform during
    simulation timesteps. Each event specifies how agents move through the town
    network, what types of locations they visit, and what actions they perform
    when they arrive at destinations.

    Purpose
    -------
    1. **Agent Movement Control**: Define where and how far agents travel during
       specific activities (work, shopping, healthcare visits, etc.).

    2. **Location Targeting**: Specify which types of places agents visit for
       different activities using place type filters.

    3. **Mobility Modeling**: Apply realistic human mobility patterns through
       customizable probability functions based on distance and agent characteristics.

    4. **Agent-Dependent Behavior**: Enable mobility patterns that adapt to individual
       agent properties such as energy levels, status, or other attributes.

    Event Types
    -----------
    - **DISPERSE**: Agents move to locations within specified distance and place
      type constraints. Enables agent-to-agent interactions at destinations.

    - **SEND_HOME**: All agents return directly to their home addresses without
      movement or interaction. Represents end-of-day or emergency scenarios.

    Probability Functions
    --------------------
    Custom probability functions must:

    - Accept exactly 2 non-default arguments: `(distances, agent)`

    - Return probabilities between 0 and 1 (will be normalized automatically)

    - Handle numpy arrays for distances

    - Be robust to edge cases (empty arrays, zero distances)

    Built-in mobility functions include:
    - `log_normal_mobility`: Human mobility based on log-normal distance 

    - `energy_exponential_mobility`: Agent energy-dependent exponential decay

    Attributes
    ----------
    name : str
        Event identifier.
    max_distance : int
        Maximum travel distance in meters.
    place_types : list
        Allowed destination place types.
    event_type : EventType
        Movement behavior type.
    folk_action : callable
        Agent interaction function.
    probability_func : callable or None
        Distance and agent-based mobility probability function.

    Examples
    --------
    >>> # End of day event
    >>> end_day = StepEvent("end_day", folk_class.sleep)
    >>> 
    >>> # Work event with distance constraints
    >>> work = StepEvent("work", folk_class.interact, EventType.DISPERSE, 
    ...                  max_distance=10000, place_types=['workplace'])
    >>>
    >>> # Shopping with log-normal mobility
    >>> shopping = StepEvent("shopping", folk_class.interact, EventType.DISPERSE,
    ...                      max_distance=5000, place_types=['commercial'],
    ...                      probability_func=log_normal_mobility)
    >>>
    >>> # Energy-dependent movement
    >>> leisure = StepEvent("leisure", folk_class.interact, EventType.DISPERSE,
    ...                     max_distance=8000, place_types=['commercial', 'religious'],
    ...                     probability_func=energy_exponential_mobility)
    >>>
    >>> # Custom agent-dependent mobility
    >>> def age_based_mobility(distances, agent):
    ...     import numpy as np
    ...     distances = np.array(distances)
    ...     # Older agents prefer shorter distances
    ...     age_factor = getattr(agent, 'age', 30) / 100.0  # Normalize age
    ...     decay_rate = 0.0001 * (1 + age_factor)  # Higher decay for older agents
    ...     probs = np.exp(-decay_rate * distances)
    ...     return probs / probs.sum() if probs.sum() > 0 else np.ones_like(probs) / len(probs)
    >>>
    >>> custom_event = StepEvent("age_sensitive", folk_class.interact, EventType.DISPERSE,
    ...                          max_distance=15000, place_types=['healthcare'],
    ...                          probability_func=age_based_mobility)
    """

    def __init__(
            self,
            name,
            folk_action,
            event_type=EventType.SEND_HOME,
            max_distance=0,
            place_types=[],
            probability_func=None):
        """
        Initialize a StepEvent for agent activity simulation.

        Parameters
        ----------

        name : str
            Descriptive name for the event (e.g., "work", "shopping", "end_day").
        folk_action : callable
            Function executed for each agent during the event. Must accept arguments:
            (folks_here, current_place_type, status_dict_t, model_params, dice).
        event_type : EventType, optional
            Movement behavior type (default: EventType.SEND_HOME).
        max_distance : int, optional
            Maximum travel distance in meters for DISPERSE events (default: 0).
        place_types : list, optional
            Place type categories agents can visit. Examples: ['commercial', 'workplace'] 
            (default: []).
        probability_func : callable, optional
            Function taking (distances, agent) and returning movement probabilities [0,1].
            Must have exactly 2 non-default arguments. Cannot be used with SEND_HOME events 
            (default: None).

        Raises
        ------

        ValueError
            - If probability_func is specified for SEND_HOME events

            - If probability_func is not callable

            - If probability_func doesn't have exactly 2 non-default arguments

            - If probability_func returns invalid probability values during validation

            - If probability_func fails signature inspection

        """
        self.name = name
        self.max_distance = max_distance
        self.place_types = place_types
        self.event_type = event_type
        self.folk_action = folk_action
        self.probability_func = probability_func
        if event_type == EventType.SEND_HOME and probability_func is not None:
            raise ValueError(
                "You cannot define a mobility probability function for an event that does not disperse people")

        if probability_func is not None:
            if not callable(probability_func):
                raise ValueError(
                    "probability_func must be a callable function")

            # Check function signature only
            try:
                sig = inspect.signature(probability_func)
                non_default_params = [
                    p for p in sig.parameters.values()
                    if p.default == inspect.Parameter.empty
                ]

                if len(non_default_params) != 2:
                    raise ValueError(
                        f"probability_func must have exactly 2 non-default arguments, "
                        f"got {len(non_default_params)}. Expected signature: func(distances, agent, **kwargs)")

            except Exception as e:
                raise ValueError(
                    f"Could not inspect probability_func signature: {e}")
