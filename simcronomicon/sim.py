from . import nx

import random as rd
import csv
import json

from .visualize import _plot_status_data

class Simulation:
    def __init__(self, town, compartmental_model, timesteps, step_events = None):

        self.folks = []
        self.folk_max_social_energy = town.town_params.max_social_energy
        self.status_dicts = []
        self.num_pop = town.town_params.num_pop
        self.town = town
        self.model = compartmental_model
        self.model_params = compartmental_model.model_params
        self.step_events = compartmental_model.step_events
        self.current_timestep = 0
        self.timesteps = timesteps
        self.active_node_indices = set()
        self.nodes_list = list(self.town.town_graph.nodes)

        num_init_spreader = town.town_params.num_init_spreader
        
        self.folks, self.household_node_indices, status_dict_t0 = self.model.initialize_sim_population(self.num_pop, num_init_spreader, town)
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
    
    def step(self, save_result, writer):
            current_timestep = self.current_timestep + 1
            for step_event in self.step_events:
                self.status_dicts.append(self.status_dicts[-1].copy())
                self.status_dicts[-1]['timestep'] = current_timestep
                self.status_dicts[-1]['current_event'] = step_event.name
            
                self.execute_social_event(step_event)
                if save_result and writer:
                    writer.writerow(self.status_dicts[-1])

            # Everybody goes home (but we don't record that as a new status)
            self.reset_population_home()
            self.current_timestep = current_timestep

    def run(self, save_result=False, result_filename="simulation_results.csv", metadata_filename="sim_metadata.json"):
        writer = None
        if save_result:
            #TODO: Generalize this
            metadata = {
                        'model parameters': {
                            'alpha': self.model_params.alpha,
                            'gamma': self.model_params.gamma,
                            'phi': self.model_params.E2R,
                            'theta': self.model_params.E2S,
                            'mu': self.model_params.mu,
                            'eta1': self.model_params.S2R,
                            'eta2': self.model_params.forget,
                            'mem_span': self.model_params.mem_span,
                        },
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
            with open(result_filename, mode='w', newline='') as result_file:
                fieldnames = ['timestep', 'current_event']
                for status in self.model.all_status:
                    fieldnames.append(status)
                writer = csv.DictWriter(result_file, fieldnames=fieldnames)
                writer.writeheader()

                # Save initial state (t=0)
                writer.writerow(self.status_dicts[-1])
                # This loop has to be duplicated for the if else block
                # Since if we run it outside of this block, the .csv will be closed.
                for i in range(1, self.timesteps+1):
                    self.step(save_result, writer)
                    print("Step has been run", i)
                    print("Status:", {k: v for k, v in self.status_dicts[-1].items() if k not in ('timestep', 'current_event')})
                    if self.status_dicts[-1]['S'] == 0:
                        break
        else:
            for i in range(1, self.timesteps+1):
                self.step(save_result, writer)
                print("Step has been run", i)
                print("Status:", {k: v for k, v in self.status_dicts[-1].items() if k not in ('timestep', 'current_event')})
                if self.status_dicts[-1]['S'] == 0:
                    break

    def plot_status(self, status_type=None):
        timesteps = range(len(self.status_dicts))
        all_keys = self.model.all_status
        data = {key: [status[key] / self.num_pop for status in self.status_dicts] for key in all_keys}
        _plot_status_data(timesteps, data, status_type, ylabel="Density")