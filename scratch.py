import simcronomicon as scon

point = 50.7753, 6.0839
town_params = scon.TownParameters(100, 10)
#town = scon.Town.from_point(point, 2000, town_params)
#town.draw_town()

town = scon.Town.from_files(
    metadata_path="test/test_data/town_graph_metadata_aachen.json",
    town_graph_path="test/test_data/town_graph_aachen.graphml",
    projected_graph_path="test/test_data/raw_projected_graph_aachen.graphml",
    town_params=town_params
)

#town.draw_town()
model_params = scon.SEIsIrRModelParameters(2 , 0.7, 0.7, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)
model = scon.SEIsIrRModel(model_params)
sim = scon.Simulation(town, model, 3)
sim.run(True)
#sim.plot_status(['S', 'E'])
scon.plot_results("simulation_results.csv", 'S')