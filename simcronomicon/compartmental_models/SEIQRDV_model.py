from .abstract_model import AbstractModelParameters, Folk, AbstractCompartmentalModel
from .step_event import *
import random as rd


class SEIQRDVModelParameters(AbstractModelParameters):
    """
    Model parameters for the SEIQRDV compartmental model.

    Parameters
    ----------
    max_energy : int
        Maximum energy for each agent.
    lam_cap : float
        Rate of new population due to birth or migration (0 <= lam_cap <= 1).
    beta : float
        Transmission probability (0 <= beta <= 1).
    alpha : float
        Vaccination rate (0 <= alpha <= 1).
    gamma : int
        Average latent time (days).
    delta : int
        Average days until the infected case is confirmed and quarantined.
    lam : int
        Average days until recovery for quarantined agents.
    rho : int
        Average days until death for quarantined agents.
    kappa : float
        Disease mortality rate (0 <= kappa <= 1).
    mu : float
        Natural background death rate (0 <= mu <= 1).
    hospital_capacity : int or float
        Average number of people a healthcare facility can vaccinate per event.
        Should be a positive integer or float('inf') for unlimited capacity.

    Raises
    ------
    TypeError
        If any parameter is not of the correct type or out of valid range.
    """

    def __init__(self, max_energy, lam_cap, beta, alpha, gamma, delta, lam, rho, kappa, mu, hospital_capacity=float('inf')):
        for name, value in zip(
            ['lam_cap', 'beta', 'alpha', 'gamma', 'delta', 'lam',
                'rho', 'kappa', 'mu', 'hospital_capacity'],
            [lam_cap, beta, alpha, gamma, delta, lam,
                rho, kappa, mu, hospital_capacity]
        ):
            if name in ['lam_cap', 'beta', 'kappa', 'alpha', 'mu']:
                if not isinstance(
                        value, (float, int)) or not (
                        0 <= value <= 1):
                    raise TypeError(
                        f"{name} must be a float between 0 and 1!")
            elif name == 'hospital_capacity':
                if not isinstance(value, int) and value != float('inf'):
                    raise TypeError(
                        f"{name} must be a positive integer or a value of infinity, got {value}")
            else:
                if not isinstance(value, int) or value <= 0:
                    raise TypeError(
                        f"{name} must be a positive integer, got {value}")

        super().__init__(max_energy)

        # Adapted from https://www.mdpi.com/2227-7390/9/6/636

        # Rate of new population due to birth or migration etc.
        self.lam_cap = lam_cap
        self.beta = beta  # Transimssion probability
        self.alpha = alpha  # Vaccination rate
        self.gamma = gamma  # Average latent time
        self.delta = delta  # Average day until the infected case got confirmed and quarantined
        self.lam = lam  # Average day until recovery
        self.rho = rho  # Average day until death
        self.kappa = kappa  # Disease mortality rate
        self.mu = mu  # Natural back ground death rate
        # Average number of people a healthcare facility can contain
        self.hospital_capacity = hospital_capacity

    def to_metadata_dict(self):
        return {
            'max_energy': self.max_energy,
            'lam_cap': self.lam_cap,
            'beta': self.beta,
            'alpha': self.alpha,
            'gamma': self.gamma,
            'delta': self.delta,
            'lam': self.lam,
            'rho': self.rho,
            'kappa': self.kappa,
            'mu': self.mu,
            'hospital_capacity': self.hospital_capacity
        }


class FolkSEIQRDV(Folk):
    """
    Agent class for the SEIQRDV model.

    Attributes
    ----------
    will_die : bool
        Whether the agent is destined to die if quarantined (set during transition to 'Q').
    want_vaccine : bool
        Whether the agent wants to get vaccinated and will seek a healthcare facility.

    Methods
    -------
    inverse_bernoulli(folks_here, conversion_prob, stats)
        Calculates the probability of status transition given contact with specific statuses.
    interact(folks_here, current_place_type, status_dict_t, model_params, dice)
        Handles agent interactions and possible state transitions (exposure, vaccination).
    sleep(folks_here, current_place_type, status_dict_t, model_params, dice)
        Handles end-of-day transitions (progression, quarantine, death, recovery, vaccination planning).
    """

    def __init__(self, id, home_address, max_energy, status):
        """
        Initialize a FolkSEIQRDV agent with 2 more attributes than the standard Folk.
        The first one being will_die which plays a role in determining if the infected agent
        will pass away or not. The second one, want_vaccine, signifies the agent's will to
        get vaccinated. An agent with this attribute == True will try to get vaccinated at
        their nearest healthcare facility.

        Parameters
        ----------
        id : int
            Unique identifier for the agent.
        home_address : int
            Node index of the agent's home.
        max_energy : int
            Maximum social energy.
        status : str
            Initial status of the agent.
        """
        super().__init__(id, home_address, max_energy, status)
        self.will_die = False
        self.want_vaccine = False

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        """
        Calculate the probability of status transition given contact with specific statuses.

        Parameters
        ----------
        folks_here : list of Folk
            List of Folk agents present at the same node.
        conversion_prob : float
            Probability of conversion per contact.
        stats : list of str
            List of statuses to consider as infectious.

        Returns
        -------
        float
            Probability of at least one successful conversion.
        """
        # beta * I / N is the non-linear term that defines conversion
        # This inverse bernoulli function is an interpretation of the term
        # in agent-based modeling
        num_contact = len(
            [folk for folk in folks_here if folk != self and folk.status in stats])
        return super().inverse_bernoulli(num_contact, conversion_prob / len(folks_here))

    def interact(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        """
        Perform interaction with other agents in the area and the environment for this agent.

        ## Transition Rules
        - If the agent is Susceptible ('S'):
            - If the agent comes into contact with at least one Infectious ('I') agent at the same node,
            the probability of becoming Exposed ('E') is calculated using the inverse Bernoulli formula with
            the transmission probability (`beta`). If this probability exceeds the random value `dice`,
            the agent transitions to Exposed ('E').
        - If the agent is Susceptible ('S'), wants a vaccine, and is at a healthcare facility:
            - If the number of agents at the facility wanting a vaccine is less than the hospital capacity,
            the agent transitions to Vaccinated ('V') and `want_vaccine` is set to False.

        Parameters
        ----------
        folks_here : list of Folk
            List of Folk agents present at the same node.
        current_place_type : str
            The type of place where the interaction occurs.
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        model_params : SEIQRDVModelParameters
            Model parameters for the simulation.
        dice : float
            Random float for stochastic transitions.

        Returns
        -------
        None
        """
        # When a susceptible person comes into contact with an infectious person,
        # they have a likelihood to become exposed to the disease
        if self.status == 'S' and self.inverse_bernoulli(
                folks_here, model_params.beta, ['I']) > dice:
            self.convert('E', status_dict_t)

        if current_place_type == 'healthcare_facility':
            # Vaccine is only effective for susceptible people but anyone who wants it can queue up
            want_vaccine_list = [
                folk for folk in folks_here if folk.want_vaccine]
            if self in want_vaccine_list and self.status == 'S':
                idx = want_vaccine_list.index(self)
                if idx < model_params.hospital_capacity:
                    self.convert('V', status_dict_t)

    def sleep(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        """
        Perform end-of-day updates for this agent.

        Handles transitions for quarantine, recovery, death, infection, and vaccination planning.

        ## Transition Rules
        - If the agent is in Quarantine ('Q'):
            - If `will_die` is True and the agent has been in quarantine for `rho` days,
            the agent transitions to Dead ('D') and is marked as not alive.
            - If `will_die` is False and the agent has been in quarantine for `lam` days,
            the agent transitions to Recovered ('R') and their movement is restricted.
        - If the agent is Exposed ('E') and has been exposed for `gamma` days,
        they transition to Infectious ('I').
        - If the agent is Infectious ('I') and has been infectious for `delta` days, their symptoms get confirmed and they
        must quarantine. They transition to Quarantine ('Q'), their movement is restricted, and with probability `kappa` 
        they are marked to die (`will_die = True`).
        - If the agent is Susceptible ('S') and a random draw is less than `alpha`,
        they plan to get vaccinated by adding 'healthcare_facility' to their priority places and setting `want_vaccine` to True.

        Parameters
        ----------
        folks_here : list of Folk
            *Just a placeholder here.* List of Folk agents present at the same node.
        current_place_type : str
            *Just a placeholder here.* The type of place where the agent is sleeping.
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        model_params : SEIQRDVModelParameters
            Model parameters for the simulation.
        dice : float
            Random float for stochastic transitions.

        Returns
        -------
        None
        """
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
        elif self.status == 'V':
            # We set self.want_vaccine = False here (in sleep) instead of immediately in interact
            # because if we set it in interact (right after conversion), it would change the order of the want_vaccine_list
            # while we are still looping through folks at the healthcare facility in the same event.
            # This could cause some agents to be skipped or processed incorrectly, since the list of agents wanting a vaccine
            # would be modified during iteration. By deferring the reset of want_vaccine to the end-of-day (sleep),
            # we ensure that all agents who wanted a vaccine at the start of the event are considered for vaccination,
            # and the event logic remains consistent and fair.
            self.want_vaccine = False


class SEIQRDVModel(AbstractCompartmentalModel):
    """
    SEIQRDV compartmental model implementation.

    Parameters
    ----------
    model_params : SEIQRDVModelParameters
        Model parameters for the simulation.
    step_events : list of StepEvent, optional
        List of step events for the simulation.

    Methods
    -------
    initialize_sim_population(town)
        Initializes the simulation population and their assignments.
    update_population(folks, town, household_node_indices, status_dict_t)
        Updates the population at the end of each day (natural deaths and births/migration).
    """

    def __init__(self, model_params, step_events=None):
        self.folk_class = FolkSEIQRDV
        self.all_statuses = (['S', 'E', 'I', 'Q', 'R', 'D', 'V'])
        self.infected_statuses = ['I', 'E', 'Q']
        self.required_place_types = set(
            ['healthcare_facility'])
        self.step_events = step_events
        super().__init__(model_params)

    def initialize_sim_population(self, town):
        num_pop, num_init_spreader, num_init_spreader_rd, folks, household_node_indices, assignments = super(
        )._initialize_sim_population(town)

        # Randomly assign initial spreaders (not on specified nodes)
        for i in range(num_init_spreader_rd):
            node = rd.choice(town.accommodation_node_ids)
            assignments.append((node, 'I'))

        # Assign the rest as susceptible
        for i in range(num_pop - num_init_spreader):
            node = rd.choice(town.accommodation_node_ids)
            assignments.append((node, 'S'))

        # Assign initial spreaders to specified nodes
        for node in town.town_params.spreader_initial_nodes:
            assignments.append((node, 'I'))

        # Create folks and update graph/node info
        for i, (node, status) in enumerate(assignments):
            folk = self.create_folk(
                i, node, self.model_params.max_energy, status)
            if status == 'S' and rd.random() < self.model_params.alpha:
                folk.priority_place_type.append('healthcare_facility')
                folk.want_vaccine = True
            folks.append(folk)
            town.town_graph.nodes[node]["folks"].append(folk)
            if len(town.town_graph.nodes[node]["folks"]) == 2:
                household_node_indices.add(node)

        status_dict_t0 = {
            'current_event': None,
            'timestep': 0,
            'S': num_pop - num_init_spreader,
            'E': 0,
            'Q': 0,
            'I': num_init_spreader,
            'R': 0,
            'D': 0,
            'V': 0
        }
        return folks, household_node_indices, status_dict_t0

    def update_population(self, folks, town, household_node_indices, status_dict_t):
        """
        Update the simulation population at the end of each day.

        This function performs two main operations:
        1. **Natural Deaths:** Iterates through all currently alive agents and, with probability `mu` (the natural death rate), transitions them to the 'D' (Dead) status and marks them as not alive.
        2. **Population Growth:** Calculates the number of possible new agents to add based on the current alive population and the parameter `lam_cap` (birth/migration rate). For each new agent:
            - Randomly selects an accommodation node as their home.
            - Randomly assigns a status from all possible statuses except 'D' (Dead) and 'Q' (Quarantine).
            - Adds the new agent to the simulation, updates the status count, and tracks their household node.

        Parameters
        ----------
        folks : list of Folk
            The current list of Folk agent objects in the simulation.
        town : Town
            The Town object representing the simulation environment.
        household_node_indices : set
            Set of node indices where households are tracked.
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.

        Returns
        -------
        int
            The updated total number of agents in the simulation after deaths and births/migration.
        """

        num_current_pop = len(folks)
        folks_alive = [folk for folk in folks if folk.alive]
        num_current_folks = len(folks_alive)
        # Account for death by natural causes here
        for folk in folks_alive:
            if rd.random() < self.model_params.mu:
                folk.convert('D', status_dict_t)
                folk.alive = False
        num_possible_new_folks = num_current_folks * self.model_params.lam_cap
        if num_possible_new_folks > 1:
            num_possible_new_folks = round(num_possible_new_folks)
            for i in range(num_possible_new_folks):
                node = rd.choice(town.accommodation_node_ids)
                stat = rd.choice(
                    [s for s in self.all_statuses if s not in ('D', 'Q')])
                folk = self.create_folk(
                    num_current_pop + i, node, self.model_params.max_energy, stat)

                status_dict_t[stat] += 1
                folks.append(folk)
                # Account for which folks live where in the graph as well
                town.town_graph.nodes[node]["folks"].append(folk)

                # Track which node has a 'family' living in it
                if len(town.town_graph.nodes[node]["folks"]) == 2:
                    # Add operation and set() data structure ensures that there is no duplicate
                    household_node_indices.add(node)

        return len(folks)
