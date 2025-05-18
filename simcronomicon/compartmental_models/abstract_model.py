import random as rd
from .step_event import StepEvent, EventType

class AbstractModelParameters():
    def __init__(self, max_social_energy):
        self.max_social_energy = max_social_energy
    def to_metadata_dict(self):
        raise NotImplementedError("Subclasses must implement to_metadata_dict()")

class Folk:
    def __init__(self, id, home_address, max_social_energy, status):
        self.id = id
        self.home_address = home_address
        self.address = self.home_address
        self.max_social_energy = max_social_energy
        self.social_energy = rd.randint(0, max_social_energy)
        self.status = status

    def convert(self, new_stat, status_dict_t):
        assert self.status != new_stat, f"New status cannot be the same as the old status({new_stat})! Please review your transition rules!"
        status_dict_t[self.status] -= 1
        status_dict_t[new_stat] += 1
        self.status = new_stat

    def inverse_bernoulli(self, contact_possibility, conversion_prob):
        """
        This function that determines the probability of status transition is adapted from section 2.2 of
        Eden, M., Castonguay, R., Munkhbat, B., Balasubramanian, H., & Gopalappa, C. (2021).
        Agent-based evolving network modeling: A new simulation method for modeling low prevalence infectious diseases.
        Health Care Management Science, 24, 623–639. https://doi.org/10.1007/s10729-021-09553-5
        """
        if contact_possibility == 0:
            return 0
        else:
            return 1-(1-conversion_prob)**(contact_possibility)

    def sleep(self):
        self.social_energy = rd.randint(0, self.max_social_energy) # Reset social energy

    def __repr__(self):
        return f"Person live at {self.home_address}, currently at {self.address}, Social Energy={self.social_energy}, Status={self.status}"

class AbstractCompartmentalModel():
    def __init__(self, model_params):
        self.model_params = model_params
        self.folk_class = Folk

        # This is an important check and it will ONLY work when you define 
        # some of the attributes before calling the abstract level constructor
        # See SEIsIrR for an example of how to write a constructor.
        required_attrs = {
            'infected_status': "Subclasses must define 'infected_status'.",
            'all_statuses': "Subclasses must define 'all_statuses' with at least 3 statuses.",
            'step_events': "Subclasses must define 'step_events' with at least one event."
        }

        for attr, message in required_attrs.items():
            if not hasattr(self, attr):
                raise NotImplementedError(message)

        # Status is also actually plural of a status but for clarity that this is plural,
        # the software will stick with the commonly used statuses
        if len(self.all_statuses) < 3:
            raise ValueError("A compartmental model must consist of at least 3 different statuses.")
        
        if len(self.step_events) < 1:
            raise ValueError("A series of events that agents cannot be an empty set.")
        
        # Append end_day event to the existing day events given by the user
        end_day = StepEvent("end_day")
        self.step_events.append(end_day)

    def create_folk(self, *args, **kwargs):
        return self.folk_class(*args, **kwargs)
    
    def initialize_sim_population(self):
        raise NotImplementedError("Subclasses must implement to_initialize_sim_population()")