from .abstract_model import AbstractModelParameters, Folk, AbstractCompartmentalModel
from .step_event import StepEvent, EventType
import random as rd


class SEIRModelParameters(AbstractModelParameters):
    def __init__(self, max_energy, beta, sigma, gamma, xi):
        # Check types and ranges
        for name, value in zip(
            ['beta', 'sigma', 'gamma', 'xi'],
            [beta, sigma, gamma, xi]
        ):
            if name == 'beta':
                if not isinstance(value, (float, int)) or not (0 < value < 1):
                    raise TypeError(
                        "beta must be a float between 0 and 1 (exclusive)!")
            else:
                if not isinstance(value, int) or value <= 0:
                    raise TypeError(
                        f"{name} must be a positive integer since it is a value that described duration, got {value}")

        super().__init__(max_energy)

        self.beta = beta  # Transimssion probability
        self.sigma = sigma  # Incubation duration
        self.gamma = gamma  # Symptom duration
        self.xi = xi  # Immune duration

    def to_metadata_dict(self):
        return {
            'max_energy': self.max_energy,
            'beta': self.beta,
            'sigma': self.sigma,
            'gamma': self.gamma,
            'xi': self.xi
        }


class FolkSEIR(Folk):
    def __init__(self, id, home_address, max_energy, status):
        super().__init__(id, home_address, max_energy, status)

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        num_contact = len(
            [folk for folk in folks_here if folk != self and folk.status in stats])
        return super().inverse_bernoulli(num_contact, conversion_prob)

    def interact(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        # When a susceptible person comes into contact with an infectious person,
        # they have a likelihood to become exposed to the disease
        if self.status == 'S' and self.inverse_bernoulli(
                folks_here, model_params.beta, ['I']) > dice:
            self.convert('E', status_dict_t)

    def sleep(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        super().sleep()
        if self.status == 'E' and self.status_step_streak == model_params.sigma:
            self.convert('I', status_dict_t)
        elif self.status == 'I' and self.status_step_streak == model_params.gamma:
            self.convert('R', status_dict_t)
        elif self.status == 'R' and self.status_step_streak == model_params.xi:
            self.convert('S', status_dict_t)


class SEIRModel(AbstractCompartmentalModel):
    def __init__(self, model_params):
        self.folk_class = FolkSEIR
        self.all_statuses = (['S', 'E', 'I', 'R'])
        self.infected_statuses = ['I', 'E']
        self.required_place_types = set(
            ['workplace', 'education', 'religious'])
        self.step_events = [
            StepEvent(
                "greet_neighbors",
                self.folk_class.interact,
                EventType.DISPERSE,
                5000,
                ['accommodation']),
            StepEvent(
                "chore",
                self.folk_class.interact,
                EventType.DISPERSE,
                19000,
                [
                    'commercial',
                    'workplace',
                    'education',
                    'religious'])]
        super().__init__(model_params)

    def initialize_sim_population(self, town):
        num_init_spreader_nodes = len(town.town_params.spreader_initial_nodes)
        assert town.num_init_spreader > num_init_spreader_nodes, "There cannot be more locations of the initial spreaders than the number of initial spreaders"

        num_pop = town.town_params.num_pop
        num_init_spreader_rd = town.town_params.num_init_spreader - num_init_spreader_nodes

        folks = []
        household_node_indices = set()

        # Prepare a list of (node, status) for all folks to be created
        assignments = []

        # Randomly assign initial spreaders (not on specified nodes)
        for i in range(num_init_spreader_rd):
            node = rd.choice(town.accommodation_node_ids)
            assignments.append((node, 'I'))

        # Assign the rest as susceptible
        for i in range(num_pop - town.town_params.num_init_spreader):
            node = rd.choice(town.accommodation_node_ids)
            assignments.append((node, 'S'))

        # Assign initial spreaders to specified nodes
        for node in town.town_params.spreader_initial_nodes:
            assignments.append((node, 'I'))

        # Create folks and update graph/node info
        for i, (node, status) in enumerate(assignments):
            folk = self.create_folk(i, node, self.model_params.max_energy, status)
            folks.append(folk)
            town.town_graph.nodes[node]['folks'].append(folk)
            if len(town.town_graph.nodes[node]['folks']) == 2:
                household_node_indices.add(node)

        status_dict_t0 = {
            'current_event': None,
            'timestep': 0,
            'S': num_pop - town.town_params.num_init_spreader,
            'E': 0,
            'I': town.town_params.num_init_spreader,
            'R': 0
        }
        return folks, household_node_indices, status_dict_t0
