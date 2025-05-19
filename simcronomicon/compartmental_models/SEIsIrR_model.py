"""
This module implements rumor spreading dynamics with considerations for
credibility, correlation, and crowd personality-based classification.

The implementation is based on:

Chen, X., & Wang, N. (2020). 
Rumor spreading model considering rumor credibility, correlation and crowd classification based on personality. 
*Scientific Reports*, 10, 5887. https://doi.org/10.1038/s41598-020-62687-5
"""

from .abstract_model import AbstractModelParameters, Folk, AbstractCompartmentalModel
from .step_event import StepEvent, EventType
import random as rd

class SEIsIrRModelParameters(AbstractModelParameters):
    def __init__(self, max_social_energy, literacy, gamma, alpha, lam, phi, theta, mu, eta1, eta2, mem_span = 10):
        super().__init__(max_social_energy)
        self.literacy = literacy

        # Use the same parameter sets as the model notation but precalculate the conversion rate
        # since these are the same through out the simulation

        # Check if we have the right input type
        for name, value in zip(
            ['gamma', 'alpha', 'lam', 'phi', 'theta', 'mu', 'eta1', 'eta2'],
            [gamma, alpha, lam, phi, theta, mu, eta1, eta2]
        ):
            if not isinstance(value, (float, int)):
                raise TypeError(f"{name} must be a float or int, got {type(value).__name__}")
        
        # Cast to float
        gamma, alpha, lam, phi, theta, mu, eta1, eta2 = map(float, [gamma, alpha, lam, phi, theta, mu, eta1, eta2])

        if not isinstance(mem_span, int) or mem_span <= 1:
            raise ValueError(f"mem_span must be an integer greater than 1, got {mem_span}")

        # Store some parameters so that they can be recalled as simulation metadata later on 
        self.alpha = alpha
        self.gamma = gamma
        self.mu = mu
        gamma_alpha_lam = gamma * alpha * lam

        # We use number 2 to signify transition that happens because of interaction
        self.Is2E = (1-gamma) * gamma_alpha_lam
        self.Is2S = gamma_alpha_lam * mu
        self.Ir2S = gamma_alpha_lam
        self.E2S = theta
        self.E2R = phi
        self.S2R = eta1
        self.forget = eta2
        self.mem_span = mem_span
    def to_metadata_dict(self):
        return {
            'max_social_energy': self.max_social_energy,
            'literacy': self.literacy,
            'alpha': self.alpha,
            'gamma': self.gamma,
            'phi': self.E2R,
            'theta': self.E2S,
            'mu': self.mu,
            'eta1': self.S2R,
            'eta2': self.forget,
            'mem_span': self.mem_span,
        }

class FolkSEIsIrR(Folk):
    def __init__(self, id, home_address, max_social_energy, status):
        super().__init__(id, home_address, max_social_energy, status)
    
    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        num_contact = len([folk for folk in folks_here if folk != self and folk.status in stats])

        if num_contact == 0:
            contact_possibility = 0
        elif num_contact >= self.social_energy:
            contact_possibility = self.social_energy
        else:
            contact_possibility = self.social_energy * num_contact / self.max_social_energy

        return super().inverse_bernoulli(contact_possibility, conversion_prob)

    def interact(self, folks_here, status_dict_t, model_params, dice):
        # Rule 1
        if self.status == 'Ir' and self.inverse_bernoulli(folks_here, model_params.Ir2S, ['S']) > dice:
            self.convert('S', status_dict_t)
        # Rule 2
        elif self.status == 'Is':
            conversion_rate_S = self.inverse_bernoulli(folks_here, model_params.Is2S, ['S'])
            conversion_rate_E = self.inverse_bernoulli(folks_here, model_params.Is2E, ['S'])

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
            conversion_rate_S = self.inverse_bernoulli(folks_here, model_params.E2S, ['S'])
            conversion_rate_R = self.inverse_bernoulli(folks_here, model_params.E2R, ['R'])

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
        elif self.status == 'S' and self.inverse_bernoulli(folks_here, model_params.S2R, ['S', 'E', 'R']) > dice:
            self.convert('R', status_dict_t)

        self.social_energy -= 1
    
    def sleep(self, status_dict_t, model_params, dice):
        super().sleep()
        if self.status == 'S':
            # Rule 4.2: Forgetting mechanism
            if model_params.mem_span <= self.status_step_streak or dice < model_params.forget:
                self.convert('R', status_dict_t)
    
class SEIsIrRModel(AbstractCompartmentalModel):
    def __init__(self, model_params):
        self.all_statuses = (['S', 'E', 'Ir', 'Is', 'R'])
        self.infected_statuses = 'S'
        self.step_events = [StepEvent("greet_neighbors", EventType.DISPERSE, False, 5000, ['accommodation']),
                            StepEvent("chore",  EventType.DISPERSE, False , 19000, ['commercial', 'workplace', 'education', 'religious'])]
        super().__init__(model_params)
        self.folk_class = FolkSEIsIrR
    
    def initialize_sim_population(self, town):
        num_pop = town.town_params.num_pop
        num_init_spreader = town.town_params.num_init_spreader
        
        folks = []
        household_node_indices = set()

        num_Is = round(self.model_params.literacy * num_pop)
        num_Ir = num_pop - num_Is

        # Spreaders often originated from Ir type of folks first
        num_Ir -= num_init_spreader
        if num_Ir < 0: # Then some Is folks can become spreader too
            num_Is += num_Ir
            num_Ir = 0

        for i in range(num_pop):
            node = rd.choice(town.accommodation_node_ids)
            if i < num_init_spreader:
                folk = self.create_folk(i, node, self.model_params.max_social_energy, 'S')
            elif i >= num_init_spreader and i < num_init_spreader + num_Is:
                folk = self.create_folk(i, node, self.model_params.max_social_energy, 'Is')
            else:
                folk = self.create_folk(i, node, self.model_params.max_social_energy,'Ir')
            folks.append(folk)
            town.town_graph.nodes[node]['folks'].append(folk) # Account for which folks live where in the graph as well
        
            if len(town.town_graph.nodes[node]['folks']) == 2: # Track which node has a 'family' living in it
                household_node_indices.add(node)

        status_dict_t0 = {'current_event': None, 'timestep':0, 'S': num_init_spreader, 'E': 0, 'Is': num_Is, 'Ir': num_Ir, 'R': 0}
        return folks, household_node_indices, status_dict_t0