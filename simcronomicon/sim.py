from . import nx

import numpy as np
import random as rd
import h5py
import json
import os

from .compartmental_models import EventType


class Simulation:
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
                        probs = step_event.probability_func(distances)
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

    def _step(self, save_result):
        current_timestep = self.current_timestep + 1
        status_row = None
        indiv_folk_rows = []

        for step_event in self.step_events:
            # Copy and annotate the new state
            self.status_dicts.append(self.status_dicts[-1].copy())
            self.status_dicts[-1]['timestep'] = current_timestep
            self.status_dicts[-1]['current_event'] = step_event.name

            self._execute_event(step_event)

            if save_result:
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

        if save_result:
            return status_row, indiv_folk_rows
        return None, None

    def run(self, save_result=False, hdf5_path="simulation_output.h5"):
        """
        Run the simulation for the specified number of timesteps.

        If save_result is True, results are saved to an HDF5 file with the following structure:

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
        save_result : bool
            Whether to save the simulation results to an HDF5 file.
        hdf5_path : str
            Path to the output HDF5 file.

        Returns
        -------
        None
        """

        if save_result:

            with h5py.File(hdf5_path, "w") as h5file:
                # Save simulation metadata
                metadata_group = h5file.create_group("metadata")

                # Write simulation metadata (without town)
                sim_metadata = {
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
                            # TODO: If work add more
                        } for event in self.step_events
                    ]
                }
                sim_metadata_json = json.dumps(sim_metadata)
                metadata_group.create_dataset(
                    "simulation_metadata", data=np.bytes_(sim_metadata_json))

                # Write town metadata separately
                town_metadata = {
                    "origin_point": [
                        float(
                            self.town.point[0]),
                        float(
                            self.town.point[1])],
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
                    status_row, indiv_rows = self._step(save_result=True)

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

        else:
            for i in range(1, self.timesteps + 1):
                self._step(False)
                print("Step has been run", i)
                print("Status:",
                      {k: v for k,
                       v in self.status_dicts[-1].items() if k not in ('timestep',
                                                                       'current_event')})
                if sum(status_row[status]
                       for status in self.model.infected_statuses) == 0:
                    break
