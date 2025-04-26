from . import nx
from . import rd
from .folk import Folk

class DayEvent():
    def __init__(self, day_freq, max_distance=float('inf')):
        self.day_freq = day_freq
        self.max_distance = max_distance
    def happen(self, person, sim):
        town = sim.town
        people = sim.people
        address = person.address
        if self.max_distance == float('inf'):
            # All other nodes in the graph
            neighbors = [node for node in town.nodes if node != address]
        else:
            # BFS: only nodes within `max_distance` hops
            lengths = nx.single_source_shortest_path_length(town, source=address, cutoff=self.max_distance)
            neighbors = [node for node in lengths if node != address]

        for _ in range(self.day_freq):
            if person.social_energy > 0:
                if neighbors:
                    chosen_address = rd.choice(neighbors)
                    people_at_address = [p for p in people if p.address == chosen_address]
                    if len(people_at_address) > 1:
                        chosen_person = rd.choice(people_at_address)
                    else:
                        chosen_person = people_at_address[0]
                    if chosen_person.social_energy > 0:
                        status_dict_t = sim.status_dicts[-1]
                        # Interaction is a two-way street!
                        person.interact(chosen_person, status_dict_t, sim.params, rd.random())
                        chosen_person.interact(person, status_dict_t, sim.params, rd.random())



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

class Simulation:
    def __init__(self, town, params, timesteps):
        if not isinstance(params, SimulationParameters):
            raise TypeError("Please defined parameters using SimulationParameters!")

        self.folks = []
        self.status_dicts = []
        self.num_pop = len(town.town_graph.nodes())
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
            if i < num_init_spread:
                folk = Folk(i, 'S')
            elif i >= num_init_spread and i < num_init_spread + num_Is:
                folk = Folk(i, 'Is')
            else:
                folk = Folk(i, 'Ir')
            self.folks.append(folk)
        
        # Keep track of the number of folks in each status
        status_dict_t = {'S': num_init_spread, 'Is': num_Is, 'Ir': num_Ir, 'R': 0, 'E': 0}
        self.status_dicts.append(status_dict_t)
    
    def step(self):
        # Set up the new step
        self.status_dicts.append(self.status_dicts[-1])
        if self.current_timestep % 14 or self.status_dicts[-1]['S'] / self.num_pop > 0.75:
            town_meeting = DayEvent(1)
            self.day_events.append(town_meeting)

        for folk in self.folks:
            for day_event in self.day_events:
                day_event.happen(folk, self)
            folk.sleep(self.status_dicts[-1], self.params, rd.random())
        
        if len(self.day_events) == 3: # Reset day events
            self.day_events.pop()
        self.current_timestep += 1

    def run(self):
        for i in range(self.timesteps):
            self.step()
        # Print summerary

    def show_step(self, i):
        if i > self.timesteps - 1:
            print("Your specified time step exceeds the maximum time step of the simulation run.")