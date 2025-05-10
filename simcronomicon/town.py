from . import plt
import osmnx as ox
from . import nx

def classify_place(row):
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

class TownParameters():
    def __init__(self, literacy, max_social_energy, num_pop, num_init_spreader):
        self.literacy = literacy
        self.max_social_energy = max_social_energy
        self.num_init_spreader = num_init_spreader
        self.num_pop = num_pop


class Town():
    def __init__(self, town_params, point, dist): # Create a town from point of latitude and longtitude and distance... one constructor now
        self.town_params = town_params

        # 0. Calculate the ESPG code of the given point

        # Calculate UTM zone based on the longitude
        utm_zone = int((point[1] + 180) / 6) + 1
        # Determine if it's in the northern or southern hemisphere
        hemisphere = 'north' if point[0] >= 0 else 'south'

        # Create the EPSG code for UTM (using the UTM zone and hemisphere)
        epsg_code = f"326{utm_zone}" if hemisphere == 'north' else f"327{utm_zone}"

        # 1. Get a raw MultiDiGraph from osmnx
        G_raw = ox.graph.graph_from_point(point, network_type="drive", dist=2000)
        tags = {"building": True}

        # 2. Project the raw graph and classify the buildings in the given area
        self.G_projected = ox.project_graph(G_raw)
        buildings = ox.features.features_from_point(point, tags, 2000)
        buildings = buildings.to_crs(epsg=epsg_code)
        buildings['centroid'] = buildings.centroid
        buildings['nearest_node'] = buildings['centroid'].apply(
            lambda p: ox.distance.nearest_nodes(G_projected, p.x, p.y)
        )
        buildings['place_type'] = buildings.apply(classify_place, axis=1)

        # 3. Annotate nodes with place_type
        place_type_map = buildings.set_index('nearest_node')['place_type'].to_dict()
        nx.set_node_attributes(self.G_projected, place_type_map, 'place_type')

        # 4. Remove nodes with unknown types
        nodes_to_keep = [n for n, d in self.G_projected.nodes(data=True) if d.get('place_type') in ['accommodation', 'healthcare_facility', 'commercial']]
        G_filtered = self.G_projected.subgraph(nodes_to_keep).copy() # Keep the filtered nodes with information of the given area's layout

        # 5. TODO: convert to simple graph easy to process

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
