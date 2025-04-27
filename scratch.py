import simcronomicon as scon

town_graph = scon.create_town_graph_barabasi_albert(2000, 2)
town = scon.Town(town_graph, 0.5, 200, 'BA')
sim_params = scon.SimulationParameters(0.7, 0.5, 0.5, 0.4, 0.7, 0.2, 0.1, 0.001)
sim = scon.Simulation(town, sim_params, 100)
sim.run()
sim.save_results()
sim.plot_status('S')
sim.plot_status()
sim.plot_status(['S', 'E'])
