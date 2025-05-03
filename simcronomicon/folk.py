from . import rd
from . import np

class Folk:
    def __init__(self, home_address, max_social_energy, status):
        self.home_address = home_address
        self.address = self.home_address
        self.max_social_energy = max_social_energy
        self.social_energy = rd.randint(0, max_social_energy) #TODO: I think max_rand_int corresponds with the maximum event occurrence in a day??
        self.status = status
        self.spreader_streak = 0
    
    #TODO: The rule of converting isnt that easy -> Bernoulli Go read ABNM method in the downloaded paper
    # Instead of 1 to 1 action do p^c_j
    def convert(self, new_stat, status_dict_t):
        """Convert the rumor spreading status of a person and update the counter of population with each status
        of the current time step"""
        
        status_dict_t[self.status] -= 1
        status_dict_t[new_stat] += 1
        if self.status == 'S':
            self.spreader_streak = 0 # Reset spreader streak
        self.status = new_stat

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        num_contact = len([folk for folk in folks_here if folk != self and folk.status in stats])

        if num_contact == 0:
            return 0
        elif num_contact >= self.social_energy:
            return 1-(1-conversion_prob)**(self.social_energy)
        else:
            return 1-(1-conversion_prob)** (self.social_energy * num_contact / self.max_social_energy)


    def interact(self, folks_here, status_dict_t, params, dice):
        self.social_energy -= 1
        
        # Rule 1
        if self.status == 'Ir' and self.inverse_bernoulli(folks_here, params.Ir2S, ['S']) > dice:
            self.convert('S', status_dict_t)
        # Rule 2
        elif self.status == 'Is':
            conversion_rate_S = self.inverse_bernoulli(folks_here, params.Is2S, ['S'])
            conversion_rate_E = self.inverse_bernoulli(folks_here, params.Is2E, ['S'])

            if conversion_rate_S > conversion_rate_E:
                if conversion_rate_E > dice:
                    self.convert('E', status_dict_t)
                elif conversion_rate_S > dice:
                    self.convert('S', status_dict_t)
            else:
                if conversion_rate_S > dice:
                    self.convert('S', status_dict_t)
                elif conversion_rate_E > dice:
                    self.convert('E', status_dict_t)
            
        # Rule 3
        elif self.status == 'E':
            conversion_rate_S = self.inverse_bernoulli(folks_here, params.E2S, ['S'])
            conversion_rate_R = self.inverse_bernoulli(folks_here, params.E2R, ['R'])

            if conversion_rate_S > conversion_rate_R:
                if conversion_rate_R > dice:
                    self.convert('R', status_dict_t)
                elif conversion_rate_S > dice:
                    self.convert('S', status_dict_t)
            else:
                if conversion_rate_R > dice:
                    self.convert('R', status_dict_t)
                elif conversion_rate_S > dice:
                    self.convert('S', status_dict_t)

        # Rule 4.1
        elif self.status == 'S' and self.inverse_bernoulli(folks_here, params.S2R, ['S', 'E', 'R']) > dice:
            self.convert('R', status_dict_t)
    
    def sleep(self, status_dict_t, params, dice):
        if self.status == 'S':
            # Rule 4.2: Forgetting mechanism
            #TODO: Consider this
            if params.mem_span <= self.spreader_streak or dice < params.forget:
                self.convert('R', status_dict_t)
            else:
                self.spreader_streak += 1
        self.social_energy = rd.randint(0, self.max_social_energy) # Reset social energy

    def __repr__(self):
        return f"Person live at {self.home_address}, currently at {self.address}, Social Energy={self.social_energy}, Status={self.status}"