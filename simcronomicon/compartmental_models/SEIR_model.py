from .abstract_model import AbstractModelParameters, Folk, AbstractCompartmentalModel
import random as rd

class SEIRModelParameters(AbstractModelParameters):
    def __init__(self, max_social_energy, beta, sigma, gamma, xi):
        super().__init__(max_social_energy)

        
        self.beta = beta # Transimssion probability
        self.sigma = sigma # Incubation duration
        self.gamma = gamma # Symptom duration
        self.xi = xi # Immune duration
    
    def to_metadata_dict(self):
            return {
                'max_social_energy': self.max_social_energy,
                'beta': self.beta,
                'sigma': self.sigma,
                'gamma': self.gamma,
                'xi':self.xi
            }

class FolkSEIR(Folk):
    def __init__(self, id, home_address, max_social_energy, status):
         super().__init__(id, home_address, max_social_energy, status)

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        num_contact = len([folk for folk in folks_here if folk != self and folk.status in stats])
        return super().inverse_bernoulli(num_contact, conversion_prob)
    
    def interact(self, folks_here, status_dict_t, model_params, dice):
        # When a susceptible person comes into contact with an infectious person,
        # they have a likelihood to become exposed to the disease
        if self.status == 'S' and self.inverse_bernoulli(folks_here, model_params.beta, ['I']) > dice:
            self.convert('E', status_dict_t)