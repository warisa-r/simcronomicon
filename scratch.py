import simcronomicon as scon

point = 50.7753, 6.0839
town_params = scon.TownParameters(0.7, 2, 5000, 10)
#town = scon.Town.from_point(point, 2000, town_params)
#town.draw_town()

town1 = scon.Town.from_files(
    metadata_path="town_graph_metadata.json",
    town_graph_path="town_graph.graphml",
    projected_graph_path="raw_projected_graph.graphml",
    town_params=town_params
)
town1.draw_town()
#sim_params = scon.SEIsIrRModelParameters(0.7, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)
#sim = scon.Simulation(town, sim_params, 5)
#sim.run(True)
#sim.plot_status('S')
#sim.plot_status()
#sim.plot_status(['S', 'E'])
#scon.plot_results("simulation_results.csv", 'S')