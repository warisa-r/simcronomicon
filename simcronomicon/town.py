import json
import pickle
import osmnx as ox
from itertools import combinations

from . import plt
from . import nx

class TownParameters():
    def __init__(self, literacy, max_social_energy, num_pop, num_init_spreader):
        self.literacy = literacy
        self.max_social_energy = max_social_energy
        self.num_init_spreader = num_init_spreader
        self.num_pop = num_pop

class Town():
    def __init__(self):
        # Default constructor for flexibility
        pass

    @classmethod
    def from_point(cls, point, dist, town_params):
        import osmnx as ox
        import networkx as nx
        from shapely.geometry import Point
        import json
        from itertools import combinations

        town = cls()
        town.town_params = town_params
        town.point = point
        town.dist = dist

        # 0. Calculate the EPSG code
        utm_zone = int((point[1] + 180) / 6) + 1
        hemisphere = 'north' if point[0] >= 0 else 'south'
        epsg_code = f"326{utm_zone}" if hemisphere == 'north' else f"327{utm_zone}"
        town.epsg_code = int(epsg_code)

        # 1. Download road network and buildings
        G_raw = ox.graph.graph_from_point(point, network_type="drive", dist=dist)
        tags = {"building": True}

        # 2. Project the raw graph and classify the buildings
        town.G_projected = ox.project_graph(G_raw)
        buildings = ox.features.features_from_point(point, tags, dist)
        buildings = buildings.to_crs(epsg=town.epsg_code)
        buildings['centroid'] = buildings.centroid
        buildings['nearest_node'] = buildings['centroid'].apply(
            lambda p: ox.distance.nearest_nodes(town.G_projected, p.x, p.y)
        )
        buildings['place_type'] = buildings.apply(town.classify_place, axis=1)

        # 3. Annotate nodes
        place_type_map = buildings.set_index('nearest_node')['place_type'].to_dict()
        nx.set_node_attributes(town.G_projected, place_type_map, 'place_type')

        # 4. Filter nodes
        nodes_to_keep = [n for n, d in town.G_projected.nodes(data=True)
                         if d.get('place_type') in ['accommodation', 'healthcare_facility', 'commercial']]
        G_filtered = town.G_projected.subgraph(nodes_to_keep).copy()

        # 5. Build town_graph
        town.town_graph = nx.Graph()
        old_nodes = list(G_filtered.nodes)
        town.id_map = {old_id: new_id for new_id, old_id in enumerate(old_nodes)}
        town.accommodation_node_ids = set()
        town.healthcare_facility_node_ids = set()
        town.commercial_node_ids = set()

        for old_id, new_id in town.id_map.items():
            place_type = G_filtered.nodes[old_id].get('place_type')
            if place_type == 'accommodation':
                town.accommodation_node_ids.add(new_id)
            elif place_type == 'healthcare_facility':
                town.healthcare_facility_node_ids.add(new_id)
            elif place_type == 'commercial':
                town.commercial_node_ids.add(new_id)
            town.town_graph.add_node(new_id, place_type=place_type)

        for id1, id2 in combinations(old_nodes, 2):
            try:
                dist = nx.shortest_path_length(town.G_projected, source=id1, target=id2, weight='length')
                town.town_graph.add_edge(town.id_map[id1], town.id_map[id2], weight=dist)
            except nx.NetworkXNoPath:
                continue

        # 6. Save graphs and metadata
        ox.save_graphml(town.G_projected, "raw_projected_graph.graphml")
        nx.write_graphml_lxml(town.town_graph, "town_graph.graphml")
        metadata = {
            "origin_point": [float(point[0]), float(point[1])],
            "epsg_code": int(epsg_code),
            "id_map": {str(k): v for k, v in town.id_map.items()},
            "accommodation_nodes": list(town.accommodation_node_ids),
            "commercial_nodes": list(town.commercial_node_ids),
            "healthcare_nodes": list(town.healthcare_facility_node_ids),
        }
        with open("town_graph_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        for i in range(len(town.town_graph.nodes)):
            town.town_graph.nodes[i]['folks'] = []

        return town

    @classmethod
    def from_files(cls, metadata_path, town_graph_path, projected_graph_path, town_params):
        import json
        import networkx as nx

        town = cls()
        town.town_params = town_params

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        town.point = metadata["origin_point"]
        town.epsg_code = metadata["epsg_code"]
        town.id_map = {k: v for k, v in metadata["id_map"].items()}
        town.accommodation_node_ids = set(metadata["accommodation_nodes"])
        town.commercial_node_ids = set(metadata["commercial_nodes"])
        town.healthcare_facility_node_ids = set(metadata["healthcare_nodes"])
        town.accommodation_node_ids = set(map(int, town.accommodation_node_ids))
        town.commercial_node_ids = set(map(int, town.commercial_node_ids))
        town.healthcare_facility_node_ids = set(map(int, town.healthcare_facility_node_ids))
        town.id_map = {int(k): v for k, v in town.id_map.items()}

        town.town_graph = nx.read_graphml(town_graph_path)
        town.G_projected = ox.load_graphml(projected_graph_path)

        # Convert node IDs to integers (assuming they are digit strings)
        town.town_graph = nx.relabel_nodes(town.town_graph, lambda x: int(x))
        town.G_projected = nx.relabel_nodes(town.G_projected, lambda x: int(x))

        for i in range(len(town.town_graph.nodes)):
            town.town_graph.nodes[i]['folks'] = []

        return town

    def classify_place(self, row):
        b = str(row.get("building", "")).lower()
        a = str(row.get("amenity", "")).lower()
        l = str(row.get("landuse", "")).lower()
        h = str(row.get("healthcare", "")).lower()
        s = str(row.get("shop", "")).lower()
        e = str(row.get("emergency", "")).lower()

        if b in ['residential', 'apartments', 'house', 'detached', 'dormitory', 'terrace', 'allotment_house', 'bungalow']:
            return 'accommodation'
        
        elif h in ['hospital', 'clinic', 'doctor', 'doctors', 'pharmacy', 'laboratory'] or \
            a in ['hospital', 'clinic', 'doctors', 'pharmacy'] or \
            s in ['medical_supply', 'hearing_aids'] or \
            e == 'yes' or b == 'hospital':
            return 'healthcare_facility'
        
        elif b in ['commercial', 'retail', 'office', 'supermarket', 'shop'] or \
            a in ['restaurant', 'bar', 'cafe', 'bank'] or \
            l in ['commercial']:
            return 'commercial'
        
        else:
            return 'other'

    def draw_town(self):
        node_colors = []
        for node, data in self.G_projected.nodes(data=True):
            if data.get("place_type") == "healthcare_facility":
                node_colors.append("red")         # Hospital → red
            elif data.get("place_type") == "commercial":
                node_colors.append("blue")        # Commercial → blue
            elif data.get("place_type") == "accommodation":
                node_colors.append("green")       # Accommodation → green
            else:
                node_colors.append("grey")        # Other unlabeled node is plotted with the color grey

        # Plot with custom node colors
        fig, ax = ox.plot_graph(
            self.G_projected,
            node_color=node_colors,
            node_size=20,
            edge_color="lightgray",
            bgcolor="white",
        )
