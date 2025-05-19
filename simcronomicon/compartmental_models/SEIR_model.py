from .abstract_model import AbstractModelParameters, Folk, AbstractCompartmentalModel
from .step_event import StepEvent, EventType
import random as rd

#TODO: Allow infected status to be more than 1 status and run through all those stats to check for termination
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

    def sleep(self, status_dict_t, model_params, dice):
        super().sleep()
        if self.status == 'E' and self.status_step_streak == model_params.sigma:
            self.convert('I', status_dict_t)
        elif self.status == 'I' and self.status_step_streak == model_params.gamma:
            #TODO: If there were to be dying, it would happen here
            self.convert('R', status_dict_t)
        elif self.status == 'R' and self.status_step_streak == model_params.xi:
            self.convert('S', status_dict_t)

class SEIRModel(AbstractCompartmentalModel):
    def __init__(self, model_params):
        self.all_statuses = (['S', 'E', 'I', 'R'])
        self.infected_statuses = ['I', 'E']
        self.step_events = [StepEvent("greet_neighbors", EventType.DISPERSE, False, 5000, ['accommodation']),
                            StepEvent("chore",  EventType.DISPERSE, False , 19000, ['commercial', 'workplace', 'education', 'religious'])]
        super().__init__(model_params)
        self.folk_class = FolkSEIR    

    def initialize_sim_population(self, town):
            num_pop = town.town_params.num_pop
            num_init_spreader = town.town_params.num_init_spreader
            
            folks = []
            household_node_indices = set()

            for i in range(num_pop):
                node = rd.choice(town.accommodation_node_ids)
                if i < num_init_spreader:
                    folk = self.create_folk(i, node, self.model_params.max_social_energy, 'I')
                else:
                    folk = self.create_folk(i, node, self.model_params.max_social_energy,'S')
                folks.append(folk)
                town.town_graph.nodes[node]['folks'].append(folk) # Account for which folks live where in the graph as well
            
                if len(town.town_graph.nodes[node]['folks']) == 2: # Track which node has a 'family' living in it
                    household_node_indices.add(node)

            status_dict_t0 = {'current_event': None, 'timestep':0, 'S': num_pop-num_init_spreader, 'E': 0, 'I': num_init_spreader, 'R': 0}
            return folks, household_node_indices, status_dict_t0