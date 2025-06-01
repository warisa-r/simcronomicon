import simcronomicon as scon

point =     50.7753, 6.0839
town_params = scon.TownParameters(5000, 10)
town_graph_path = "test/test_data/aachen_dom_2000m.graphmlz"
town_metadata_path = "test/test_data/aachen_dom_2000m_metadata.json"


town = scon.Town.from_files(
    metadata_path= town_metadata_path,
    town_graph_path=town_graph_path,
    town_params=town_params
)

step_events = [
            scon.StepEvent(
                "greet_neighbors",
                scon.FolkSEIQRDV.interact,
                scon.EventType.DISPERSE,
                5000,
                ['accommodation']),
            scon.StepEvent(
                "chore",
                scon.FolkSEIQRDV.interact,
                scon.EventType.DISPERSE,
                19000,
                [
                    'commercial',
                    'workplace',
                    'education',
                    'religious'], scon.log_normal_probabilities)]


#scon.visualize_place_types_from_graphml(town_graph_path, town_metadata_path)
model_params = scon.SEIQRDVModelParameters(max_energy=2, lam_cap=0, beta= 0.4, alpha=0.3, gamma= 4, delta=5, lam=7, rho=7, kappa=0.2, mu = 0, hospital_capacity=100)
model = scon.SEIQRDVModel(model_params, step_events)
sim = scon.Simulation(town, model, 50)
sim.run(save_result=True)
scon.plot_status_summary_from_hdf5("simulation_output.h5")
scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)