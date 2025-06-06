"""
This module implements rumor spreading dynamics with considerations for
credibility, correlation, and crowd personality-based classification.

The implementation is based on:

Chen, X., & Wang, N. (2020).
Rumor spreading model considering rumor credibility, correlation and crowd classification based on personality.
*Scientific Reports*, 10, 5887. https://doi.org/10.1038/s41598-020-62585-9
"""

from .abstract_model import AbstractModelParameters, Folk, AbstractCompartmentalModel
from .step_event import StepEvent, EventType
import random as rd


class SEIsIrRModelParameters(AbstractModelParameters):
    """
    Model parameters for the SEIsIrR rumor spreading model.

    Parameters
    ----------
    max_energy : int
        Maximum energy for each agent.
    literacy : float
        Fraction of the population that is literate (0 <= literacy <= 1, affects Is/Ir split).
    gamma : float
        Fraction representing how credible the rumor is (0 <= gamma <= 1).
    alpha : float
        Fraction representing how relevant the rumor is to a human's life (0 <= alpha <= 1).
    lam : float
        Rumor spreading probability (0 <= lam <= 1).
    phi : float
        Stifling probability parameter for E to R transition (0 <= phi <= 1).
    theta : float
        Probability parameter for E to S transition (0 <= theta <= 1).
    mu : float
        The spreading desire ratio of individuals in class Is to individuals in class Ir (0 <= mu <= 1).
    eta1 : float
        Probability parameter for S to R transition (0 <= eta1 <= 1).
    eta2 : float
        Probability parameter for forgetting (S to R) in sleep (0 <= eta2 <= 1).
    mem_span : int, optional
        Memory span for forgetting mechanism (default: 10).

    Raises
    ------
    TypeError
        If any parameter is not of the correct type or out of valid range.
    """

    def __init__(
            self,
            max_energy,
            literacy,
            gamma,
            alpha,
            lam,
            phi,
            theta,
            mu,
            eta1,
            eta2,
            mem_span=10):
        super().__init__(max_energy)
        self.literacy = literacy

        # Use the same parameter sets as the model notation but precalculate the conversion rate
        # since these are the same through out the simulation

        # Check if we have the right input type
        for name, value in zip(
            ['gamma', 'alpha', 'lam', 'phi', 'theta', 'mu', 'eta1', 'eta2'],
            [gamma, alpha, lam, phi, theta, mu, eta1, eta2]
        ):
            if not isinstance(value, (float, int)):
                raise TypeError(
                    f"{name} must be a float or int, got {
                        type(value).__name__}")

        # Cast to float
        gamma, alpha, lam, phi, theta, mu, eta1, eta2 = map(
            float, [gamma, alpha, lam, phi, theta, mu, eta1, eta2])

        if not isinstance(mem_span, int) or mem_span <= 1:
            raise TypeError(
                f"mem_span must be an integer greater than 1, got {mem_span}")

        # Store some parameters so that they can be recalled as simulation
        # metadata later on
        self.alpha = alpha
        self.gamma = gamma
        self.mu = mu
        self.lam = lam
        gamma_alpha_lam = gamma * alpha * lam

        # We use number 2 to signify transition that happens because of
        # interaction
        self.Is2E = (1 - gamma) * gamma_alpha_lam
        self.Is2S = gamma_alpha_lam * mu
        self.Ir2S = gamma_alpha_lam
        self.E2S = theta
        self.E2R = phi
        self.S2R = eta1
        self.forget = eta2
        self.mem_span = mem_span

    def to_metadata_dict(self):
        return {
            'max_energy': self.max_energy,
            'literacy': self.literacy,
            'lam': self.lam,
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
    def __init__(self, id, home_address, max_energy, status):
        super().__init__(id, home_address, max_energy, status)

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        num_contact = len(
            [folk for folk in folks_here if folk != self and folk.status in stats])
        return super().inverse_bernoulli(num_contact, conversion_prob * self.energy / self.max_energy)

    def interact(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        # Rule 1
        if self.status == 'Ir' and self.inverse_bernoulli(
                folks_here, model_params.Ir2S, ['S']) > dice:
            self.convert('S', status_dict_t)
        # Rule 2
        elif self.status == 'Is':
            conversion_rate_S = self.inverse_bernoulli(
                folks_here, model_params.Is2S, ['S'])
            conversion_rate_E = self.inverse_bernoulli(
                folks_here, model_params.Is2E, ['S'])

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
            conversion_rate_S = self.inverse_bernoulli(
                folks_here, model_params.E2S, ['S'])
            conversion_rate_R = self.inverse_bernoulli(
                folks_here, model_params.E2R, ['R'])

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

        self.energy -= 1

    def sleep(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        super().sleep()
        if self.status == 'S':
            # Rule 4.2: Forgetting mechanism
            if model_params.mem_span <= self.status_step_streak or dice < model_params.forget:
                self.convert('R', status_dict_t)


class SEIsIrRModel(AbstractCompartmentalModel):
    def __init__(self, model_params, step_events=None):
        self.folk_class = FolkSEIsIrR
        self.all_statuses = (['S', 'E', 'Ir', 'Is', 'R'])
        self.infected_statuses = 'S'
        self.step_events = step_events
        super().__init__(model_params)

    def initialize_sim_population(self, town):
        num_pop, num_init_spreader, num_init_spreader_rd, folks, household_node_indices, assignments = super(
        )._initialize_sim_population(town)

        num_IsIr = num_pop - num_init_spreader

        # Divide remaining population between Is and Ir based on literacy
        num_Is = round(self.model_params.literacy * num_IsIr)
        num_Ir = num_IsIr - num_Is

        # Randomly assign initial spreaders (not on specified nodes)
        for _ in range(num_init_spreader_rd):
            node = rd.choice(town.accommodation_node_ids)
            assignments.append((node, 'S'))

        # Assign the rest as Is and Ir
        for _ in range(num_Is):
            node = rd.choice(town.accommodation_node_ids)
            assignments.append((node, 'Is'))
        for _ in range(num_Ir):
            node = rd.choice(town.accommodation_node_ids)
            assignments.append((node, 'Ir'))

        # Assign initial spreaders to specified nodes
        for node in town.town_params.spreader_initial_nodes:
            assignments.append((node, 'S'))

        # Create folks and update graph/node info
        for i, (node, status) in enumerate(assignments):
            folk = self.create_folk(
                i, node, self.model_params.max_energy, status)
            folks.append(folk)
            town.town_graph.nodes[node]["folks"].append(folk)
            if len(town.town_graph.nodes[node]["folks"]) == 2:
                household_node_indices.add(node)

        status_dict_t0 = {
            'current_event': None,
            'timestep': 0,
            'S': num_init_spreader,
            'E': 0,
            'Is': num_Is,
            'Ir': num_Ir,
            'R': 0
        }
        return folks, household_node_indices, status_dict_t0
