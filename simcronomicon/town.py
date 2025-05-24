import json
import osmnx as ox
from itertools import combinations
import geopandas as gpd
from shapely.geometry import Point

from . import plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from . import nx

def classify_place( row):
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

class TownParameters():
    def __init__(self, num_pop, num_init_spreader):
        self.num_init_spreader = num_init_spreader
        self.num_pop = num_pop

class Town():
    def __init__(self):
        # Default constructor for flexibility
        pass

    @classmethod
    def from_point(cls, point, dist, town_params, classify_place_func=classify_place,
                   all_place_types=None):
        
        if not callable(classify_place_func):
            raise TypeError("`classify_place_func` must be a function.")

        # If the user passed a custom function, they must also pass custom place_types
        if classify_place_func is not classify_place:
            if all_place_types is None:
                raise ValueError(
                    "If you pass a custom `classify_place_func`, you must also provide `all_place_types`."
                )
            elif not "accommodation" in all_place_types:
                raise ValueError(
                                "Your `all_place_types` must be consisted of residential or 'accommodation' type of buildings."
                )

        # Use default place types only when using default function
        if all_place_types is None:
            all_place_types = [
                "accommodation", "healthcare_facility", "commercial",
                "workplace", "education", "religious", "other"
            ]

        town = cls()
        town.all_place_types = all_place_types
        town.town_params = town_params
        town.point = point
        town.dist = dist

        # 0. Calculate the EPSG code
        utm_zone = int((point[1] + 180) / 6) + 1
        hemisphere = 'north' if point[0] >= 0 else 'south'
        epsg_code = f"326{utm_zone}" if hemisphere == 'north' else f"327{utm_zone}"
        town.epsg_code = int(epsg_code)

        # 1. Download road network and buildings
        G_raw = ox.graph.graph_from_point(point, network_type="all", dist=dist)
        tags = {"building": True}

        # 2. Project the raw graph and classify the buildings
        town.G_projected = ox.project_graph(G_raw)
        buildings = ox.features.features_from_point(point, tags, dist)
        buildings = buildings.to_crs(epsg=town.epsg_code)


        is_polygon = buildings.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
        buildings.loc[is_polygon, 'geometry'] = buildings.loc[is_polygon, 'geometry'].centroid
        POI = buildings[buildings.geometry.geom_type == 'Point']


        # We are getting in this simulation node in G_raw that is closest to the buildings
        # osnmx provides a point in the street with some level of labels that imply the type of the buildings
        # nearest to that node. For better labelings (to get more information on building type), 
        # we pull data of building centroid.
        POI['nearest_node'] = POI.geometry.apply(
            lambda geom: ox.distance.nearest_nodes(town.G_projected, geom.x, geom.y)
        )
        POI['place_type'] = POI.apply(classify_place_func, axis=1)

        # 3. Annotate nodes
        place_type_map = POI.set_index('nearest_node')['place_type'].to_dict()
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

            # Find matching point in POI (should be only one)
            row = POI[POI['nearest_node'] == old_id]
            if not row.empty:
                geom = row.iloc[0].geometry
                x = geom.x
                y = geom.y
            else:
                Warning("What is going on. Cant find that")
                x = y = None  # Fallback if something's off

            if place_type == 'accommodation':
                town.accommodation_node_ids.append(new_id)

            town.town_graph.add_node(new_id, 
                                    place_type=place_type,
                                    x=x,
                                    y=y)

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
            "all_place_types": town.all_place_types,
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
        town.dist = metadata["dist"]
        town.all_place_types = list(metadata["all_place_types"])
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

    def draw_town(self):
        color_map = cm.get_cmap("tab10", len(self.all_place_types))
        
        place_types_for_coloring = [pt for pt in self.all_place_types if pt != "other"]
        
        place_type_to_color = {
            pt: mcolors.to_hex(color_map(i)) for i, pt in enumerate(sorted(place_types_for_coloring))
        }
        place_type_to_color["other"] = "grey"

        node_colors = []
        for _, data in self.G_projected.nodes(data=True):
            pt = data.get("place_type", "other")
            node_colors.append(place_type_to_color.get(pt, "grey"))

        # Create figure and axes manually
        fig, ax = plt.subplots(figsize=(10, 10))
        legend_patches = [
            mpatches.Patch(color=color, label=pt)
            for pt, color in place_type_to_color.items()
        ]
        ax.legend(
            handles=legend_patches,
            title="Place Types",
            loc="upper left",
            bbox_to_anchor=(1.05, 1),
            borderaxespad=0.
        )

        fig, ax = ox.plot_graph(
            self.G_projected,
            ax=ax,
            node_color=node_colors,
            node_size=20,
            edge_color="lightgray",
            bgcolor="white",
        )