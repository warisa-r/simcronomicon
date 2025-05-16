class StepEvent():
    def __init__(self, name, step_freq, max_distance, place_types):
        #TODO: Write check that place_types is in the classification in town.py
        self.name = name
        self.step_freq = step_freq
        self.max_distance = max_distance # Unit here is [m]
        self.place_types = place_types
    def __repr__(self):
        return f"{self.name} happens {self.step_freq} time(s) a step and each folk can travel up to {self.max_distance} to complete it."