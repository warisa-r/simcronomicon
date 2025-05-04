import simcronomicon as scon

town_graph = scon.create_town_graph_barabasi_albert(5000, 10)
town = scon.Town(town_graph, 0.7, 2, 6000, 10, 'BA')
sim_params = scon.SEIsIrRModelParameters(0.7, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)
sim = scon.Simulation(town, sim_params, 100)
sim.run(True)
sim.plot_status('S')
sim.plot_status()
sim.plot_status(['S', 'E'])
#scon.plot_results("simulation_results.csv", 'S')