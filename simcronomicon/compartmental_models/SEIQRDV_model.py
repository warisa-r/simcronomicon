from .abstract_model import AbstractModelParameters, Folk, AbstractCompartmentalModel
from .step_event import StepEvent, EventType
import random as rd

class SEIQRDVModelParameters(AbstractModelParameters):
    def __init__(self, max_energy, beta, alpha, gamma, delta, lam, rho, kappa):
        super().__init__(max_energy)

        # Adapted from https://www.mdpi.com/2227-7390/9/6/636

        self.beta = beta # Transimssion probability
        self.alpha = alpha # Vaccination rate
        self.gamma = gamma # Average latent time
        self.delta = delta # Average day until the infected case got confirmed and quarantined
        self.lam = lam # Average day until recovery
        self.rho = rho # Average day until death
        self.kappa = kappa # Disease mortality rate
    
    def to_metadata_dict(self):
            return {
                'max_energy': self.max_energy,
                'beta': self.beta,
                'alpha':self.alpha,
                'gamma': self.gamma,
                'delta': self.delta,
                'lam':self.lam,
                'rho':self.rho,
                'kappa':self.kappa
            }

class FolkSEIQRDV(Folk):
    def __init__(self, id, home_address, max_energy, status):
         super().__init__(id, home_address, max_energy, status)
         self.will_die = False
         self.want_vaccine = False

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        num_contact = len([folk for folk in folks_here if folk != self and folk.status in stats])
        return super().inverse_bernoulli(num_contact, conversion_prob)
    
    def interact(self, folks_here, current_place_type,  status_dict_t, model_params, dice):
        # When a susceptible person comes into contact with an infectious person,
        # they have a likelihood to become exposed to the disease
        if self.status == 'S' and self.inverse_bernoulli(folks_here, model_params.beta, ['I']) > dice:
            self.convert('E', status_dict_t)

        if current_place_type == 'healthcare_facility':
            if self.status == 'S' and self.want_vaccine:
                self.convert('V', status_dict_t)
                self.want_vaccine = False

    def sleep(self, folks_here, current_place_type,  status_dict_t, model_params, dice):
        super().sleep()
        if self.status == 'Q':
            if self.will_die:
                if self.status_step_streak == model_params.rho:
                    self.convert('D', status_dict_t)
                    self.alive = False
            else:
                if self.status_step_streak == model_params.lam:
                    self.convert('R', status_dict_t)
                    self.movement_restricted = True
        elif self.status == 'E' and self.status_step_streak == model_params.gamma:
            self.convert('I', status_dict_t)
        elif self.status == 'I' and self.status_step_streak == model_params.delta:
            self.convert('Q', status_dict_t)
            self.movement_restricted = True
            if dice > model_params.kappa:
                self.will_die = True
        elif self.status == 'S' and model_params.alpha > dice:
            # A person has a likelyhood alpha to plane to get vaccinated
            self.priority_place_type.append('healthcare_facility')
            self.want_vaccine = True

class SEIQRDVModel(AbstractCompartmentalModel):
    def __init__(self, model_params):
        self.folk_class = FolkSEIQRDV
        self.all_statuses = (['S', 'E', 'I', 'Q', 'R', 'D', 'V'])
        self.infected_statuses = ['I', 'E', 'Q']
        self.required_place_types = set(["healthcare_facility", 'workplace', 'education', 'religious'])
        self.step_events = [
            StepEvent("greet_neighbors", self.folk_class.interact, EventType.DISPERSE, 5000, ['accommodation']),
            StepEvent("chore", self.folk_class.interact, EventType.DISPERSE, 19000, ['commercial', 'workplace', 'education', 'religious'])]
        super().__init__(model_params)    

    def initialize_sim_population(self, town):
            num_pop = town.town_params.num_pop
            num_init_spreader = town.town_params.num_init_spreader
            
            folks = []
            household_node_indices = set()

            for i in range(num_pop):
                node = rd.choice(town.accommodation_node_ids)
                if i < num_init_spreader:
                    folk = self.create_folk(i, node, self.model_params.max_energy, 'I')
                else:
                    folk = self.create_folk(i, node, self.model_params.max_energy,'S')
                folks.append(folk)
                town.town_graph.nodes[node]['folks'].append(folk) # Account for which folks live where in the graph as well
            
                if len(town.town_graph.nodes[node]['folks']) == 2: # Track which node has a 'family' living in it
                    household_node_indices.add(node)

            status_dict_t0 = {'current_event': None, 'timestep':0, 'S': num_pop-num_init_spreader, 'E': 0, 'Q': 0, 'I': num_init_spreader, 'R': 0, 'D':0, 'V':0}
            return folks, household_node_indices, status_dict_t0