import simcronomicon as scon

point = 50.7753, 6.0839
town_params = scon.TownParameters(1000, 10)
# town = scon.Town.from_point(point, 500, town_params)
town_graph_path = "test/test_data/aachen_dom_500m.graphmlz"
town_metadata_path = "test/test_data/aachen_dom_500m_metadata.json"


town = scon.Town.from_files(
    metadata_path=town_metadata_path,
    town_graph_path=town_graph_path,
    town_params=town_params
)

step_events = [
    scon.StepEvent(
        "greet_neighbors",
        scon.FolkSEIsIrR.interact,
        scon.EventType.DISPERSE,
        5000,
        ['accommodation']),
    scon.StepEvent(
        "chore",
        scon.FolkSEIsIrR.interact,
        scon.EventType.DISPERSE,
        19000,
        [
            'commercial',
            'workplace',
            'education',
            'religious'], scon.log_normal_probabilities)]


# scon.visualize_place_types_from_graphml(town_graph_path, town_metadata_path)

model_params = scon.SEIsIrRModelParameters(
    4, 0.7, 0.9, 0.5, 0.5, 0.5, 0.7, 0.62, 0.1, 0.1)
model = scon.SEIsIrRModel(model_params, step_events)
sim = scon.Simulation(town, model, 50)
sim.run(save_result=True)
scon.plot_status_summary_from_hdf5("simulation_output.h5")
# scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)
