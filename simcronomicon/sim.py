import json
import random as rd

import h5py
import numpy as np

from .compartmental_models import EventType


class Simulation:
    """
    Agent-based simulation engine for epidemic modeling in spatial networks.

    The Simulation class implements an agent-based modeling (ABM) framework that applies
    transition rules according to user-defined compartmental models. Agents move through
    a spatial town network, interact with each other and their environment, and undergo
    state transitions based on the rules defined in the chosen compartmental model.

    Purpose
    -------
    1. **Initialize Population**: Distribute agents across the town network according to
       user-specified parameters, including initial spreader locations and population size.

    2. **Agent Movement**: Move agents through the city during simulation timesteps based
       on step events that define mobility patterns and destination preferences.

    3. **Agent Interactions**: Enable agent-to-agent and agent-to-environment interactions
       at each location according to the rules defined in the compartmental model.

    4. **State Transitions**: Apply compartmental model transition rules (e.g., S→E→I→R)
       based on agent interactions, environmental factors, and time-dependent processes.

    5. **Temporal Dynamics**: Execute simulation in discrete timesteps, where each step
       consists of multiple events, and agents return home after each complete step.

    Simulation Workflow
    -------------------
    Each simulation timestep follows this pattern:

    1. **Event Execution**: For each step event in the current timestep:
       - Reset agent locations (clear previous positions)
       - Execute event-specific movement (DISPERSE) or actions (SEND_HOME)
       - Apply compartmental model rules for agent interactions
       - Record population status and individual agent states

    2. **Agent Movement**: During DISPERSE events:
       - Agents move to locations within their travel distance
       - Movement considers place type preferences and priority destinations
       - Probability functions can influence destination selection

    3. **Interactions**: At each active location:
       - Agents interact according to compartmental model rules
       - Environmental factors (place type) influence interaction outcomes
       - State transitions occur based on model-specific probabilities

    4. **Home Reset**: After all events, agents return to their home addresses

    Parameters
    ----------
    town : Town
        The Town object representing the spatial network with nodes (locations)
        and edges (travel routes) where the simulation takes place.
    compartmental_model : AbstractCompartmentalModel
        The compartmental model instance (e.g., SEIRModel, SEIQRDVModel) that
        defines agent states, transition rules, and interaction behaviors.
    timesteps : int
        Number of discrete timesteps to run the simulation.
    seed : bool, optional
        Whether to set random seeds for reproducible results (default: True).
    seed_value : int, optional
        Random seed value for reproducibility (default: 5710).

    Attributes
    ----------
    folks : list
        List of AbstractFolk (agent) objects representing the population.
    town : Town
        The spatial network where agents live and move.
    model : AbstractCompartmentalModel
        The compartmental model governing agent behavior and transitions.
    step_events : list
        Sequence of events that occur in each timestep.
    active_node_indices : set
        Set of town nodes currently occupied by agents.
    status_dicts : list
        Historical record of population status counts at each timestep.

    Raises
    ------
    ValueError
        If required place types for the chosen compartmental model are missing
        in the town data. This ensures model-specific locations (e.g., healthcare
        facilities for medical models) are available in the spatial network.

    Examples
    --------

    >>> # Create town and model
    >>> town = Town.from_point(point=[50.7753, 6.0839], dist=1000, 
    ...                        town_params=TownParameters(num_pop=1000, num_init_spreader=10))
    >>> model_params = SEIRModelParameters(max_energy=10, beta=0.3, sigma=5, gamma=7, xi=100)
    >>> model = SEIRModel(model_params)
    >>> 
    >>> # Run simulation
    >>> sim = Simulation(town, model, timesteps=100)
    >>> sim.run(hdf5_path="epidemic_simulation.h5")

    Notes
    -----

    - The simulation saves detailed results to HDF5 format, including population
      summaries and individual agent trajectories.

    - Agent energy levels affect movement capability and interaction potential.

    - Movement restrictions (e.g., quarantine) can limit agent mobility while
      still allowing interactions with visiting agents.

    - The simulation automatically terminates early if no infected agents remain.
    """

    def __init__(
            self,
            town,
            compartmental_model,
            timesteps,
            seed=True,
            seed_value=5710):
        """
        Initialize a Simulation instance.

        Parameters
        ----------
        town : Town
            The Town object representing the simulation environment.
        compartmental_model : AbstractCompartmentalModel
            The compartmental model instance (e.g., SEIRModel) to use for the simulation.
        timesteps : int
            Number of timesteps to run the simulation.
        seed : bool, optional
            Whether to set the random seed for reproducibility (default: True).
        seed_value : int, optional
            The value to use for the random seed (default: 5710).

        Raises
        ------
        ValueError
            If required place types for the model are missing in the town data of the given spatial area.
        """
        self.folks = []
        self.status_dicts = []
        self.town = town
        self.num_pop = town.town_params.num_pop
        self.model = compartmental_model
        self.model_params = compartmental_model.model_params
        self.step_events = compartmental_model.step_events
        self.current_timestep = 0
        self.timesteps = timesteps
        self.active_node_indices = set()
        self.nodes_list = list(self.town.town_graph.nodes)

        missing = [
            ptype for ptype in self.model.required_place_types if ptype not in self.town.found_place_types]
        if missing:
            raise ValueError(
                f"Missing required place types for this model in town data: {missing}. Please increase the radius of your interested area or change it.")

        if seed:
            rd.seed(seed_value)
            np.random.seed(seed_value)

        self.folks, self.household_node_indices, status_dict_t0 = self.model.initialize_sim_population(
            town)
        self.active_node_indices = self.household_node_indices.copy()

        self.status_dicts.append(status_dict_t0)

    def _reset_population_home(self):
        # Reset every person's current address to their home address
        # And reset the town graph
        # In addition, send everyone to sleep as well
        for i in range(self.num_pop):
            self.folks[i].address = self.folks[i].home_address
            self.town.town_graph.nodes[self.folks[i].home_address]["folks"].append(
                self.folks[i])

        self.num_pop = self.model.update_population(
            self.folks, self.town, self.household_node_indices, self.status_dicts[-1])
        # Simple list -> Shallow copy
        self.active_node_indices = self.household_node_indices.copy()

    def _disperse_for_event(self, step_event):
        for person in self.folks:
            if person.movement_restricted == False and person.alive and person.energy > 0:
                current_node = person.address
                candidates = []
                # Get the shortest path lengths from current_node to all other
                # nodes, considering edge weights

                if person.priority_place_type == []:
                    # If this agent doesn't have a place that they prioritize to go to, send them on their normal schedule
                    # like everybody else in the town.
                    # Get the nodes where the shortest path length is less than or
                    # equal to the possible travel distance
                    candidates = [
                        neighbor for neighbor in self.town.town_graph.nodes
                        if neighbor != current_node
                        # check if an edge exists
                        and self.town.town_graph[current_node].get(neighbor)
                        and self.town.town_graph[current_node][neighbor]['weight'] <= step_event.max_distance
                        and self.town.town_graph.nodes[neighbor]['place_type'] in step_event.place_types
                    ]
                else:
                    # If the agent has prioritized place types to go to
                    # Find the closest node with one of those place types,
                    # regardless of max_distance
                    min_dist = float('inf')
                    chosen_node = None
                    chosen_place_type = None
                    for node in self.town.town_graph.nodes:
                        node_place_type = self.town.town_graph.nodes[node]['place_type']
                        if node_place_type in person.priority_place_type:
                            if self.town.town_graph.has_edge(person.address, node):
                                dist = self.town.town_graph[person.address][node]['weight']
                            else:
                                continue
                            if dist < min_dist:
                                min_dist = dist
                                chosen_node = node
                                chosen_place_type = node_place_type

                    # If there exists a precomputed shortest path from the current location to this place,
                    # move agent to the prioritized place and remove that place
                    # from the priority list.
                    if chosen_node and chosen_place_type:
                        candidates = [chosen_node]
                        # Remove the visited place type from the priority list
                        person.priority_place_type.remove(chosen_place_type)

                if candidates:
                    if step_event.probability_func is not None:
                        distances = [
                            self.town.town_graph[current_node][neighbor]['weight']
                            for neighbor in candidates
                        ]
                        probs = step_event.probability_func(distances, person)
                        new_node = np.random.choice(candidates, p=probs)
                    else:
                        new_node = rd.choice(candidates)
                    # Update person's address
                    person.address = new_node
            self.town.town_graph.nodes[person.address]["folks"].append(person)

        # Reset active_node_indices and update consistently
        self.active_node_indices = set()
        for node in self.town.town_graph.nodes:
            if len(self.town.town_graph.nodes[node]) >= 2:
                self.active_node_indices.add(node)

    def _execute_event(self, step_event):
        # Regardless of the type of events, there are always movements.
        # To consistently update the list we have to
        # reset every house to empty first and fill in the folks at the nodes
        # after their address changes
        for i in range(len(self.town.town_graph.nodes)
                       ):
            self.town.town_graph.nodes[i]["folks"] = []

        for person in self.folks:
            person.clear_previous_event_effect()

        if step_event.event_type == EventType.SEND_HOME:
            for i in range(self.num_pop):
                if not self.folks[i].alive:
                    continue
                # Dummy folks_here and current_place_type since
                # this type of event is meant to relocate people and allow them some time to pass
                # for time-sensitive transition while they do that
                step_event.folk_action(
                    self.folks[i], None, None, self.status_dicts[-1], self.model_params, rd.random())
            if step_event.name == "end_day":
                self._reset_population_home()
        elif step_event.event_type == EventType.DISPERSE:
            # Move people through the town first
            self._disperse_for_event(step_event)
            for node in self.active_node_indices:  # Only iterate through active nodes
                # A person whose movement is restricted can stil be interact with other people who come to their location
                # e.g. delivery service comes into contact with people are
                # quarantined...
                folks_here = [folk for folk in self.town.town_graph.nodes[node]
                              ["folks"] if folk.alive and folk.energy > 0]
                current_place_type = self.town.town_graph.nodes[node]['place_type']
                for folk in folks_here:
                    step_event.folk_action(folk,
                                           folks_here,
                                           current_place_type,
                                           self.status_dicts[-1],
                                           self.model_params,
                                           rd.random())

    def _step(self):
        current_timestep = self.current_timestep + 1
        status_row = None
        indiv_folk_rows = []

        for step_event in self.step_events:
            # Copy and annotate the new state
            self.status_dicts.append(self.status_dicts[-1].copy())
            self.status_dicts[-1]['timestep'] = current_timestep
            self.status_dicts[-1]['current_event'] = step_event.name

            self._execute_event(step_event)

            # Record the latest summary
            status_row = self.status_dicts[-1].copy()

            # Record each individual's state
            for folk in self.folks:
                indiv_folk_rows.append({
                    'timestep': current_timestep,
                    'event': step_event.name,
                    'folk_id': folk.id,
                    'status': folk.status,
                    'address': folk.address
                })
        self.current_timestep = current_timestep

        return status_row, indiv_folk_rows

    def run(self, hdf5_path="simulation_output.h5", silent=False):
        """
        Run the simulation for the specified number of timesteps.

        The simulation results are saved to an HDF5 file with the following structure:

        .. code-block:: text

            simulation_output.h5
            ├── metadata
            │   ├── simulation_metadata   (JSON-encoded simulation metadata)
            │   └── town_metadata         (JSON-encoded town metadata)
            ├── status_summary
            │   └── summary               (dataset: structured array with timestep, current_event, and statuses)
            └── individual_logs
                └── log                   (dataset: structured array with timestep, event, folk_id, status, address)

        Parameters
        ----------
        hdf5_path : str
            Path to the output HDF5 file.

        Returns
        -------
        None
        """
        try:
            with h5py.File(hdf5_path, "w") as h5file:
                # Save simulation metadata
                metadata_group = h5file.create_group("metadata")

                # Write simulation metadata (without town)
                sim_metadata = {
                    'seed_enabled': hasattr(self, 'seed_value'),
                    'seed_value': getattr(self, 'seed_value', None),

                    'all_statuses': self.model.all_statuses,
                    'model_parameters': self.model_params.to_metadata_dict(),
                    'num_locations': len(self.town.town_graph.nodes),
                    'max_timesteps': self.timesteps,
                    'population': self.num_pop,
                    'step_events': [
                        {
                            'name': event.name,
                            'max_distance': event.max_distance,
                            'place_types': event.place_types,
                            'event_type': event.event_type.value,
                            'probability_func': event.probability_func.__name__ if event.probability_func else None,
                        } for event in self.step_events
                    ],
                }
                sim_metadata_json = json.dumps(sim_metadata)
                metadata_group.create_dataset(
                    "simulation_metadata", data=np.bytes_(sim_metadata_json))

                # Write town metadata separately
                town_metadata = {
                    "origin_point": [
                        float(
                            self.town.origin_point[0]),
                        float(
                            self.town.origin_point[1])],
                    "dist": self.town.dist,
                    "epsg_code": self.town.epsg_code,
                    "accommodation_nodes": list(
                        self.town.accommodation_node_ids)}
                town_metadata_json = json.dumps(town_metadata)
                metadata_group.create_dataset(
                    "town_metadata", data=np.bytes_(town_metadata_json))

                # Save initial status summary
                status_group = h5file.create_group("status_summary")
                status_dtype = [("timestep", 'i4'), ("current_event", 'S32')] + [
                    (status, 'i4') for status in self.model.all_statuses]
                status_data = []
                initial_status = self.status_dicts[-1]
                row = tuple([initial_status.get("timestep", 0),
                            bytes(str(initial_status.get("current_event", "")), 'utf-8')] +
                            [initial_status[status] for status in self.model.all_statuses])
                status_data.append(row)

                # Save initial individual logs
                indiv_group = h5file.create_group("individual_logs")
                folk_dtype = [("timestep", 'i4'), ("event", 'S32'),
                              ("folk_id", 'i4'), ("status", 'S8'), ("address", 'i4')]
                indiv_data = [
                    (0, b"", folk.id, bytes(folk.status, 'utf-8'), folk.address)
                    for folk in self.folks
                ]

                # Run simulation
                for i in range(1, self.timesteps + 1):
                    status_row, indiv_rows = self._step()

                    # Collect status row
                    row = tuple([
                        status_row["timestep"],
                        bytes(str(initial_status.get("current_event", "")), 'utf-8')
                    ] + [status_row[status] for status in self.model.all_statuses])
                    status_data.append(row)

                    # Collect individual rows
                    for row in indiv_rows:
                        indiv_data.append((
                            row["timestep"],
                            bytes(row["event"], 'utf-8'),
                            row["folk_id"],
                            bytes(row["status"], 'utf-8'),
                            row["address"]
                        ))

                    if not silent:
                        print("Step has been run", i)
                        print(
                            "Status:", {
                                k: v for k, v in status_row.items() if k not in (
                                    'timestep', 'current_event')})

                    if sum(status_row[status]
                            for status in self.model.infected_statuses) == 0:
                        break

                # Store final datasets
                status_group.create_dataset(
                    "summary", data=np.array(
                        status_data, dtype=status_dtype))
                indiv_group.create_dataset(
                    "log", data=np.array(
                        indiv_data, dtype=folk_dtype))
        except IOError as e:
            print(f"Error writing simulation output: {e}")
