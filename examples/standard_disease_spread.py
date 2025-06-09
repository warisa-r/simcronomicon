import simcronomicon as scon

point = 50.7753, 6.0839
town_params = scon.TownParameters(1000, 10)
town_graph_path = "test/test_data/aachen_dom_500m.graphmlz"
town_config_path = "test/test_data/aachen_dom_500m_config.json"


town = scon.Town.from_files(
    config_path=town_config_path,
    town_graph_path=town_graph_path,
    town_params=town_params
)

step_events = [
    scon.StepEvent(
        "greet_neighbors",
        scon.FolkSEIR.interact,
        scon.EventType.DISPERSE,
        5000,
        ['accommodation']),
    scon.StepEvent(
        "chore",
        scon.FolkSEIR.interact,
        scon.EventType.DISPERSE,
        19000,
        [
            'commercial',
            'workplace',
            'education',
            'religious'], scon.log_normal_mobility)]


# scon.visualize_place_types_from_graphml(town_graph_path, town_config_path)

model_params = scon.SEIRModelParameters(
    max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200)
model = scon.SEIRModel(model_params, step_events)
sim = scon.Simulation(town, model, 100)
sim.run()
#scon.plot_status_summary_from_hdf5("simulation_output.h5")
scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)
