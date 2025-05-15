import random as rd

class AbstractModelParameters():
    def __init__(self, max_social_energy):
        self.max_social_energy = max_social_energy
    def to_metadata_dict(self):
        raise NotImplementedError("Subclasses must implement to_metadata_dict()")

class Folk:
    def __init__(self, home_address, max_social_energy, status):
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
        # the infected status before calling the abstract level constructor
        # See SEIsIrR for an example of how to write a constructor.
        if not hasattr(self, 'infected_status'):
            raise NotImplementedError("Subclasses of AbstractCompartmentalModel must define 'infected_status'")

    def create_folk(self, *args, **kwargs):
        return self.folk_class(*args, **kwargs)