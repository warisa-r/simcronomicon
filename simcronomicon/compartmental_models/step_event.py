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
        # TODO: Write check that place_types is in the classification in
        # town.py
        self.name = name
        self.max_distance = max_distance  # in meters
        self.place_types = place_types
        self.event_type = event_type
        # MUST ALWAYS BE A FUNCTION OF 4 ARGUMENTS (folks_here, status_dict_t,
        # model_params, dice)
        self.folk_action = folk_action

    def __repr__(self):
        return (
            f"{
                self.name} ({
                self.event_type.value}) happens {
                self.step_freq} time(s) a step " f"and each folk can travel up to {
                    self.max_distance}m to complete it.")
