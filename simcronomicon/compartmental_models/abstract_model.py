import random as rd

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

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        num_contact = len([folk for folk in folks_here if folk != self and folk.status in stats])

        if num_contact == 0:
            return 0
        elif num_contact >= self.social_energy:
            return 1-(1-conversion_prob)**(self.social_energy)
        else:
            return 1-(1-conversion_prob)** (self.social_energy * num_contact / self.max_social_energy)
    
    def sleep(self):
        self.social_energy = rd.randint(0, self.max_social_energy) # Reset social energy
    def __repr__(self):
        return f"Person live at {self.home_address}, currently at {self.address}, Social Energy={self.social_energy}, Status={self.status}"

class AbstractCompartmentalModel():
    def __init__(self, model_params):
        self.model_params = model_params
        self.folk_class = Folk

    def create_folk(self, *args, **kwargs):
        return self.folk_class(*args, **kwargs)