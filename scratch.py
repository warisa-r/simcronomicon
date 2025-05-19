import simcronomicon as scon

point = 50.7753, 6.0839
town_params = scon.TownParameters(100, 10)
#town = scon.Town.from_point(point, 2000, town_params)
#town.draw_town()
town_graph_path = "test/test_data/town_graph_aachen.graphml"
projected_graph_path = "test/test_data/raw_projected_graph_aachen.graphml"
town_metadata_path = "test/test_data/town_graph_metadata_aachen.json"

town = scon.Town.from_files(
    metadata_path= town_metadata_path,
    town_graph_path=town_graph_path,
    projected_graph_path= projected_graph_path,
    town_params=town_params
)

#town.draw_town()
#model_params = scon.SEIsIrRModelParameters(2 , 0.7, 0.7, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)
#model = scon.SEIsIrRModel(model_params)
model_params = scon.SEIRModelParameters(max_social_energy=2, beta= 0.4, sigma= 6, gamma=5, xi = 200)
model = scon.SEIRModel(model_params)
sim = scon.Simulation(town, model, 2)
sim.run(True)
#scon.plot_status_summary_from_csv("simulation_results.csv")
scon.plot_status_summary_from_hdf5("simulation_output.h5")
scon.visualize_folks_on_map("simulation_output.h5", projected_graph_path)