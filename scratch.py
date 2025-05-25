import simcronomicon as scon

point =     50.7753, 6.0839
town_params = scon.TownParameters(10000, 10)
#town = scon.Town.from_point(point, 500, town_params)
town_graph_path = "test/test_data/town_graph_aachen_dom_2000m.graphmlz"
town_metadata_path = "test/test_data/town_graph_metadata_aachen_dom_2000m.json"


town = scon.Town.from_files(
    metadata_path= town_metadata_path,
    town_graph_path=town_graph_path,
    town_params=town_params
)



#scon.visualize_place_types_from_graphml(town_graph_path, town_metadata_path)

#model_params = scon.SEIsIrRModelParameters(4 , 0.7, 0.7, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)
#model = scon.SEIsIrRModel(model_params)
#model_params = scon.SEIRModelParameters(max_energy=5, beta= 0.4, sigma= 6, gamma=5, xi = 200)
#model = scon.SEIRModel(model_params)
model_params = scon.SEIQRDVModelParameters(2, 0.6, 0.05, 5, 2, 3, 4, 0.3)
model = scon.SEIQRDVModel(model_params)
sim = scon.Simulation(town, model, 1000)
sim.run(True)
#scon.plot_status_summary_from_csv("simulation_results.csv")
#scon.plot_status_summary_from_hdf5("simulation_output.h5")
#scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)