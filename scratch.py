import simcronomicon as scon

town_graph = scon.create_town_graph(600, 0.1)
town = scon.Town(town_graph, 0.4, 400)
sim_params = scon.SimulationParameters(0.04, 0.05, 0.05, 0.04, 0.07, 0.05, 0.001, 0.001)
sim = scon.Simulation(town, sim_params, 100)
sim.run()
print(sim.status_dicts[-1])