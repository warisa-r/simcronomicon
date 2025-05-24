import json
import osmnx as ox
from itertools import combinations
from tqdm import tqdm
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
    def __init__(self, num_pop, num_init_spreader):
        self.num_init_spreader = num_init_spreader
        self.num_pop = num_pop


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
            all_place_types=None):

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
        POI['nearest_node'] = POI.geometry.apply(
            lambda geom: ox.distance.nearest_nodes(G_projected, geom.x, geom.y)
        )

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
        town.town_graph = nx.Graph()
        old_nodes = list(G_filtered.nodes)
        id_map = {
            old_id: new_id for new_id,
            old_id in enumerate(old_nodes)}
        town.accommodation_node_ids = []

        for old_id, new_id in id_map.items():
            place_type = G_filtered.nodes[old_id].get('place_type')
            row = POI[POI['nearest_node'] == old_id]
            if not row.empty:
                geom = row.iloc[0].geometry
                x = geom.x
                y = geom.y
            else:
                raise ValueError(
                    "Corrupted DataFrame found. Please check that the input area includes buildings with valid centroid mappings!")

            if place_type == 'accommodation':
                town.accommodation_node_ids.append(new_id)

            town.town_graph.add_node(new_id, place_type=place_type, x=x, y=y)

        print("Calculating shortest paths between all node pairs...")
        for id1, id2 in tqdm(combinations(old_nodes, 2), total=len(
                old_nodes) * (len(old_nodes) - 1) // 2):
            try:
                dist = nx.shortest_path_length(
                    G_projected, source=id1, target=id2, weight='length')
                town.town_graph.add_edge(
                    id_map[id1], id_map[id2], weight=dist)
            except nx.NetworkXNoPath:
                continue

        town.found_place_types = set(
            nx.get_node_attributes(
                town.town_graph,
                'place_type').values())

        print("[10/10] Saving a compressed graph and metadata...")
        nx.write_graphml_lxml(town.town_graph, "town_graph.graphml")
        with zipfile.ZipFile("town_graph.graphmlz", "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write("town_graph.graphml", arcname="graph.graphml")
        os.remove("town_graph.graphml")

        metadata = {
            "origin_point": [float(point[0]), float(point[1])],
            "dist": town.dist,
            "epsg_code": int(epsg_code),
            "all_place_types": town.all_place_types,
            "found_place_types": list(town.found_place_types),
            "accommodation_nodes": list(town.accommodation_node_ids),
        }
        with open("town_graph_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        for i in range(len(town.town_graph.nodes)):
            town.town_graph.nodes[i]['folks'] = []

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

        print("Town graph successfully built from input files!")
        return town
