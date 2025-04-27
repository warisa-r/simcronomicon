import simcronomicon as scon

town_graph = scon.create_town_graph(600, 0.7)
town = scon.Town(town_graph, 0.4, 200)
sim_params = scon.SimulationParameters(0.3, 0.5, 0.5, 0.4, 0.7, 0.2, 0.001, 0.001)
print(sim_params)
sim = scon.Simulation(town, sim_params, 100)
sim.run()
print(sim.status_dicts[-1])