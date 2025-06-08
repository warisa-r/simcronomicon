from enum import Enum
import numpy as np


def log_normal_probabilities(distances, mu=0, sigma=1):
    """
    Return probabilities inversely proportional to log-normal PDF of distances. Log-normal PDF has been studied to model
    the human mobility pattern in this follow literature and its predecessor:
    Faisal, S., Bertelle, C., & George, L. E. (2016). Human Mobility Patterns Modelling using CDRs. 
    International Journal of UbiComp (IJU), 7(1), 13–19. https://doi.org/10.5121/iju.2016.7102

    Note: CDRs are call detail records. These include the position of the cell towers the subscribers are closest to at the
    moment.
    """
    distances = np.array(distances)
    # Avoid log(0) and negative/zero distances
    distances = np.clip(distances, 1e-6, None)
    probs = 1 / (distances * sigma * np.sqrt(2 * np.pi)) * \
        np.exp(- (np.log(distances) - mu) ** 2 / (2 * sigma ** 2))
    probs = np.nan_to_num(probs, nan=0.0, posinf=0.0, neginf=0.0)
    probs = probs / probs.sum() if probs.sum() > 0 else np.ones_like(probs) / len(probs)
    return probs


class EventType(Enum):
    """
    Step events are classified into two types.
    - DISPERSE is the type of event
    that send agents around the town graph to specific locations in a given range and allow them to interact with other agents
    who are in the same nodes.
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
       customizable probability functions based on distance.

    Event Types
    -----------
    - **DISPERSE**: Agents move to locations within specified distance and place
      type constraints. Enables agent-to-agent interactions at destinations.
    - **SEND_HOME**: All agents return directly to their home addresses without
      movement or interaction. Represents end-of-day or emergency scenarios.

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
        Distance-based mobility probability function.

    Examples
    --------
    >>> # End of day event
    >>> end_day = StepEvent("end_day", folk_class.sleep)
    >>> 
    >>> # Work event with specific constraints
    >>> work = StepEvent("work", folk_class.interact, EventType.DISPERSE, 
    ...                  max_distance=10000, place_types=['workplace'])
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
            Function executed for each agent during the event. Must accept 4 arguments:
            (folks_here, status_dict_t, model_params, dice).
        event_type : EventType, optional
            Movement behavior type (default: EventType.SEND_HOME).
        max_distance : int, optional
            Maximum travel distance in meters for DISPERSE events (default: 0).
        place_types : list, optional
            Place type categories agents can visit. Examples: ['commercial', 'workplace'] 
            (default: []).
        probability_func : callable, optional
            Function taking distances and returning movement probabilities [0,1].
            Cannot be used with SEND_HOME events (default: None).

        Raises
        ------
        ValueError
            If probability_func is specified for SEND_HOME events, if probability_func
            is not callable, or if it returns invalid probability values.

        Examples
        --------
        >>> # Simple home event
        >>> StepEvent("end_day", folk_class.sleep)

        >>> # Complex disperse event with mobility function
        >>> StepEvent("shopping", folk_class.interact, EventType.DISPERSE,
        ...           max_distance=5000, place_types=['commercial'],
        ...           probability_func=log_normal_probabilities)
        """
        # town.py
        self.name = name
        self.max_distance = max_distance  # in meters
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

            try:
                # Test with dummy arguments
                # or whatever test arguments make sense
                test_result = probability_func([0, 1000])
                if not isinstance(test_result, (int, float, np.ndarray)):
                    raise ValueError(
                        "probability_func must return a numeric value (int, float, or numpy array)")

                # Convert to numpy array for easier validation
                result_array = np.asarray(test_result)

                # Check if all values are between 0 and 1
                if not np.all((result_array >= 0) & (result_array <= 1)):
                    raise ValueError(
                        "probability_func must return values between 0 and 1 (inclusive)")

            except Exception as e:
                raise ValueError(
                    f"probability_func failed validation test: {e}")
