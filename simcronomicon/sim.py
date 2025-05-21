from . import nx

import numpy as np
import random as rd
import h5py
import json
import os

from .compartmental_models import EventType

class Simulation:
    def __init__(self, town, compartmental_model, timesteps, seed=True, seed_value=5710):
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

        if seed:
            rd.seed(seed_value)
        
        self.folks, self.household_node_indices, status_dict_t0 = self.model.initialize_sim_population(town)
        self.active_node_indices = self.household_node_indices.copy()

        self.status_dicts.append(status_dict_t0)
    
    def reset_population_home(self):
        self.active_node_indices = self.household_node_indices.copy() # Simple list -> Shallow copy
        
        for i in range(len(self.town.town_graph.nodes)): # Reset every house to empty first
            self.town.town_graph.nodes[i]['folks'] = []

        # Reset every person's current address to their home address
        # And reset the town graph
        # In addition, send everyone to sleep as well
        for i in range(self.num_pop):
            self.folks[i].address = self.folks[i].home_address
            self.town.town_graph.nodes[self.folks[i].home_address]['folks'].append(self.folks[i])

    def disperse_for_event(self, step_event):
        for person in self.folks:            
            current_node = person.address
            # Get the shortest path lengths from current_node to all other nodes, considering edge weights
            lengths = nx.single_source_dijkstra_path_length(self.town.town_graph, current_node, cutoff=step_event.max_distance)
    
            # Get the nodes where the shortest path length is less than or equal to the possible travel distance
            candidates = [node for node, dist in lengths.items() if dist <= step_event.max_distance 
                          and self.town.town_graph.nodes[node]['place_type'] in step_event.place_types]
            if candidates:
                new_node = rd.choice(candidates)

                # Track the number of folks at current node to see if this node becomes inactive later on
                num_folks_current_node = len(self.town.town_graph.nodes[current_node]['folks'])
                # Remove the person from their old address
                self.town.town_graph.nodes[current_node]['folks'].remove(person)

                num_folks_new_node = len(self.town.town_graph.nodes[new_node]['folks'])
                # Add person to new node
                self.town.town_graph.nodes[new_node]['folks'].append(person)
                # Update person's address
                person.address = new_node

                # Update active_node_indices
                if len(self.town.town_graph.nodes[current_node]['folks']) == 1 and num_folks_current_node == 2: 
                    # Node has become inactive after one person moves away
                    self.active_node_indices.remove(current_node)
                if len(self.town.town_graph.nodes[new_node]['folks']) == 2 and num_folks_new_node == 1:
                    # One person just move in and make this node 'active' -> interaction here is possible
                    self.active_node_indices.add(new_node)

    def execute_event(self, step_event):
        if step_event.event_type == EventType.SEND_HOME:
            self.reset_population_home()
            for i in range(self.num_pop):
                # Dummy [] folks_here
                step_event.folk_action(self.folks[i], [], self.status_dicts[-1], self.model_params, rd.random())
        elif step_event.event_type == EventType.DISPERSE:
            # Move people through the town first
            self.disperse_for_event(step_event)
            for node in self.active_node_indices:  # Only iterate through active nodes
                folks_here = self.town.town_graph.nodes[node]['folks']
                for folk in folks_here:
                    if folk.energy > 0:
                        step_event.folk_action(folk, folks_here, self.status_dicts[-1], self.model_params, rd.random())
    
    def step(self, save_result):
        current_timestep = self.current_timestep + 1
        status_row = None
        indiv_folk_rows = []

        for step_event in self.step_events:
            # Copy and annotate the new state
            self.status_dicts.append(self.status_dicts[-1].copy())
            self.status_dicts[-1]['timestep'] = current_timestep
            self.status_dicts[-1]['current_event'] = step_event.name

            self.execute_event(step_event)

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
        The output hierarchical structure is the following
        simulation_output.h5
        ├── metadata
        │   └── simulation_metadata         (JSON-encoded metadata)
        │   └── town_metadata               (bytes, JSON-encoded metadata)
        │
        ├── status_summary
        │   └── summary                     (dataset: structured array with timestep, current_event, and statuses)
        ├── individual_logs
        │   └── log                         (dataset: structured array with timestep, event, folk_id, status, address)
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
                            #TODO: If work add more
                        } for event in self.step_events
                    ]
                }
                sim_metadata_json = json.dumps(sim_metadata)
                metadata_group.create_dataset("simulation_metadata", data=np.bytes_(sim_metadata_json))

                # Write town metadata separately
                town_metadata = {
                    "origin_point": [float(self.town.point[0]), float(self.town.point[1])],
                    "dist": self.town.dist,
                    "epsg_code": self.town.epsg_code,
                    "id_map": {str(k): v for k, v in self.town.id_map.items()},
                    "accommodation_nodes": list(self.town.accommodation_node_ids)
                }
                town_metadata_json = json.dumps(town_metadata)
                metadata_group.create_dataset("town_metadata", data=np.bytes_(town_metadata_json))

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
                folk_dtype = [("timestep", 'i4'), ("event", 'S32'), ("folk_id", 'i4'), ("status", 'S8'), ("address", 'i4')]
                indiv_data = [
                    (0, b"", folk.id, bytes(folk.status, 'utf-8'), folk.address)
                    for folk in self.folks
                ]

                # Run simulation
                for i in range(1, self.timesteps + 1):
                    status_row, indiv_rows = self.step(save_result=True)

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
                    print("Status:", {k: v for k, v in status_row.items() if k not in ('timestep', 'current_event')})

                    if sum(status_row[status] for status in self.model.infected_statuses) == 0:
                        break

                # Store final datasets
                status_group.create_dataset("summary", data=np.array(status_data, dtype=status_dtype))
                indiv_group.create_dataset("log", data=np.array(indiv_data, dtype=folk_dtype))

        else:
            for i in range(1, self.timesteps + 1):
                self.step(False)
                print("Step has been run", i)
                print("Status:", {k: v for k, v in self.status_dicts[-1].items()
                                if k not in ('timestep', 'current_event')})
                if sum(status_row[status] for status in self.model.infected_statuses) == 0:
                    break
