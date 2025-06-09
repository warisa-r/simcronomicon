import simcronomicon as scon

point = 50.7753, 6.0839
town_params = scon.TownParameters(2000, 0)
town_graph_path = "test/test_data/uniklinik_500m.graphmlz"
town_config_path = "test/test_data/uniklinik_500m_config.json"


town = scon.Town.from_files(
    config_path=town_config_path,
    town_graph_path=town_graph_path,
    town_params=town_params
)

healthcare_nodes = [n for n, d in town.town_graph.nodes(data=True) if d.get("place_type") == "healthcare_facility"]
print(healthcare_nodes)

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
            'religious'], scon.log_normal_mobility)]


# scon.visualize_place_types_from_graphml(town_graph_path, town_config_path)
model_params = scon.SEIQRDVModelParameters(
    max_energy=2, lam_cap=0, beta=0.4, alpha=0, gamma=4, delta=5, lam=7, rho=7, kappa=0.2, mu=0, hospital_capacity=100)
model = scon.SEIQRDVModel(model_params, step_events)
sim = scon.Simulation(town, model, 100)
sim.run()
scon.plot_status_summary_from_hdf5("simulation_output.h5")
scon.visualize_folks_on_map_from_sim("simulation_output.h5", town_graph_path)
