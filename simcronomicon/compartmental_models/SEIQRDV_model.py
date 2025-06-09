from .abstract_model import AbstractModelParameters, AbstractFolk, AbstractCompartmentalModel
from .step_event import *
import random as rd


class SEIQRDVModelParameters(AbstractModelParameters):
    """
    Model parameters for the SEIQRDV compartmental model.

    This class encapsulates all tunable parameters required for the SEIQRDV
    compartmental model, including epidemiological rates, probabilities, and
    healthcare system constraints. It validates parameter types and ranges
    upon initialization.
    """

    def __init__(self, max_energy, lam_cap, beta, alpha, gamma, delta, lam, rho, kappa, mu, hospital_capacity=float('inf')):
        """
        Initialize SEIQRDV model parameters and validate all inputs.

        Parameters
        ----------
        max_energy : int
            Maximum energy for each agent (must be a positive integer).
        lam_cap : float
            Rate of new population due to birth or migration (must be between 0 and 1).
        beta : float
            Transmission probability (must be between 0 and 1).
        alpha : float
            Vaccination rate (must be between 0 and 1).
        gamma : int
            Average latent time (must be a positive integer).
        delta : int
            Average days until the infected case is confirmed and quarantined (must be a positive integer).
        lam : int
            Average days until recovery for quarantined agents (must be a positive integer).
        rho : int
            Average days until death for quarantined agents (must be a positive integer).
        kappa : float
            Disease mortality rate (must be between 0 and 1).
        mu : float
            Natural background death rate (must be between 0 and 1).
        hospital_capacity : int or float, optional
            Average number of people a healthcare facility can vaccinate per event.
            Must be a positive integer or float('inf') for unlimited capacity (default: float('inf')).

        Raises
        ------
        TypeError
            If any parameter is not of the correct type or out of valid range.
        """
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
        """
        Convert SEIQRDV model parameters to a dictionary for metadata serialization.

        Returns
        -------
        dict
            Dictionary containing all model parameters as key-value pairs.
        """
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


class FolkSEIQRDV(AbstractFolk):
    """
    Agent class for the SEIQRDV compartmental model with vaccination and mortality dynamics.
    FolkSEIQRDV agents extend the basic AbstractFolk with two critical attributes for epidemic modeling: 
    `will_die` and `want_vaccine`. The `will_die` attribute is probabilistically set when an agent enters 
    quarantine and determines their eventual outcome (recovery or death), 
    reflecting the stochastic nature of disease severity. The `want_vaccine` attribute models vaccination-seeking behavior, 
    where susceptible agents can spontaneously decide to seek vaccination based on the model's `alpha` parameter, 
    creating realistic vaccine demand patterns. These agents exhibit complex behavioral dynamics including healthcare-seeking 
    movement (prioritizing healthcare facilities when `want_vaccine` is True), quarantine compliance 
    (restricted movement when infectious), and status-dependent interaction patterns. 
    The vaccination system implements a queue-based mechanism at healthcare facilities with capacity constraints, 
    ensuring fair vaccine distribution while maintaining epidemiological realism. 
    Additionally, agents undergo natural aging and mortality processes independent of disease status, allowing for 
    comprehensive population dynamics that include births, deaths, migration, and demographic changes throughout the simulation period.
    """

    def __init__(self, id, home_address, max_energy, status):
        """
        Initialize a FolkSEIQRDV agent with 2 more attributes than the standard AbstractFolk.
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
        folks_here : list of FolkSEIQRDV
            List of FolkSEIQRDV agents present at the same node.
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

        Transition Rules
        ----------------

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
        folks_here : list of FolkSEIQRDV
            List of FolkSEIQRDV agents present at the same node.
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
        Perform end-of-day updates and state transitions for this agent.

        This method handles all status progressions and transitions that occur at the end of a simulation day,
        including quarantine outcomes, recovery, death, infection progression, and vaccination planning.

        Transition Rules
        ----------------
        - **If the agent is in Quarantine ('Q'):**
            
            - If `will_die` is True and the agent has been in quarantine for `rho` days,
            the agent transitions to Dead ('D'), is marked as not alive, and `want_vaccine` is set to False.

            - If `will_die` is False and the agent has been in quarantine for `lam` days,
            the agent transitions to Recovered ('R') and their movement restriction is lifted.

        - **If the agent is Exposed ('E')** and has been exposed for `gamma` days,
        they transition to Infectious ('I').

        - **If the agent is Infectious ('I')** and has been infectious for `delta` days,
        their symptoms are confirmed and they must quarantine. They transition to Quarantine ('Q'),
        their movement is restricted, `want_vaccine` is set to False, and with probability `kappa`
        they are marked to die (`will_die = True`).

        - **If the agent is Susceptible ('S')** and a random draw is less than `alpha`,
        they plan to get vaccinated by setting `want_vaccine` to True.

        - **If the agent is Vaccinated ('V')**, their `want_vaccine` attribute is reset to False
        at the end of the day to ensure correct vaccine queue handling during the next day's events.

        - **For any agent with `want_vaccine = True`**, 'healthcare_facility' is added to their
        priority place types to guide movement toward vaccination sites.

        Parameters
        ----------
        
        folks_here : list of FolkSEIQRDV
            List of agents present at the same node (not used in this method, for interface compatibility).
        current_place_type : str
            Type of place where the agent is sleeping (not used in this method, for interface compatibility).
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        model_params : SEIQRDVModelParameters
            Model parameters for the simulation.
        dice : float
            Random float for stochastic transitions.

        Returns
        -------

        None

        Notes
        -----

        The `want_vaccine` attribute is reset to False in `sleep()` rather than immediately after
        vaccination in `interact()` to maintain queue integrity. If reset during `interact()`,
        it would modify the vaccination queue while agents are still being processed, potentially
        causing some agents to be skipped or processed incorrectly. Deferring the reset ensures
        fair and consistent vaccination queue processing.
        """
        super().sleep()
        if self.status == 'Q':
            if self.will_die:
                if self.status_step_streak == model_params.rho:
                    self.convert('D', status_dict_t)
                    self.want_vaccine = False
                    self.alive = False
            else:
                if self.status_step_streak == model_params.lam:
                    self.convert('R', status_dict_t)
                    self.movement_restricted = False
        elif self.status == 'E' and self.status_step_streak == model_params.gamma:
            self.convert('I', status_dict_t)
        elif self.status == 'I' and self.status_step_streak == model_params.delta:
            self.convert('Q', status_dict_t)
            self.movement_restricted = True
            self.want_vaccine = False
            if dice > model_params.kappa:
                self.will_die = True
        elif self.status == 'S':
            # We only apply the rate of planning to get vaccination on susceptible agents
            if model_params.alpha > dice:
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

        if self.want_vaccine:
                self.priority_place_type.append('healthcare_facility')

class SEIQRDVModel(AbstractCompartmentalModel):
    """
    SEIQRDV compartmental model implementation for epidemic simulation with vaccination.

    The SEIQRDV model extends the classic SEIR model by adding three additional compartments:
    Quarantine (Q), Death (D), and Vaccination (V). This model is particularly suited for
    simulating disease outbreaks where quarantine measures, vaccination campaigns, and
    mortality are important factors.
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
        """
        Initialize the simulation population and their assignments.

        This method assigns initial statuses and home locations to all agents in the simulation,
        including initial spreaders (both randomly assigned and those at specified nodes) and susceptible agents.
        It also creates agent objects, updates the town graph with agent assignments, and tracks household nodes.

        Parameters
        ----------
        town : Town
            The Town object representing the simulation environment.

        Returns
        -------
        tuple
            (folks, household_node_indices, status_dict_t0)

            - folks : list of FolkSEIQRDV
                List of all agent objects created for the simulation.

            - household_node_indices : set
                Set of node indices where households are tracked.

            - status_dict_t0 : dict
                Dictionary with the initial count of each status at timestep 0.
        """
        num_pop, num_init_spreader, num_init_spreader_rd, folks, household_node_indices, assignments = super(
        ).initialize_sim_population(town)

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
        folks : list of FolkSEIQRDV
            The current list of FolkSEIQRDV agent objects in the simulation.
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
