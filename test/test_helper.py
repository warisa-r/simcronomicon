import simcronomicon as scon
from pyproj import Transformer

# Common coordinates
POINT_DOM = (50.7753, 6.0839)
POINT_UNIKLINIK = (50.77583, 6.045277)
COORDS_THERESIENKIRCHE = (50.77809, 6.081859)
COORDS_HAUSARZT = (50.76943, 6.081437)
COORDS_SUPERC = (50.77828, 6.078571)

# Default town parameters for `test_town.py`
DEFAULT_TOWN_PARAMS = scon.TownParameters(100, 10)


def get_nearest_node(town, coords):
    lat, lon = coords
    transformer = Transformer.from_crs(
        "EPSG:4326", f"EPSG:{town.epsg_code}", always_xy=True)
    x, y = transformer.transform(lon, lat)
    min_dist = float("inf")
    closest_node = None
    for node, data in town.town_graph.nodes(data=True):
        dx = float(data["x"]) - x
        dy = float(data["y"]) - y
        dist = dx ** 2 + dy ** 2
        if dist < min_dist:
            min_dist = dist
            closest_node = node
    return closest_node


def get_shortest_path_length(town, node_a, node_b):
    G = town.town_graph
    import networkx as nx
    assert nx.has_path(G, node_a, node_b), \
        "A path between the nodes isn't found!"
    return nx.shortest_path_length(G, node_a, node_b, weight="weight")


MODEL_MATRIX = {
    "seir": (
        scon.SEIRModel,
        scon.SEIRModelParameters,
        scon.FolkSEIR,
        dict(max_energy=5, beta=0.4, sigma=6, gamma=5, xi=20),
        "test/test_data/aachen_dom_500m_metadata.json",
        "test/test_data/aachen_dom_500m.graphmlz"
    ),
    "seisir": (
        scon.SEIsIrRModel,
        scon.SEIsIrRModelParameters,
        scon.FolkSEIsIrR,
        dict(max_energy=5, literacy=0.5, gamma=0.5, alpha=0.5, lam=0.9,
             phi=0.5, theta=0.8, mu=0.5, eta1=0.5, eta2=0.5, mem_span=10),
        "test/test_data/aachen_dom_500m_metadata.json",
        "test/test_data/aachen_dom_500m.graphmlz"
    ),
    "seiqrdv": (
        scon.SEIQRDVModel,
        scon.SEIQRDVModelParameters,
        scon.FolkSEIQRDV,
        dict(max_energy=5, lam_cap=0.01, beta=0.4, alpha=0.5, gamma=3,
             delta=2, lam=4, rho=5, kappa=0.2, mu=0.01, hospital_capacity=100),
        "test/test_data/uniklinik_500m_metadata.json",
        "test/test_data/uniklinik_500m.graphmlz"
    )
}


def default_test_step_events(folk_class):
    return [
        scon.StepEvent("greet_neighbors", folk_class.interact, scon.EventType.DISPERSE, 5000, [
                       'accommodation'], scon.energy_exponential_mobility),
        scon.StepEvent("chore", folk_class.interact, scon.EventType.DISPERSE, 19000,
                       ['commercial', 'workplace', 'education', 'religious'], scon.log_normal_mobility)
    ]


def setup_simulation(model_key, town_params, step_events=None, timesteps=1, seed=None, override_params=None):
    model_class, model_params_class, folk_class, base_params, metadata_path, graphmlz_path = MODEL_MATRIX[
        model_key]
    params = dict(base_params)
    if override_params:
        params.update(override_params)
    model_params = model_params_class(**params)
    model = model_class(model_params, step_events=step_events)
    town = scon.Town.from_files(metadata_path, graphmlz_path, town_params)
    return scon.Simulation(town, model, timesteps=timesteps, seed=seed), town, model
