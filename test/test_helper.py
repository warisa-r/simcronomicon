import simcronomicon as scon

MODEL_MATRIX = {
    "seir": (
        scon.SEIRModel,
        scon.SEIRModelParameters,
        scon.FolkSEIR,
        dict(max_energy=5, beta=0.4, sigma=6, gamma=5, xi=200),
        "test/test_data/aachen_dom_500m_metadata.json",
        "test/test_data/aachen_dom_500m.graphmlz"
    ),
    "seisir": (
        scon.SEIsIrRModel,
        scon.SEIsIrRModelParameters,
        scon.FolkSEIsIrR,
        dict(max_energy=5, literacy=0.5, gamma=0.5, alpha=0.5, lam=0.5, phi=0.5, theta=0.5, mu=0.5, eta1=0.5, eta2=0.5, mem_span=10),
        "test/test_data/aachen_dom_500m_metadata.json",
        "test/test_data/aachen_dom_500m.graphmlz"
    ),
    "seiqrdv": (
        scon.SEIQRDVModel,
        scon.SEIQRDVModelParameters,
        scon.FolkSEIQRDV,
        dict(max_energy=5, lam_cap=0.01, beta=0.4, alpha=0.5, gamma=3, delta=2, lam=4, rho=5, kappa=0.2, mu=0.01, hospital_capacity=100),
        "test/test_data/uniklinik_500m_metadata.json",
        "test/test_data/uniklinik_500m.graphmlz"
    )
}

def default_step_events(folk_class):
    return [
        scon.StepEvent("greet_neighbors", folk_class.interact, scon.EventType.DISPERSE, 5000, ['accommodation']),
        scon.StepEvent("chore", folk_class.interact, scon.EventType.DISPERSE, 19000,
                       ['commercial', 'workplace', 'education', 'religious'], scon.log_normal_probabilities)
    ]

def setup_simulation(model_key, town_params, step_events=None, timesteps=1, seed=None, override_params=None):
    model_class, model_params_class, folk_class, base_params, metadata_path, graphmlz_path = MODEL_MATRIX[model_key]
    params = dict(base_params)
    if override_params:
        params.update(override_params)
    model_params = model_params_class(**params)
    model = model_class(model_params, step_events=step_events)
    town = scon.Town.from_files(metadata_path, graphmlz_path, town_params)
    return scon.Simulation(town, model, timesteps=timesteps, seed=seed), town, model
