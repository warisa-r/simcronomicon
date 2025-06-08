import random as rd
from .step_event import StepEvent, EventType


class AbstractModelParameters:
    """
    Base class for compartmental model parameters.

    This abstract class defines the common interface for all compartmental model
    parameter classes. It provides basic energy management and requires subclasses
    to implement metadata serialization for simulation persistence.

    Parameters
    ----------

    max_energy : int
        The maximum energy for an agent. This number limits the maximum number 
        of events an agent can attend in a day.

    Attributes
    ----------

    max_energy : int
        Maximum social energy value for agents in the simulation.

    Methods
    -------

    to_metadata_dict()
        Abstract method that subclasses must implement to serialize parameters
        to a dictionary for saving simulation metadata.
    """

    def __init__(self, max_energy):
        """
        Initialize model parameters.

        Parameters
        ----------

        max_energy : int
            The maximum energy for an agent. This number limits the maximum number of events an agent can attend in a day.
        Raises
        ------

        AssertionError
            If max_energy is not a positive integer.
        """
        assert isinstance(
            max_energy, int) and max_energy > 0, "max_energy must be a positive integer!"
        self.max_energy = max_energy

    def to_metadata_dict(self):
        """
        Convert model parameters to a dictionary for metadata serialization.

        This abstract method must be implemented by subclasses to enable saving
        and loading of simulation configurations. The returned dictionary should
        contain all parameter values needed to reconstruct the model.

        Returns
        -------

        dict
            Dictionary containing all model parameters as key-value pairs.

        Raises
        ------

        NotImplementedError
            Always raised in the base class. Subclasses must override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement to_metadata_dict()")


class AbstractFolk:
    """
    Agent class representing individuals in the simulation.

    AbstractFolk objects represent individual agents that move through the town network,
    interact with other agents, and undergo status transitions according to
    compartmental model rules. Each agent has energy, status, location, and
    behavioral attributes that influence their participation in simulation events.

    Parameters
    ----------

    id : int
        Unique identifier for the agent.
    home_address : int
        Node index of the agent's home location in the town network.
    max_energy : int
        Maximum social energy. Limits the number of events an agent can attend daily.
    status : str
        Initial compartmental status of the agent (e.g., 'S', 'I', 'R').

    Attributes
    ----------

    id : int
        Unique agent identifier.
    home_address : int
        Home node index in the town network.
    address : int
        Current location node index (initially set to home_address).
    max_energy : int
        Maximum daily social energy.
    energy : int
        Current social energy (randomly initialized between 0 and max_energy).
    status : str
        Current compartmental status.
    status_step_streak : int
        Number of consecutive timesteps in current status.
    movement_restricted : bool
        Whether agent movement is restricted (e.g., quarantine).
    alive : bool
        Whether the agent is alive and active in the simulation.
    priority_place_type : list
        List of place types the agent prioritizes for visits.

    Methods
    -------

    convert(new_stat, status_dict_t)
        Change agent status and update population counts.
    inverse_bernoulli(contact_possibility, conversion_prob)
        Calculate probability of status transition given contacts and conversion rates.
    sleep()
        Reset energy and increment status streak (called at day end).
    """

    def __init__(self, id, home_address, max_energy, status):
        """
        Initialize a AbstractFolk agent.

        Parameters
        ----------

        id : int
            Unique identifier for the agent.
        home_address : int
            Node index of the agent's home. After performing all the events in a day, the agent will return to this address.
        max_energy : int
            Maximum social energy. This number limits the maximum number of events an agent can attend in a day.
            The agent can wake up with any random integer number of energy between 0 and max_energy. 
        status : str
            Initial status of the agent.
        """
        self.id = id
        self.home_address = home_address
        self.address = self.home_address
        self.max_energy = max_energy
        self.energy = rd.randint(0, max_energy)
        self.status = status
        self.status_step_streak = 0
        self.movement_restricted = False
        self.alive = True
        self.priority_place_type = []

    def convert(self, new_stat, status_dict_t):
        """
        Change the agent's status and update the status counts.

        Parameters
        ----------

        new_stat : str
            The new status to assign.
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.
        """
        assert self.status != new_stat, f"New status cannot be the same as the old status({new_stat})! Please review your transition rules!"
        assert status_dict_t[self.status] > 0, f"Attempting to decrement {self.status} below zero!"
        status_dict_t[self.status] -= 1
        status_dict_t[new_stat] += 1
        self.status = new_stat
        self.status_step_streak = 0

    def inverse_bernoulli(self, contact_possibility, conversion_prob):
        """
        Calculate the probability of status transition given contact possibility and conversion probability.
        This function is adapted from section 2.2 of
        Eden, M., Castonguay, R., Munkhbat, B., Balasubramanian, H., & Gopalappa, C. (2021).
        Agent-based evolving network modeling: A new simulation method for modeling low prevalence infectious diseases.
        Health Care Management Science, 24, 623–639. https://link.springer.com/article/10.1007/s10729-021-09558-0

        Parameters
        ----------

        contact_possibility : int
            Number of possible contacts.
        conversion_prob : float
            Probability of conversion per contact.

        Returns
        -------

        float
            Probability of at least one successful conversion.
        """
        if contact_possibility == 0:
            return 0
        else:
            return 1 - (1 - conversion_prob)**(contact_possibility)

    def sleep(self):
        """
        Reset the agent's energy and increment the status streak (called at the end of a day).
        """
        self.status_step_streak += 1
        self.energy = rd.randint(0, self.max_energy)  # Reset social energy


class AbstractCompartmentalModel:
    """
    Abstract base class for all compartmental epidemic models.

    This class provides the foundation for implementing compartmental models
    (e.g., SIR, SEIR, SEIQRDV) in agent-based simulations. It handles agent
    creation, step event management, population initialization, and defines
    the interface that all compartmental models must implement.

    Parameters
    ----------

    model_params : AbstractModelParameters
        Model-specific parameters object containing simulation configuration.

    Attributes
    ----------

    model_params : AbstractModelParameters
        Configuration parameters for the model.
    step_events : list of StepEvent
        Sequence of events that occur during each simulation timestep.
    infected_statuses : list
        List of status strings considered infectious (must be defined by subclasses).
    all_statuses : list
        Complete list of all possible agent statuses (must be defined by subclasses).
    required_place_types : set
        Set of place types required by the model (includes 'accommodation', 'commercial').
    folk_class : class
        The Folk class or subclass used to create agents (must be defined by subclasses).

    Methods
    -------

    create_folk(*args, **kwargs)
        Create a new Folk agent using the model's folk_class.

    initialize_sim_population(town)
        Initialize simulation population at the beginning of the simulation.

    update_population(folks, town, household_node_indices, status_dict_t)
        Update simulation population at the end of each timestep.

    Notes
    -----

    - Subclasses must define 'infected_statuses', 'all_statuses', and 'folk_class'
      before calling the parent constructor.
    - An 'end_day' event is automatically appended to step_events if not provided.
    - Default step_events include neighborhood greeting and commercial activities.
    """

    def __init__(self, model_params):
        """
        Initialize the abstract compartmental model.

        Parameters
        ----------

        model_params : AbstractModelParameters
            Model parameters object.
            Raises

        Raise
        ------

        NotImplementedError
            If subclass doesn't define required attributes (infected_statuses, all_statuses).
        TypeError
            If step_events contains invalid objects or folk_action methods are not callable.
        ValueError
            If the model has fewer than 3 different statuses.
        """
        self.model_params = model_params

        # If step_events is not set, use default events
        if not hasattr(self, "step_events") or self.step_events is None:
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
                        'commercial'])
            ]
        else:
            # Check that step_events is a StepEvent or list of StepEvent objects
            if isinstance(self.step_events, StepEvent):
                self.step_events = [self.step_events]
            elif isinstance(self.step_events, list):
                if not all(isinstance(ev, StepEvent) for ev in self.step_events):
                    raise TypeError(
                        "step_events must be a StepEvent or a list of StepEvent objects")
            else:
                raise TypeError(
                    "step_events must be a StepEvent or a list of StepEvent objects")

            for event in self.step_events:
                if not callable(event.folk_action):
                    raise TypeError(
                        f"folk_action in StepEvent '{event.name}' must be callable")
                # Print folk_class and the class of event.folk_action for debugging
                # Check if the function is a method of self.folk_class
                if not any(event.folk_action is func for name, func in vars(self.folk_class).items() if callable(func)):
                    raise TypeError(
                        f"folk_action in StepEvent '{event.name}' must be a method of the folk_class '{self.folk_class.__name__}'"
                    )

        # This is an important check and it will ONLY work when you define
        # some of the attributes before calling the abstract level constructor
        # See SEIsIrR for an example of how to write a constructor.
        required_attrs = {
            'infected_statuses': "Subclasses must define 'infected_statuses'.",
            'all_statuses': "Subclasses must define 'all_statuses' with at least 3 statuses."}

        for attr, message in required_attrs.items():
            if not hasattr(self, attr):
                raise NotImplementedError(message)

        if not hasattr(self, 'required_place_types'):
            self.required_place_types = set()
        self.required_place_types.update(['accommodation', 'commercial'])

        # Status is also actually plural of a status but for clarity that this is plural,
        # the software will stick with the commonly used statuses
        if len(self.all_statuses) < 3:
            raise ValueError(
                "A compartmental model must consist of at least 3 different statuses.")

        # Append end_day event to the existing day events given by the user
        end_day = StepEvent("end_day", self.folk_class.sleep)
        if not any(
            isinstance(ev, StepEvent) and getattr(
                ev, "name", None) == "end_day"
            for ev in self.step_events
        ):
            self.step_events.append(end_day)

    def create_folk(self, *args, **kwargs):
        """
        Create a new AbstractFolk agent using the model's folk_class.

        Returns
        -------

        AbstractFolk
            A new AbstractFolk agent instance of a given folk_class.
        """
        return self.folk_class(*args, **kwargs)

    def initialize_sim_population(self, town):
        """
        Initialize simulation population data structures and validate spreader configuration.

        This method sets up the basic data structures needed for population initialization
        and validates that the spreader configuration is valid. It prepares containers
        for agent creation and household assignment.

        Parameters
        ----------

        town : Town
            The town network where agents will be placed.

        Returns
        -------

        tuple
            Contains (num_pop, num_init_spreader, num_init_spreader_rd, folks, 
            household_node_indices, assignments) where:
            - num_pop : int - Total population size
            - num_init_spreader : int - Total number of initial spreaders
            - num_init_spreader_rd : int - Number of randomly placed spreaders
            - folks : list - Empty list for agent objects
            - household_node_indices : set - Empty set for household node tracking
            - assignments : list - Empty list for agent assignments

        Raises
        ------

        AssertionError
            If there are more spreader locations than total number of spreaders.

        Notes
        -----

        This method only initializes data structures and validates configuration.
        Actual agent creation and placement is handled by the Simulation class.
        """
        num_init_spreader_nodes = len(town.town_params.spreader_initial_nodes)
        assert town.town_params.num_init_spreader >= num_init_spreader_nodes, \
            "There cannot be more locations of the initial spreaders than the number of initial spreaders"

        num_init_spreader = town.town_params.num_init_spreader
        num_pop = town.town_params.num_pop
        num_init_spreader_rd = num_init_spreader - num_init_spreader_nodes

        folks = []
        household_node_indices = set()
        assignments = []

        return num_pop, num_init_spreader, num_init_spreader_rd, folks, household_node_indices, assignments

    def update_population(self, folks, town, household_node_indices, status_dict_t):
        """
        Update the simulation population (e.g., add or remove agents).

        This method is called at the end of each day. By default, it does nothing.
        Subclasses can override this method to implement population growth, death, or migration.

        Parameters
        ----------
        
        folks : list of AbstractFolk
            The current list of AbstractFolk agent objects in the simulation.
        town : Town
            The Town object representing the simulation environment.
        status_dict_t : dict
            Dictionary tracking the count of each status at the current timestep.

        Returns
        -------
        int
            An updated number of overall population
        """
        return len(folks)
