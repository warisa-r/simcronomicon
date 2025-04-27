from . import nx
from . import rd
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

        # We use number 2 to signify transition that happens because of interaction
        gamma_alpha_lam = gamma * alpha * lam
        self.Is2E = (1-gamma) * gamma_alpha_lam
        assert 1-gamma > mu # Ensure that the conversion rate for Is to E is lower than Is to S
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
        chore = DayEvent(3, 10)
        self.day_events = [hi_neighbour, chore]
        
        num_init_spread = town.num_init_spread
        
        num_Ir = round(town.literacy * self.num_pop)
        num_Is = self.num_pop - num_Ir

        # Spreaders often originated from Ir type of folks first
        num_Ir -= num_init_spread
        if num_Ir < 0: # Then some Is folks can become spreader too
            num_Is += num_Ir
            num_Ir = 0
        for i in range(self.num_pop):
            # A location is occupied only by one person
            if i < num_init_spread:
                folk = Folk(i, 'S')
            elif i >= num_init_spread and i < num_init_spread + num_Is:
                folk = Folk(i, 'Is')
            else:
                folk = Folk(i, 'Ir')
            self.folks.append(folk)
            self.town.town_graph.nodes[i]['folk'].append(folk) # Account for which folks live where in the graph as well
        
        # Keep track of the number of folks in each status
        status_dict_t = {'S': num_init_spread, 'Is': num_Is, 'Ir': num_Ir, 'R': 0, 'E': 0}
        self.status_dicts.append(status_dict_t)

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
        self.status_dicts.append(self.status_dicts[-1])
        
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

        # End day with everybody in the town sleeping
        for folk in self.folks:
            folk.sleep(self.status_dicts[-1], self.params, rd.random())
        self.current_timestep += 1

    def run(self):
        for i in range(self.timesteps):
            self.step()
        #TODO: Print summary

    def show_step(self, i):
        if i > self.timesteps - 1:
            print("Your specified time step exceeds the maximum time step of the simulation run.")