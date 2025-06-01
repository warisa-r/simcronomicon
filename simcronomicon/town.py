import json
import osmnx as ox
import numpy as np
import zipfile
import os
import tempfile

from . import nx


def classify_place(row):
    b = str(row.get("building", "")).lower()
    a = str(row.get("amenity", "")).lower()
    l = str(row.get("landuse", "")).lower()
    h = str(row.get("healthcare", "")).lower()
    s = str(row.get("shop", "")).lower()
    e = str(row.get("emergency", "")).lower()

    # Accommodation classification
    if b in [
        'residential',
        'apartments',
        'house',
        'detached',
        'dormitory',
        'terrace',
        'allotment_house',
        'bungalow',
        'semidetached_house',
            'hut']:
        return 'accommodation'

    # Healthcare classification
    elif b in ['hospital', 'dentist'] or \
            h in ['hospital', 'clinic', 'doctor', 'doctors', 'pharmacy', 'laboratory'] or \
            a in ['hospital', 'clinic', 'doctors', 'pharmacy', 'dentist'] or \
            s in ['medical_supply'] or \
            e == 'yes':
        return 'healthcare_facility'

    # Commercial classification
    elif b in ['commercial', 'retail', 'supermarket', 'shop', 'service', 'sports_centre'] or \
            a in ['restaurant', 'bar', 'cafe', 'bank', 'fast_food'] or \
            l in ['commercial']:
        return 'commercial'

    # Workplace classification (universities, offices, factories)
    elif b in ['office', 'factory', 'industrial', 'government'] or \
            a in ['office', 'factory', 'industry'] or \
            l in ['industrial', 'office']:
        return 'workplace'

    # Education classification
    elif b in ['school', 'university', 'kindergarten'] or \
            a in ['university', 'kindergarten']:
        return 'education'

    elif b in ['chapel', 'church', 'temple', 'mosque', 'synagogue'] or \
            a in ['chapel', 'church', 'temple', 'mosque', 'synagogue'] or \
            l in ['religious']:
        return 'religious'

    else:
        return 'other'


class TownParameters():
    def __init__(self, num_pop, num_init_spreader, spreader_initial_nodes=[]):
        self.num_init_spreader = num_init_spreader
        self.num_pop = num_pop
        self.spreader_initial_nodes = spreader_initial_nodes


class Town():
    def __init__(self):
        # Default constructor for flexibility
        pass

    @classmethod
    def from_point(
        cls,
        point,
        dist,
        town_params,
        classify_place_func=classify_place,
        all_place_types=None,
        file_prefix="town_graph",
        save_dir="."
    ):

        import igraph as ig
        from tqdm import tqdm
        from scipy.spatial import KDTree

        if not callable(classify_place_func):
            raise TypeError("`classify_place_func` must be a function.")

        if classify_place_func is not classify_place:
            if all_place_types is None:
                raise ValueError(
                    "If you pass a custom `classify_place_func`, you must also provide `all_place_types`."
                )
            elif "accommodation" not in all_place_types:
                raise ValueError(
                    "Your `all_place_types` must include 'accommodation' type buildings."
                )

        if all_place_types is None:
            all_place_types = [
                "accommodation", "healthcare_facility", "commercial",
                "workplace", "education", "religious", "other"
            ]

        print("[1/10] Initializing town object and parameters...")
        town = cls()
        town.all_place_types = all_place_types
        town.town_params = town_params
        town.point = point
        town.dist = dist

        print("[2/10] Calculating EPSG code...")
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(
                "`point` must be a list or tuple in the format [latitude, longitude].")
        if not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
            raise ValueError(
                "`point` values must represent valid latitude and longitude coordinates.")
        utm_zone = int((point[1] + 180) / 6) + 1
        hemisphere = 'north' if point[0] >= 0 else 'south'
        epsg_code = f"326{utm_zone}" if hemisphere == 'north' else f"327{utm_zone}"
        town.epsg_code = int(epsg_code)

        print("[3/10] Downloading OSM road network and building data...")
        G_raw = ox.graph.graph_from_point(point, network_type="all", dist=dist)
        tags = {"building": True}
        G_projected = ox.project_graph(G_raw)
        buildings = ox.features.features_from_point(point, tags, dist)
        buildings = buildings.to_crs(epsg=town.epsg_code)

        print("[4/10] Processing building geometries...")
        is_polygon = buildings.geometry.geom_type.isin(
            ['Polygon', 'MultiPolygon'])
        buildings.loc[is_polygon,
                      'geometry'] = buildings.loc[is_polygon,
                                                  'geometry'].centroid
        POI = buildings[buildings.geometry.geom_type == 'Point']

        print("[5/10] Matching building centroids to nearest road nodes...")
        # Get projected coordinates of road nodes
        node_xy = {
            node: (data['x'], data['y'])
            for node, data in G_projected.nodes(data=True)
        }
        node_ids = list(node_xy.keys())
        node_coords = np.array([node_xy[n] for n in node_ids])

        # Build KDTree for fast nearest-neighbor queries
        tree = KDTree(node_coords)

        # Get POI coords
        poi_coords = np.array([(geom.x, geom.y) for geom in POI.geometry])

        # Query nearest road node for each POI
        _, nearest_indices = tree.query(poi_coords)
        POI['nearest_node'] = [node_ids[i] for i in nearest_indices]

        print("[6/10] Classifying buildings...")
        POI['place_type'] = POI.apply(classify_place_func, axis=1)

        print("[7/10] Annotating road graph with place types...")
        place_type_map = POI.set_index('nearest_node')['place_type'].to_dict()
        nx.set_node_attributes(G_projected, place_type_map, 'place_type')

        print("[8/10] Filtering out irrelevant nodes...")
        nodes_to_keep = [n for n, d in G_projected.nodes(data=True) if d.get(
            'place_type') is not None and d.get('place_type') != 'other']
        G_filtered = G_projected.subgraph(nodes_to_keep).copy()

        print("[9/10] Building town graph...")
        # We use igraph here for fast distance computation between nodes. The rest of the simulation uses NetworkX for its flexible attribute handling.
        # Convert G_projected to igraph
        projected_nodes = list(G_projected.nodes)
        node_idx_map = {node: idx for idx, node in enumerate(projected_nodes)}

        g_ig = ig.Graph(directed=False)
        g_ig.add_vertices(len(projected_nodes))

        edges = []
        weights = []

        for u, v, data in G_projected.edges(data=True):
            if u in node_idx_map and v in node_idx_map:
                edges.append((node_idx_map[u], node_idx_map[v]))
                weights.append(data.get("length", 1.0))

        g_ig.add_edges(edges)
        g_ig.es["weight"] = weights

        # Filtered nodes for shortest path computation
        filtered_nodes = list(G_filtered.nodes)
        filtered_indices = [node_idx_map[n] for n in filtered_nodes]

        # Compute all-pairs shortest paths among filtered nodes
        print("Computing shortest paths between filtered nodes...")
        dist_matrix = g_ig.distances(
            source=filtered_indices,
            target=filtered_indices,
            weights=g_ig.es["weight"])

        # Build final NetworkX town graph using filtered nodes and shortest
        # paths
        town.town_graph = nx.Graph()
        id_map = {
            old_id: new_id for new_id,
            old_id in enumerate(filtered_nodes)}
        town.accommodation_node_ids = []

        for old_id, new_id in id_map.items():
            place_type = G_filtered.nodes[old_id].get("place_type")
            row = POI[POI['nearest_node'] == old_id]
            if not row.empty:
                geom = row.iloc[0].geometry
                x, y = geom.x, geom.y
            else:
                raise ValueError("Missing centroid mapping for node.")

            if place_type == "accommodation":
                town.accommodation_node_ids.append(new_id)

            town.town_graph.add_node(new_id, place_type=place_type, x=x, y=y)

        print("Adding edges to final town graph...")
        for i in tqdm(range(len(filtered_nodes))):
            for j in range(i + 1, len(filtered_nodes)):
                dist = dist_matrix[i][j]
                if dist != float("inf"):
                    town.town_graph.add_edge(id_map[filtered_nodes[i]],
                                             id_map[filtered_nodes[j]],
                                             weight=dist)

        town.found_place_types = set(
            nx.get_node_attributes(
                town.town_graph,
                'place_type').values())

        # Assert that all spreader_initial_nodes exist in the town graph
        assert all(
            node in town.town_graph.nodes
            for node in town.town_params.spreader_initial_nodes
        ), (
            f"Some spreader_initial_nodes do not exist in the town graph: "
            f"{[node for node in town.town_params.spreader_initial_nodes if node not in town.town_graph.nodes]}"
        )

        print("[10/10] Saving a compressed graph and metadata...")
        graphml_name = os.path.join(save_dir, f"{file_prefix}.graphml")
        graphmlz_name = os.path.join(save_dir, f"{file_prefix}.graphmlz")
        metadata_name = os.path.join(save_dir, f"{file_prefix}_metadata.json")

        nx.write_graphml_lxml(town.town_graph, graphml_name)
        if os.path.exists(graphmlz_name):
            overwrite = input(
                f"The file '{graphmlz_name}' already exists. Overwrite? (y/n): ").strip().lower()
            if overwrite != 'y':
                print(
                    "Input file saving operation aborted to avoid overwriting the file. Returning town object../")
                return town

        with zipfile.ZipFile(graphmlz_name, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(graphml_name, arcname="graph.graphml")
        os.remove(graphml_name)  # Remove the unzipped file

        metadata = {
            "origin_point": [float(point[0]), float(point[1])],
            "dist": town.dist,
            "epsg_code": int(epsg_code),
            "all_place_types": town.all_place_types,
            "found_place_types": list(town.found_place_types),
            "accommodation_nodes": list(town.accommodation_node_ids),
        }
        with open(metadata_name, "w") as f:
            json.dump(metadata, f, indent=2)

        # This attribute has to be assigned here since xml doesn't support
        # writing list as attributes
        for node in town.town_graph.nodes:
            town.town_graph.nodes[node]["folks"] = []

        print("Town graph successfully built and saved!")
        return town

    @classmethod
    def from_files(cls, metadata_path, town_graph_path, town_params):
        # 1. Unzip the graphmlz to a temp folder
        print("[1/3] Decompressing the graphmlz file...")
        with tempfile.TemporaryDirectory() as tmpdirname:
            with zipfile.ZipFile(town_graph_path, 'r') as zf:
                zf.extractall(tmpdirname)
                graphml_path = os.path.join(tmpdirname, "graph.graphml")
                G = nx.read_graphml(graphml_path)
                # Relabel node ID as integers
                G = nx.relabel_nodes(G, lambda x: int(x))

        # 2. Load metadata
        print("[2/3] Load the metadata...")
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # 3. Rebuild Town object
        print("[3/3] Rebuild the town object...")
        town = cls()
        town.town_graph = G
        town.town_params = town_params
        town.epsg_code = metadata["epsg_code"]
        town.point = metadata["origin_point"]
        town.dist = metadata["dist"]
        town.all_place_types = metadata["all_place_types"]
        town.found_place_types = metadata["found_place_types"]
        town.accommodation_node_ids = metadata["accommodation_nodes"]

        # Initialize folks list if not already present
        for i in town.town_graph.nodes:
            if "folks" not in town.town_graph.nodes[i]:
                town.town_graph.nodes[i]["folks"] = []

        # Assert that all spreader_initial_nodes exist in the town graph
        assert all(
            node in town.town_graph.nodes
            for node in town.town_params.spreader_initial_nodes
        ), (
            f"Some spreader_initial_nodes do not exist in the town graph: "
            f"{[node for node in town.town_params.spreader_initial_nodes if node not in town.town_graph.nodes]}"
        )

        print("Town graph successfully built from input files!")
        return town
