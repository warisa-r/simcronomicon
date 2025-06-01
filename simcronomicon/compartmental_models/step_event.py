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
    def __init__(
            self,
            name,
            folk_action,
            event_type=EventType.SEND_HOME,
            max_distance=0,
            place_types=[],
            probability_func=None):
        """
        Initialize a StepEvent. A StepEvent is an instance that defines an agents' activities in a day.
        This means that one day can have multiple StepEvent defined!
        A StepEvent contained a name, an action that is performed by the agent when this StepEvent is being
        carried out, a maximum distance that agents will travel to perform this event, and the place types
        of the event.

        Parameters
        ----------
        name : str
            Name of the event.
        folk_action : callable
            Function to execute for each folk during the event. Must accept 4 arguments (folks_here, status_dict_t, model_params, dice).
        event_type : EventType, optional
            Type of the event (default: EventType.SEND_HOME).
        max_distance : int, optional
            Maximum distance in meters for the event (default: 0).
        place_types : list, optional
            List of place types relevant for the event (default: []).
        probability_func : callable, optional
            Function that takes a list of distances and returns a list of probabilities of those distances based on the probability
            function you want to use to model human mobility.
            If None, uniform probability is used.

        Examples
        --------
        - StepEvent("end_day", self.folk_class.sleep):
        Agents send home and send to sleep. A days ends with this event.

        - StepEvent("chore", self.folk_class.interact, EventType.DISPERSE, 19000, ['commercial', 'workplace', 'education', 'religious']):
        Agents disperse up to 19km to perform chores at commercial, workplace, education, or religious places.
        """
        # TODO: Write check that place_types is in the classification in
        # town.py
        self.name = name
        self.max_distance = max_distance  # in meters
        self.place_types = place_types
        self.event_type = event_type
        self.folk_action = folk_action
        self.probability_func = probability_func
        assert not (event_type == EventType.SEND_HOME and probability_func !=
                    None), "You cannot define a mobility probability function for an event that does not disperse people"
