import simcronomicon as scon

point =     50.7753, 6.0839
town_params = scon.TownParameters(10000, 10)
#town = scon.Town.from_point(point, 500, town_params)
town_graph_path = "test/test_data/aachen_dom_750m.graphmlz"
town_metadata_path = "test/test_data/aachen_dom_750m_metadata.json"


town = scon.Town.from_files(
    metadata_path= town_metadata_path,
    town_graph_path=town_graph_path,
    town_params=town_params
)



#scon.visualize_place_types_from_graphml(town_graph_path, town_metadata_path)

#model_params = scon.SEIsIrRModelParameters(4 , 0.7, 0.7, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)
#model = scon.SEIsIrRModel(model_params)
model_params = scon.SEIRModelParameters(max_energy=5, beta= 0.4, sigma= 6, gamma=5, xi = 200)
model = scon.SEIRModel(model_params)
#model_params = scon.SEIQRDVModelParameters(2, 0.005, 0.8, 0.00001, 5, 2, 3, 4, 0.05, 0.01)
#model = scon.SEIQRDVModel(model_params)
sim = scon.Simulation(town, model, 200)
sim.run(save_result=True)
scon.plot_status_summary_from_hdf5("simulation_output.h5")
#scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)