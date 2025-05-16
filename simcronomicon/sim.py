from . import nx

import random as rd
import csv
import json

from .visualize import _plot_status_data

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
            self.folks[i].sleep(self.status_dicts[-1], self.model_params, rd.random())

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

    def execute_social_event(self, step_event):
        for i in range(step_event.step_freq):   
            # Move people through the town first
            self.disperse_for_event(step_event)
            for node in self.active_node_indices:  # Only iterate through active nodes
                folks_here = self.town.town_graph.nodes[node]['folks']
                for folk in folks_here:
                    if folk.social_energy > 0:
                        folk.interact(folks_here, self.status_dicts[-1], self.model_params, rd.random())
    
    def step(self, save_result, writer, indiv_folk_writer):
            current_timestep = self.current_timestep + 1
            for step_event in self.step_events:
                self.status_dicts.append(self.status_dicts[-1].copy())
                self.status_dicts[-1]['timestep'] = current_timestep
                self.status_dicts[-1]['current_event'] = step_event.name
            
                self.execute_social_event(step_event)
                if save_result:
                    writer.writerow(self.status_dicts[-1])
                    for folk in self.folks:
                        indiv_folk_writer.writerow({
                            'timestep': current_timestep,
                            'event': step_event.name,
                            'folk_id': folk.id,
                            'status': folk.status,
                            'address': folk.address
                        })

            # Everybody goes home (but we don't record that as a new status)
            self.reset_population_home()
            self.current_timestep = current_timestep

    def run(self, save_result=False, result_filename="simulation_log.csv", metadata_filename="sim_metadata.json"):
        writer = None
        indiv_folk_writer = None
        if save_result:
            metadata = {
                'model parameters': self.model_params.to_metadata_dict(),
                'num_locations': len(self.town.town_graph.nodes),
                'max_timesteps': self.timesteps,
                'population': self.num_pop,
                'step_events': [
                    {
                        'name': event.name,
                        'step_freq': event.step_freq,
                        'max_distance': event.max_distance,
                        'place_types': event.place_types,
                    } for event in self.step_events
                ],
            }
            with open(metadata_filename, 'w') as f:
                json.dump(metadata, f, indent=4)

            # Write CSV while simulation runs
            with open("individual_folks_log.csv", mode='w', newline='') as indiv_file, \
                open(result_filename, mode='w', newline='') as result_file:
                
                indiv_folk_writer = csv.DictWriter(indiv_file, fieldnames=['timestep', 'event', 'folk_id', 'status', 'address'])
                indiv_folk_writer.writeheader()
                for folk in self.folks:
                        indiv_folk_writer.writerow({
                            'timestep': 0,
                            'event': None,
                            'folk_id': folk.id,
                            'status': folk.status,
                            'address': folk.address
                        })

                fieldnames = ['timestep', 'current_event']
                for status in self.model.all_status:
                    fieldnames.append(status)
                writer = csv.DictWriter(result_file, fieldnames=fieldnames)
                writer.writeheader()

                writer.writerow(self.status_dicts[-1])

                # This loop has to be duplicated for the if else block
                # Since if we run it outside of this block, the .csv will be closed.
                for i in range(1, self.timesteps+1):
                    self.step(save_result, writer, indiv_folk_writer)
                    print("Step has been run", i)
                    print("Status:", {k: v for k, v in self.status_dicts[-1].items() if k not in ('timestep', 'current_event')})
                    if self.status_dicts[-1][self.model.infected_status] == 0:
                        break
        else:
            for i in range(1, self.timesteps+1):
                self.step(save_result, writer, indiv_folk_writer)
                print("Step has been run", i)
                print("Status:", {k: v for k, v in self.status_dicts[-1].items() if k not in ('timestep', 'current_event')})
                if self.status_dicts[-1][self.model.infected_status] == 0:
                    break