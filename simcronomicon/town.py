import json
import osmnx as ox
from itertools import combinations

from . import plt
from . import nx

class TownParameters():
    def __init__(self, num_pop, num_init_spreader):
        self.num_init_spreader = num_init_spreader
        self.num_pop = num_pop

class Town():
    def __init__(self):
        # Default constructor for flexibility
        pass

    @classmethod
    def from_point(cls, point, dist, town_params):
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
        town.accommodation_node_ids = []

        for old_id, new_id in town.id_map.items():
            place_type = G_filtered.nodes[old_id].get('place_type')
            if place_type == 'accommodation':
                town.accommodation_node_ids.append(new_id)

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
            "dist": dist,
            "epsg_code": int(epsg_code),
            "id_map": {str(k): v for k, v in town.id_map.items()},
            "accommodation_nodes": list(town.accommodation_node_ids),
        }
        with open("town_graph_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        for i in range(len(town.town_graph.nodes)):
            town.town_graph.nodes[i]['folks'] = []

        return town

    @classmethod
    def from_files(cls, metadata_path, town_graph_path, projected_graph_path, town_params):
        town = cls()
        town.town_params = town_params

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        town.point = metadata["origin_point"]
        town.epsg_code = metadata["epsg_code"]
        town.id_map = {k: v for k, v in metadata["id_map"].items()}
        town.accommodation_node_ids = list(metadata["accommodation_nodes"])

        # Now, to make sure the IDs are integers (if they were originally strings):
        town.accommodation_node_ids = list(map(int, town.accommodation_node_ids))

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

        # Accommodation classification
        if b in ['residential', 'apartments', 'house', 'detached', 'dormitory', 'terrace', 'allotment_house', 'bungalow', 'semidetached_house', 'hut']:
            return 'accommodation'
        
        # Healthcare classification
        elif b in ['hospital', 'dentist'] or \
            h in ['hospital', 'clinic', 'doctor', 'doctors', 'pharmacy', 'laboratory'] or \
            a in ['hospital', 'clinic', 'doctors', 'pharmacy', 'dentist'] or \
            s in ['medical_supply', 'hearing_aids'] or \
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

    def draw_town(self):
        node_colors = []
        for node, data in self.G_projected.nodes(data=True):
            if data.get("place_type") == "healthcare_facility":
                node_colors.append("red")         # Hospital → red
            elif data.get("place_type") == "commercial":
                node_colors.append("blue")        # Commercial → blue
            elif data.get("place_type") == "accommodation":
                node_colors.append("green")       # Accommodation → green
            elif data.get("place_type") == "workplace":
                node_colors.append("cyan")
            elif data.get("place_type") == "education":
                node_colors.append("yellow")
            elif data.get("place_type") == "religious":
                node_colors.append("magenta")
            else:
                node_colors.append("grey")

        # Plot with custom node colors
        fig, ax = ox.plot_graph(
            self.G_projected,
            node_color=node_colors,
            node_size=20,
            edge_color="lightgray",
            bgcolor="white",
        )
