from . import nx
from . import rd
from . import plt

import csv
import json

from .folk import Folk

class DayEvent():
    def __init__(self, day_freq, max_distance):
        self.day_freq = day_freq
        self.max_distance = max_distance

class SimulationParameters():
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
        
        if mu >= 1-gamma: # Ensure that the conversion rate for Is to E is higher than Is to S
            raise ValueError(f"Steady Ignorant is less susceptible to becoming a spreader than just being exposed! \
                             Therefore, (1-gamma) < mu.")

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
    def __init__(self, town, params, timesteps):
        if not isinstance(params, SimulationParameters):
            raise TypeError("Please defined parameters using SimulationParameters!")

        self.folks = []
        self.status_dicts = []
        self.num_pop = len(town.town_graph.nodes())
        self.town = town
        self.params = params
        self.current_timestep = 0
        self.timesteps = timesteps

        hi_neighbour = DayEvent(1, 2)
        chore = DayEvent(1, 5)
        self.day_events = [hi_neighbour, chore]
        
        num_init_spreader = town.num_init_spreader
        
        num_Is = round(town.literacy * self.num_pop)
        num_Ir = self.num_pop - num_Is

        # Spreaders often originated from Ir type of folks first
        num_Ir -= num_init_spreader
        if num_Ir < 0: # Then some Is folks can become spreader too
            num_Is += num_Ir
            num_Ir = 0

        for i in range(self.num_pop):
            # A location is occupied only by one person
            node = self.select_random_node()
            if i < num_init_spreader:
                folk = Folk(node, 'S')
            elif i >= num_init_spreader and i < num_init_spreader + num_Is:
                folk = Folk(node, 'Is')
            else:
                folk = Folk(node, 'Ir')
            self.folks.append(folk)
            self.town.town_graph.nodes[node]['folk'].append(folk) # Account for which folks live where in the graph as well
        
        # Keep track of the number of folks in each status
        status_dict_t = {'S': num_init_spreader, 'Is': num_Is, 'Ir': num_Ir, 'R': 0, 'E': 0}
        self.status_dicts.append(status_dict_t)

    def select_random_node(self):
            """Select a random node that is unoccupied."""
            available_nodes = [node for node, data in self.town.town_graph.nodes(data=True) if len(data['folk']) == 0]
            return rd.choice(available_nodes)
    
    def everyone_go_home(self):
        # Reset every person's current address to their home address
        # And reset the town graph
        for i in range(self.num_pop):
            self.folks[i].address = self.folks[i].home_address
            self.town.town_graph.nodes[self.folks[i].home_address]['folk'] = [self.folks[i]]

    def move_people(self, day_event):
        for person in self.folks:
            possible_travel_distance = rd.randint(0, day_event.max_distance)
            
            current_node = person.address
            lengths = nx.single_source_shortest_path_length(self.town.town_graph, current_node, cutoff=possible_travel_distance)
            candidates = [node for node, dist in lengths.items() if dist == possible_travel_distance]
            if candidates:
                new_node = rd.choice(candidates)
                # Remove the person from their old address
                self.town.town_graph.nodes[current_node]['folk'].remove(person)
                # Add person to new node
                self.town.town_graph.nodes[new_node]['folk'].append(person)
                # Update person's address
                person.address = new_node

    def day_event_happen(self, day_event):
        for i in range(day_event.day_freq):   
            # Move people through the town first
            self.move_people(day_event)
            for node in self.town.town_graph.nodes():
                folks_here = self.town.town_graph.nodes[node]['folk']
                if len(folks_here) >= 2:
                    # Randomly sample 2 different people that are currently in the node
                    person1, person2 = rd.sample(folks_here, 2)
                    # Interaction is a two-way street
                    person1.interact(person2, self.status_dicts[-1], self.params, rd.random())
                    person2.interact(person1, self.status_dicts[-1], self.params, rd.random())
    
    def step(self):
        # Set up the new step
        self.status_dicts.append(self.status_dicts[-1].copy())
        
        # Event happens during the day
        for day_event in self.day_events:
            self.day_event_happen(day_event)

        if self.current_timestep % 14 or self.status_dicts[-1]['S'] / self.num_pop > 0.75:
            # Shuffle the list of people
            rd.shuffle(self.folks)

            # Pair people for interaction
            for i in range(0, len(self.folks) - 1, 2):
                person1 = self.folks[i]
                person2 = self.folks[i+1]
                person1.interact(person2, self.status_dicts[-1], self.params, rd.random())
                person2.interact(person1, self.status_dicts[-1], self.params, rd.random())
        
        # Everybody in the town go home after a long day
        self.everyone_go_home()

        # Everybody in the town sleeping
        for folk in self.folks:
            folk.sleep(self.status_dicts[-1], self.params, rd.random())
        self.current_timestep += 1

    def run(self):
        for i in range(self.timesteps):
            print("Step has been run", i)
            print("Status: ", self.status_dicts[-1])
            self.step()
            # Termination condition
            if self.status_dicts[-1]['S'] == 0:
                break

    def plot_status(self, status_type=None):
        """
        Plot the evolution of statuses over time.
        
        Parameters:
        - status_type: str or list of str or None
            If None, plot all statuses.
            If str, plot the given status.
            If list, plot the specified statuses.
        """
        timesteps = range(len(self.status_dicts))
        
        # Prepare data
        all_keys = ['S', 'Is', 'Ir', 'R', 'E']
        data = {key: [status[key] for status in self.status_dicts] for key in all_keys}

        # Figure out what to plot
        if status_type is None:
            keys_to_plot = all_keys
        elif isinstance(status_type, str):
            if status_type not in all_keys:
                raise ValueError(f"Invalid status_type '{status_type}'. Must be one of {all_keys}.")
            keys_to_plot = [status_type]
        elif isinstance(status_type, list):
            invalid = [k for k in status_type if k not in all_keys]
            if invalid:
                raise ValueError(f"Invalid status types {invalid}. Must be from {all_keys}.")
            keys_to_plot = status_type
        else:
            raise TypeError(f"status_type must be None, str, or list of str, got {type(status_type).__name__}.")

        # Plotting
        plt.figure(figsize=(10, 6))
        for key in keys_to_plot:
            plt.plot(timesteps, data[key], label=key)

        plt.xlabel('Timestep')
        plt.ylabel('Number of People')
        plt.title('Simulation Status Over Time')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def save_results(self, result_filename = "simulation_results.csv", metadata_filename = "metadata.json"):
        """Save simulation results to CSV and metadata to JSON."""
        assert self.current_timestep > 0
        # Save metadata
        metadata = {
            'parameters': {
                'alpha': self.params.alpha,
                'gamma': self.params.gamma,
                'phi': self.params.E2R,
                'theta': self.params.E2S,
                'mu': self.params.mu,
                'eta1': self.params.S2R,
                'eta2': self.params.forget,
                'mem_span': self.params.mem_span,
            },
            'network_type': self.town.network_type,
            'max_timesteps': self.timesteps,
            'population': self.num_pop,
        }
        with open(metadata_filename, 'w') as f:
            json.dump(metadata, f, indent=4)

        # Save results
        fieldnames = ['timestep', 'S', 'Is', 'Ir', 'R', 'E']
        with open(result_filename, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for timestep, status in enumerate(self.status_dicts):
                row = {'timestep': timestep}
                row.update(status)
                writer.writerow(row)