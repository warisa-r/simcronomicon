from . import nx
from . import rd
from . import csv

import json

from .folk import Folk
from .visualize import _plot_status_data

class StepEvent():
    def __init__(self, step_freq, max_distance):
        self.step_freq = step_freq
        self.max_distance = max_distance
    def __repr__(self):
        return f"This even happens {self.step_freq} time(s) a step and each folk can travel up to {self.max_distance} to complete it."

class SEIsIrRModelParameters():
    def __init__(self, gamma, alpha, lam, phi, theta, mu, eta1, eta2, mem_span = 10):
        # Use the same parameter sets as the model notation but precalculate the conversion rate
        # since these are the same through out the simulation

        # Check if we have the right input type
        for name, value in zip(
            ['gamma', 'alpha', 'lam', 'phi', 'theta', 'mu', 'eta1', 'eta2'],
            [gamma, alpha, lam, phi, theta, mu, eta1, eta2]
        ):
            if not isinstance(value, (float, int)):
                raise TypeError(f"{name} must be a float or int, got {type(value).__name__}")
        
        # Cast to float
        gamma, alpha, lam, phi, theta, mu, eta1, eta2 = map(float, [gamma, alpha, lam, phi, theta, mu, eta1, eta2])

        if not isinstance(mem_span, int) or mem_span <= 1:
            raise ValueError(f"mem_span must be an integer greater than 1, got {mem_span}")

        # Store some parameters so that they can be recalled as simulation metadata later on 
        self.alpha = alpha
        self.gamma = gamma
        self.mu = mu
        gamma_alpha_lam = gamma * alpha * lam

        # We use number 2 to signify transition that happens because of interaction
        self.Is2E = (1-gamma) * gamma_alpha_lam
        self.Is2S = gamma_alpha_lam * mu
        self.Ir2S = gamma_alpha_lam
        self.E2S = theta
        self.E2R = phi
        self.S2R = eta1
        self.forget = eta2
        self.mem_span = mem_span

class Simulation:
    def __init__(self, town, model_params, timesteps, step_events = None):
        if not isinstance(model_params, SEIsIrRModelParameters):
            raise TypeError("Please defined parameters using SEIsIrRModelParameters!")

        self.folks = []
        self.folk_max_social_energy = town.town_params.max_social_energy
        self.status_dicts = []
        self.num_pop = town.town_params.num_pop
        self.town = town
        self.model_params = model_params
        self.current_timestep = 0
        self.timesteps = timesteps
        self.household_node_indices = set()
        self.active_node_indices = set()
        self.nodes_list = list(self.town.town_graph.nodes)

        # Validate step_events
        if step_events is None: # Use default step events
            hi_neighbour = StepEvent(2, 2)
            chore = StepEvent(1, 5)
            self.step_events = [hi_neighbour, chore]
        elif isinstance(step_events, StepEvent):
            self.step_events = [step_events]
        elif isinstance(step_events, list):
            if not all(isinstance(event, StepEvent) for event in step_events):
                raise TypeError("All elements in step_events must be StepEvent instances!")
            self.step_events = step_events
        else:
            raise TypeError("step_events must be a StepEvent or a list of StepEvent objects!")
        
        
        num_init_spreader = town.town_params.num_init_spreader
        
        num_Is = round(town.town_params.literacy * self.num_pop)
        num_Ir = self.num_pop - num_Is

        # Spreaders often originated from Ir type of folks first
        num_Ir -= num_init_spreader
        if num_Ir < 0: # Then some Is folks can become spreader too
            num_Is += num_Ir
            num_Ir = 0

        for i in range(self.num_pop):
            node = rd.choice(self.town.accommodation_node_ids)
            if i < num_init_spreader:
                folk = Folk(node, self.folk_max_social_energy, 'S')
            elif i >= num_init_spreader and i < num_init_spreader + num_Is:
                folk = Folk(node, self.folk_max_social_energy, 'Is')
            else:
                folk = Folk(node, self.folk_max_social_energy,'Ir')
            self.folks.append(folk)
            self.town.town_graph.nodes[node]['folks'].append(folk) # Account for which folks live where in the graph as well
        
            if len(self.town.town_graph.nodes[node]['folks']) == 2: # Track which node has a 'family' living in it
                self.household_node_indices.add(node)
        self.active_node_indices = self.household_node_indices.copy()

        # Keep track of the number of folks in each status
        status_dict_t = {'S': num_init_spreader, 'Is': num_Is, 'Ir': num_Ir, 'R': 0, 'E': 0}
        self.status_dicts.append(status_dict_t)
    
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
            possible_travel_distance = rd.randint(0, step_event.max_distance)
            
            current_node = person.address
            lengths = nx.single_source_shortest_path_length(self.town.town_graph, current_node, cutoff=possible_travel_distance)
            candidates = [node for node, dist in lengths.items() if dist == possible_travel_distance]
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
    
    def step(self):
        # Set up the new step
        self.status_dicts.append(self.status_dicts[-1].copy())
        
        # Events happen during the step
        for step_event in self.step_events:
            self.execute_social_event(step_event)

        # Town meeting
        if self.current_timestep % 14 == 0 or self.status_dicts[-1]['S'] / self.num_pop > 0.75:
            for folk in self.folks:
                if folk.social_energy > 0:
                    folk.interact(self.folks, self.status_dicts[-1], self.model_params, rd.random())
        
        # Everybody in the town goes home
        self.reset_population_home()
            
        self.current_timestep += 1

    def run(self, save_result=False, result_filename="simulation_results.csv", metadata_filename="sim_metadata.json"):
        if save_result:
            # Save metadata at the beginning
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
            }
            with open(metadata_filename, 'w') as f:
                json.dump(metadata, f, indent=4)

            # Write CSV while simulation runs
            with open(result_filename, mode='w', newline='') as result_file:
                fieldnames = ['timestep', 'S', 'Is', 'Ir', 'R', 'E']
                writer = csv.DictWriter(result_file, fieldnames=fieldnames)
                writer.writeheader()

                # Save initial state (t=0)
                initial_row = {'timestep': 0}
                initial_row.update(self.status_dicts[-1])
                writer.writerow(initial_row)

                for i in range(1, self.timesteps + 1):
                    print("Step has been run", i)
                    print("Status: ", self.status_dicts[-1])

                    self.step()
                    row = {'timestep': i}
                    row.update(self.status_dicts[-1])
                    writer.writerow(row)

                    if self.status_dicts[-1]['S'] == 0:
                        break

        else:
            # No saving to CSV
            for i in range(self.timesteps):
                print("Step has been run", i)
                print("Status: ", self.status_dicts[-1])
                self.step()
                if self.status_dicts[-1]['S'] == 0:
                    break

    def plot_status(self, status_type=None):
        timesteps = range(len(self.status_dicts))
        all_keys = ['S', 'Is', 'Ir', 'R', 'E']
        data = {key: [status[key] / self.num_pop for status in self.status_dicts] for key in all_keys}
        _plot_status_data(timesteps, data, status_type, ylabel="Density")