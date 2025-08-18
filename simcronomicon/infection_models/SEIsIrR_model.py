"""
This module implements the adaptation of rumor spreading dynamics with considerations for
credibility, correlation, and crowd personality-based classification or the so-called
SEIsIrR model in the paper mentioned below.

The implementation is based on:

Chen, X., & Wang, N. (2020).
Rumor spreading model considering rumor credibility, correlation and crowd classification based on personality.
*Scientific Reports*, 10, 5887. https://doi.org/10.1038/s41598-020-62585-9
"""

import random as rd

from .abstract_model import (AbstractInfectionModel, AbstractFolk,
                             AbstractModelParameters)


class SEIsIrRModelParameters(AbstractModelParameters):
    """
    Model parameters for the SEIsIrR rumor spreading model.

    This class encapsulates all tunable parameters required for the SEIsIrR
    rumor spreading model, including rumor credibility, spreading probabilities,
    and population literacy characteristics. It validates parameter types and
    ranges upon initialization.
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
        """
        Initialize SEIsIrR model parameters and validate all inputs.

        Parameters
        ----------
        max_energy : int
            Maximum energy for each agent (must be a positive integer).
        literacy : float
            Fraction of the population that is literate (must be between 0 and 1, affects Is/Ir split).
        gamma : float
            Fraction representing how credible the rumor is (must be between 0 and 1).
        alpha : float
            Fraction representing how relevant the rumor is to a human's life (must be between 0 and 1).
        lam : float
            Rumor spreading probability (must be between 0 and 1).
        phi : float
            Stifling probability parameter for E to R transition (must be between 0 and 1).
        theta : float
            Probability parameter for E to S transition (must be between 0 and 1).
        mu : float
            The spreading desire ratio of individuals in class Is to individuals in class Ir (must be between 0 and 1).
        eta1 : float
            Probability parameter for S to R transition (must be between 0 and 1).
        eta2 : float
            Probability parameter for forgetting (S to R) in sleep (must be between 0 and 1).
        mem_span : int, optional
            Memory span for forgetting mechanism (must be >= 1, default: 10).

        Raises
        ------
        TypeError
            If any parameter is not of the correct type or out of valid range.
        """
        super().__init__(max_energy)
        self.literacy = literacy

        for name, value in zip(
            ['gamma', 'alpha', 'lam', 'phi', 'theta', 'mu', 'eta1', 'eta2'],
            [gamma, alpha, lam, phi, theta, mu, eta1, eta2]
        ):
            if not isinstance(value, (float, int)):
                raise TypeError(
                    f"{name} must be a float or int, got {
                        type(value).__name__}")

        gamma, alpha, lam, phi, theta, mu, eta1, eta2 = map(
            float, [gamma, alpha, lam, phi, theta, mu, eta1, eta2])

        if not isinstance(mem_span, int) or mem_span < 1:
            raise TypeError(
                f"mem_span must be an integer greater or equal to 1, got {mem_span}")

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

    def to_config_dict(self):
        """
        Convert SEIsIrR model parameters to a dictionary for configuration serialization.

        Returns
        -------
        dict
            Dictionary containing all model parameters as key-value pairs.
        """
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


class FolkSEIsIrR(AbstractFolk):
    """
    Agent class for the SEIsIrR rumor spreading model.

    This class represents individual agents in the SEIsIrR infection model,
    handling transitions between Susceptible (S), Exposed (E), Ignorant spreaders (Is),
    Intelligent spreaders (Ir), and Recovered/Stifler (R) states based on rumor
    credibility, literacy levels, and social interactions.
    """

    def __init__(self, id, home_address, max_energy, status):
        """
        Initialize a FolkSEIsIrR agent.

        Parameters
        ----------

        id : int
            Unique identifier for the agent.
        home_address : int
            Node index of the agent's home location.
        max_energy : int
            Maximum social energy for the agent.
        status : str
            Initial infection status ('S', 'E', 'Is', 'Ir', or 'R').
        """
        super().__init__(id, home_address, max_energy, status)

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        """
        Calculate the probability of status transition given contact with specific statuses.

        This method implements an energy-weighted inverse Bernoulli probability calculation
        for rumor spreading dynamics. The probability is scaled by the agent's current
        energy relative to their maximum energy, representing decreased social influence
        when tired.

        Parameters
        ----------
        folks_here : list of FolkSEIsIrR
            List of agents present at the same node.
        conversion_prob : float
            Base transition probability per contact.
        stats : list of str
            List of status types to consider for contact counting.

        Returns
        -------
        float
            Probability of at least one successful transition event.
        """
        num_contact = len(
            [folk for folk in folks_here if folk != self and folk.status in stats])
        return super().inverse_bernoulli(num_contact,
                                         conversion_prob * self.energy / self.max_energy)

    def interact(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        """
        Perform interactions with other agents and handle rumor spreading dynamics.

        Transition Rules
        ----------------
        - **Rule 1:** If the agent is Intelligent spreader ('Ir') and contacts Susceptible ('S') agents,
          they may transition to Susceptible ('S') based on `Ir2S` probability.

        - **Rule 2:** If the agent is Ignorant spreader ('Is') and contacts Susceptible ('S') agents,
          they may transition to either Exposed ('E') or Susceptible ('S') based on `Is2E` and `Is2S`
          probabilities respectively. The transition with higher probability is evaluated first.

        - **Rule 3:** If the agent is Exposed ('E'), they may transition to either Susceptible ('S')
          or Recovered ('R') based on `E2S` and `E2R` probabilities respectively. The transition
          with higher probability is evaluated first.

        - **Rule 4.1:** If the agent is Susceptible ('S'), they may transition to Recovered ('R')
          when contacting any other agents ('S', 'E', 'R') based on `S2R` probability.

        Parameters
        ----------
        folks_here : list of FolkSEIsIrR
            List of agents present at the same node.
        current_place_type : str
            Type of place where the interaction occurs.
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        model_params : SEIsIrRModelParameters
            Model parameters for the simulation.
        dice : float
            Random float for stochastic transitions.

        Returns
        -------

        None
        """
        # The rule numbers below are references to each rule defined in the literature of
        # SEIsIrR model

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
        """
        Perform end-of-day status transitions and forgetting mechanisms.

        This method handles the forgetting mechanism for Susceptible agents,
        representing the natural tendency to lose interest in rumors over time.

        Transition Rules
        ----------------
        - **Rule 4.2:** If the agent is Susceptible ('S'), they may transition to Recovered ('R')
          through forgetting if either:
          - They have been in 'S' status for longer than `mem_span` days, OR
          - A random draw is less than the forgetting probability `forget`

        Parameters
        ----------
        folks_here : list of FolkSEIsIrR
            List of agents present at the same node (not used, for interface compatibility).
        current_place_type : str
            Type of place where the agent is sleeping (not used, for interface compatibility).
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        model_params : SEIsIrRModelParameters
            Model parameters for the simulation.
        dice : float
            Random float for stochastic transitions.

        Returns
        -------
        None
        """
        super().sleep()
        if self.status == 'S':
            # Rule 4.2: Forgetting mechanism
            if model_params.mem_span <= self.status_step_streak or dice < model_params.forget:
                self.convert('R', status_dict_t)


class SEIsIrRModel(AbstractInfectionModel):
    """
    SEIsIrR rumor spreading model implementation.

    This class implements the Susceptible-Exposed-Ignorant spreader-Intelligent spreader-Recovered
    model for rumor spreading dynamics. The model considers rumor credibility, population literacy,
    and personality-based classification of spreaders.
    """

    def __init__(self, model_params, step_events=None):
        """
        Initialize the SEIsIrR model with specified parameters and events.

        Parameters
        ----------

        model_params : SEIsIrRModelParameters
            Configuration parameters for the SEIsIrR model.
        step_events : list of StepEvent, optional
            Custom step events for the simulation. If None, default events are used.
        """
        self.folk_class = FolkSEIsIrR
        self.all_statuses = (['S', 'E', 'Ir', 'Is', 'R'])
        self.infected_statuses = 'S'
        self.step_events = step_events
        super().__init__(model_params)

    def initialize_sim_population(self, town):
        """
        Initialize the simulation population and their initial status assignments.

        This method assigns initial statuses and home locations to all agents in the simulation.
        The population is divided between Ignorant spreaders (Is) and Intelligent spreaders (Ir)
        based on the literacy parameter, with initial rumor spreaders assigned to 'S' status.

        Parameters
        ----------
        town : Town
            The Town object representing the simulation environment.

        Returns
        -------
        tuple
            (folks, household_node_indices, status_dict_t0

            - folks : list of FolkSEIsIrR
                List of all agent objects created for the simulation.

            - household_node_indices : set
                Set of node indices where households are tracked.

            - status_dict_t0 : dict
                Dictionary with the initial count of each status at timestep 0.
        """
        num_pop, num_init_spreader, num_init_spreader_rd, folks, household_node_indices, assignments = super(
        ).initialize_sim_population(town)

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
