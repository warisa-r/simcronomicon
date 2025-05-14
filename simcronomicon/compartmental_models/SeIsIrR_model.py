from .abstract_agent import Folk
from .step_event import StepEvent
import random as rd

class SEIsIrRModelParameters():
    def __init__(self, gamma, alpha, lam, phi, theta, mu, eta1, eta2, mem_span = 10):
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

class FolkSEIsIrR(Folk):
    def __init__(self, home_address, max_social_energy, status):
        super().__init__(home_address, max_social_energy, status)

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
        if self.status == 'S':
            # Rule 4.2: Forgetting mechanism
            #TODO: Consider this
            if model_params.mem_span <= self.spreader_streak or dice < model_params.forget:
                self.convert('R', status_dict_t)
            else:
                self.spreader_streak += 1
        self.social_energy = rd.randint(0, self.max_social_energy) # Reset social energy
    
class SEIsIrRModel():
    def __init__(self, model_params):
        self.step_events = [StepEvent("greet_neighbors", 1, 5000, ['accommodation']),
                            StepEvent("chore", 1, 19000, ['commercial', 'workplace', 'education', 'religious'])]
        self.model_params = model_params
        self.all_status = ['S', 'E', 'Ir', 'Is', 'R']
        self.folk_class = FolkSEIsIrR

    def create_folk(self, *args, **kwargs):
        return self.folk_class(*args, **kwargs)
    
    def initialize_sim_population(self, num_pop, num_init_spreader, town):
        #TODO: max_social_energy and literacy should be model params
        folks = []
        household_node_indices = set()

        num_Is = round(town.town_params.literacy * num_pop)
        num_Ir = num_pop - num_Is

        # Spreaders often originated from Ir type of folks first
        num_Ir -= num_init_spreader
        if num_Ir < 0: # Then some Is folks can become spreader too
            num_Is += num_Ir
            num_Ir = 0

        for i in range(num_pop):
            node = rd.choice(town.accommodation_node_ids)
            if i < num_init_spreader:
                folk = self.create_folk(node, town.town_params.max_social_energy, 'S')
            elif i >= num_init_spreader and i < num_init_spreader + num_Is:
                folk = self.create_folk(node, town.town_params.max_social_energy, 'Is')
            else:
                folk = self.create_folk(node, town.town_params.max_social_energy,'Ir')
            folks.append(folk)
            town.town_graph.nodes[node]['folks'].append(folk) # Account for which folks live where in the graph as well
        
            if len(town.town_graph.nodes[node]['folks']) == 2: # Track which node has a 'family' living in it
                household_node_indices.add(node)

        status_dict_t0 = {'S': num_init_spreader, 'Is': num_Is, 'Ir': num_Ir, 'R': 0, 'E': 0, 'current_event': None, 'timestep':0}
        return folks, household_node_indices, status_dict_t0