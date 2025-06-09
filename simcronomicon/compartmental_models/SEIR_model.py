from .abstract_model import AbstractModelParameters, AbstractFolk, AbstractCompartmentalModel
from .step_event import StepEvent, EventType
import random as rd


class SEIRModelParameters(AbstractModelParameters):
    """
    Model parameters for the SEIR compartmental model.

    This class encapsulates all tunable parameters required for the SEIR
    compartmental model, including transmission rates and duration parameters.
    It validates parameter types and ranges upon initialization.
    """

    def __init__(self, max_energy, beta, sigma, gamma, xi):
        """
        Initialize SEIR model parameters and validate all inputs.

        Parameters
        ----------
        max_energy : int
            Maximum energy for each agent (must be a positive integer).
        beta : float
            Transmission probability (must be between 0 and 1, exclusive).
        sigma : int
            Incubation duration in days (must be a positive integer).
        gamma : int
            Symptom duration in days (must be a positive integer).
        xi : int
            Immune duration in days (must be a positive integer).

        Raises
        ------
        TypeError
            If any parameter is not of the correct type or out of valid range.
        """
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
        """
        Convert SEIR model parameters to a dictionary for metadata serialization.

        Returns
        -------
        dict
            Dictionary containing all model parameters as key-value pairs.
        """
        return {
            'max_energy': self.max_energy,
            'beta': self.beta,
            'sigma': self.sigma,
            'gamma': self.gamma,
            'xi': self.xi
        }


class FolkSEIR(AbstractFolk):
    """
    Agent class for the SEIR model.

    This class represents individual agents in the SEIR compartmental model,
    handling transitions between Susceptible (S), Exposed (E), Infectious (I),
    and Recovered (R) states based on contact with infectious agents and
    time-based progression rules.
    """
    def __init__(self, id, home_address, max_energy, status):
        """
        Initialize a FolkSEIR agent.

        Parameters
        ----------
        id : int
            Unique identifier for the agent.
        home_address : int
            Node index of the agent's home location.
        max_energy : int
            Maximum social energy for the agent.
        status : str
            Initial compartmental status ('S', 'E', 'I', or 'R').
        """
        super().__init__(id, home_address, max_energy, status)

    def inverse_bernoulli(self, folks_here, conversion_prob, stats):
        """
        Calculate the probability of status transition given contact with infectious agents.

        This method implements the inverse Bernoulli probability calculation used
        in agent-based modeling to approximate the continuous ODE dynamics of
        compartmental models. It calculates the probability of infection based
        on the number of infectious contacts and transmission probability.

        Parameters
        ----------
        folks_here : list of FolkSEIR
            List of agents present at the same node.
        conversion_prob : float
            Base transmission probability per contact.
        stats : list of str
            List of infectious status types to consider.

        Returns
        -------
        float
            Probability of at least one successful transmission event.
        """
        num_contact = len(
            [folk for folk in folks_here if folk != self and folk.status in stats])
        # beta * I / N is the non-linear term that defines conversion
        # This inverse bernoulli function is an interpretation of the term
        # in agent-based modeling
        return super().inverse_bernoulli(num_contact, conversion_prob / len(folks_here))

    def interact(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        """
        Perform interactions with other agents and handle potential disease transmission.

        Transition Rules
        ----------------
        - If the agent is Susceptible ('S') and comes into contact with at least one
          Infectious ('I') agent, the probability of becoming Exposed ('E') is calculated
          using the inverse Bernoulli formula with transmission probability (`beta`).
          If this probability exceeds the random value `dice`, the agent transitions to Exposed.

        Parameters
        ----------
        folks_here : list of FolkSEIR
            List of agents present at the same node.
        current_place_type : str
            Type of place where the interaction occurs.
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        model_params : SEIRModelParameters
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

        self.energy -= 1

    def sleep(
            self,
            folks_here,
            current_place_type,
            status_dict_t,
            model_params,
            dice):
        """
        Perform end-of-day status transitions based on disease progression.

        This method handles the deterministic time-based transitions between
        compartmental states at the end of each simulation day.

        Transition Rules
        ----------------
        - If the agent is Exposed ('E') and has been exposed for `sigma` days,
          they transition to Infectious ('I').

        - If the agent is Infectious ('I') and has been infectious for `gamma` days,
          they transition to Recovered ('R').

        - If the agent is Recovered ('R') and has been recovered for `xi` days,
          they transition back to Susceptible ('S') (waning immunity).

        Parameters
        ----------
        folks_here : list of FolkSEIR
            List of agents present at the same node (not used, for interface compatibility).
        current_place_type : str
            Type of place where the agent is sleeping (not used, for interface compatibility).
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        model_params : SEIRModelParameters
            Model parameters for the simulation.
        dice : float
            Random float for stochastic transitions (not used for deterministic transitions).

        Returns
        -------

        None
        """
        super().sleep()
        if self.status == 'E' and self.status_step_streak == model_params.sigma:
            self.convert('I', status_dict_t)
        elif self.status == 'I' and self.status_step_streak == model_params.gamma:
            self.convert('R', status_dict_t)
        elif self.status == 'R' and self.status_step_streak == model_params.xi:
            self.convert('S', status_dict_t)


class SEIRModel(AbstractCompartmentalModel):
    """
    SEIR compartmental model implementation.

    This class implements the Susceptible-Exposed-Infectious-Recovered model
    for epidemic simulation. It includes waning immunity where recovered
    individuals return to susceptible status after a specified duration.
    """
    def __init__(self, model_params, step_events=None):
        """
        Initialize the SEIR model with specified parameters and events.

        Parameters
        ----------
        model_params : SEIRModelParameters
            Configuration parameters for the SEIR model.
        step_events : list of StepEvent, optional
            Custom step events for the simulation. If None, default events are used.
        """
        self.folk_class = FolkSEIR
        self.all_statuses = (['S', 'E', 'I', 'R'])
        self.infected_statuses = ['I', 'E']
        self.required_place_types = set(
            ['workplace', 'education', 'religious'])
        self.step_events = step_events
        super().__init__(model_params)

    def initialize_sim_population(self, town):
        """
        Initialize the simulation population and their initial status assignments.

        This method assigns initial statuses and home locations to all agents in the simulation,
        including initial spreaders (both randomly assigned and those at specified nodes) and
        susceptible agents. It creates agent objects, updates the town graph with agent
        assignments, and tracks household nodes.

        Parameters
        ----------
        town : Town
            The Town object representing the simulation environment.

        Returns
        -------
        tuple
            (folks, household_node_indices, status_dict_t0)

            - folks : list of FolkSEIR
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
            folks.append(folk)
            town.town_graph.nodes[node]["folks"].append(folk)
            if len(town.town_graph.nodes[node]["folks"]) == 2:
                household_node_indices.add(node)

        status_dict_t0 = {
            'current_event': None,
            'timestep': 0,
            'S': num_pop - num_init_spreader,
            'E': 0,
            'I': num_init_spreader,
            'R': 0
        }
        return folks, household_node_indices, status_dict_t0
