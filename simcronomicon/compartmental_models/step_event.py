from enum import Enum


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
            place_types=[]):
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
        # MUST ALWAYS BE A FUNCTION OF 4 ARGUMENTS (folks_here, status_dict_t,
        # model_params, dice)
        self.folk_action = folk_action
