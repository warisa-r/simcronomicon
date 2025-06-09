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

    if b in {
        'residential', 'apartments', 'house', 'detached', 'dormitory', 'terrace',
        'allotment_house', 'bungalow', 'semidetached_house', 'hut'
    }:
        return 'accommodation'
    elif b in {'hospital', 'dentist'} or \
         h in {'hospital', 'clinic', 'doctor', 'doctors', 'pharmacy', 'laboratory'} or \
         a in {'hospital', 'clinic', 'doctors', 'pharmacy', 'dentist'} or \
         s in {'medical_supply'} or \
         e == 'yes':
        return 'healthcare_facility'
    elif b in {'commercial', 'retail', 'supermarket', 'shop', 'service', 'sports_centre'} or \
         a in {'restaurant', 'bar', 'cafe', 'bank', 'fast_food'} or \
         l in {'commercial'}:
        return 'commercial'
    elif b in {'office', 'factory', 'industrial', 'government'} or \
         a in {'office', 'factory', 'industry'} or \
         l in {'industrial', 'office'}:
        return 'workplace'
    elif b in {'school', 'university', 'kindergarten'} or \
         a in {'university', 'kindergarten'}:
        return 'education'
    elif b in {'chapel', 'church', 'temple', 'mosque', 'synagogue'} or \
         a in {'chapel', 'church', 'temple', 'mosque', 'synagogue'} or \
         l in {'religious'}:
        return 'religious'
    else:
        return 'other'


class TownParameters():
    # TODO: Throw error here when appropriate
    def __init__(self, num_pop, num_init_spreader, spreader_initial_nodes=[]):
        self.num_init_spreader = num_init_spreader
        self.num_pop = num_pop
        self.spreader_initial_nodes = spreader_initial_nodes


class Town():
    """
    Spatial network representation for agent-based epidemic modeling.

    The Town class represents a spatial network derived from OpenStreetMap data,
    where nodes correspond to places of interest (POIs) and edges represent
    walkable paths between locations. This network serves as the environment
    where agents move, interact, and undergo state transitions during simulation.

    Purpose
    -------
    1. **Spatial Network Creation**: Build a graph representation of urban areas
       from OpenStreetMap data, including roads, buildings, and points of interest.

    2. **Place Classification**: Categorize locations into functional types
       (accommodation, workplace, healthcare, etc.) that influence agent behavior.

    3. **Agent Housing**: Provide accommodation nodes where agents reside and
       return to after each simulation timestep.

    4. **Distance Calculation**: Maintain shortest-path distances between all
       locations to enable realistic agent movement patterns.

    5. **Data Persistence**: Save and load town networks to/from compressed
       files for reuse across multiple simulations.

    Network Structure
    -----------------
    - **Nodes**: Represent places of interest with attributes including:

      - place_type: Functional category of the location

      - x, y: Projected coordinates in the town's coordinate system

      - folks: List of agents currently at this location

    - **Edges**: Represent walkable connections with attributes:

      - weight: Shortest-path distance in meters between connected nodes

    Place Types
    -----------
    The default classification system recognizes:
    - accommodation: Residential buildings where agents live

    - healthcare_facility: Hospitals, clinics, pharmacies

    - commercial: Shops, restaurants, banks

    - workplace: Offices, factories, industrial areas

    - education: Schools, universities

    - religious: Churches, mosques, temples

    - other: Unclassified locations (filtered out by default)

    Attributes
    ----------
    town_graph : networkx.Graph
        The spatial network with nodes representing locations and edges
        representing shortest paths between them.
    town_params : TownParameters
        Configuration parameters including population size and initial spreader locations.
    epsg_code : int
        EPSG coordinate reference system code for spatial projections.
    point : tuple
        Origin point [latitude, longitude] used to center the network.
    dist : float
        Radius in meters defining the network extent from the origin point.
    all_place_types : list
        Complete list of possible place type categories.
    found_place_types : set
        Place types actually present in this town network.
    accommodation_node_ids : list
        Node IDs of all accommodation locations where agents can reside.

    Examples
    --------
    >>> # Create town from geographic coordinates (Aachen, Germany)
    >>> town_params = TownParameters(num_pop=1000, num_init_spreader=10)
    >>> town = Town.from_point(
    ...     point=[50.7753, 6.0839],  # Aachen Dom coordinates
    ...     dist=1000,  # 1km radius
    ...     town_params=town_params
    ... )
    >>> 
    >>> # Load previously saved town
    >>> town = Town.from_files(
    ...     metadata_path="town_metadata.json",
    ...     town_graph_path="town_graph.graphmlz",
    ...     town_params=town_params
    ... )
    >>> 
    >>> # Examine town properties
    >>> print(f"Town has {len(town.town_graph.nodes)} locations")
    >>> print(f"Place types found: {town.found_place_types}")
    >>> print(f"Accommodation nodes: {len(town.accommodation_node_ids)}")

    Notes
    -----
    - The town network uses shortest-path distances calculated from road network
      edges rather than Euclidean distances to provide realistic travel times
      between locations. These distances are computed by finding the shortest
      route along actual roads and pathways connecting places.

    - All shortest paths between every pair of places are pre-calculated during
      town creation, and the resulting simplified graph stores these distances
      as direct edge weights. This optimization dramatically reduces computational
      overhead during simulation steps, as agent movement only requires looking
      up neighboring edge weights rather than performing path searches.

    - This pre-computation approach is especially beneficial when running multiple
      simulations in the same location or simulations with many agents and timesteps,
      as the expensive shortest-path calculations are done once during town creation.

    - Building centroids are mapped to nearest road network nodes to ensure
      all locations are accessible via the street network.

    - Custom place classification functions can be provided to adapt the
      categorization system to specific research needs.

    - Town networks are automatically saved in compressed GraphMLZ format
      along with JSON metadata for efficient storage and reuse. These output
      files serve as input files for the Simulation class, enabling rapid
      simulation setup without re-downloading or re-processing OpenStreetMap data.

    Raises
    ------

    ValueError
        If the specified point coordinates are invalid, if no relevant
        locations remain after filtering, or if initial spreader nodes
        don't exist in the network.
    TypeError
        If the place classification function is not callable or if required
        parameters are missing when using custom classification.
    """

    def __init__(self):
        # Default constructor for flexibility
        pass

    def _validate_inputs(self, point, classify_place_func, all_place_types):
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

        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(
                "`point` must be a list or tuple in the format [latitude, longitude].")
        if not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
            raise ValueError(
                "`point` values must represent valid latitude and longitude coordinates.")

    def _setup_basic_attributes(self, point, dist, town_params, classify_place_func, all_place_types):
        print("[1/10] Initializing town object and parameters...")
        if all_place_types is None:
            all_place_types = [
                "accommodation", "healthcare_facility", "commercial",
                "workplace", "education", "religious", "other"
            ]

        self.all_place_types = all_place_types
        self.town_params = town_params
        self.classify_place_func = classify_place_func
        self.point = point
        self.dist = dist

        print("[2/10] Calculating EPSG code...")
        utm_zone = int((point[1] + 180) / 6) + 1
        self.epsg_code = int(
            f"326{utm_zone}" if point[0] >= 0 else f"327{utm_zone}")

    def _download_osm_data(self):
        import osmnx as ox

        print("[3/10] Downloading OSM road network and building data...")
        G_raw = ox.graph.graph_from_point(
            self.point, network_type="all", dist=self.dist)
        tags = {"building": True}
        self.G_projected = ox.project_graph(G_raw)
        buildings = ox.features.features_from_point(
            self.point, tags, self.dist)
        self.buildings = buildings.to_crs(epsg=self.epsg_code)

    def _process_buildings(self):
        from scipy.spatial import KDTree
        import numpy as np

        print("[4/10] Processing building geometries...")
        is_polygon = self.buildings.geometry.geom_type.isin(
            ['Polygon', 'MultiPolygon'])
        self.buildings.loc[is_polygon,
                           'geometry'] = self.buildings.loc[is_polygon, 'geometry'].centroid
        self.POI = self.buildings[self.buildings.geometry.geom_type == 'Point']

        print("[5/10] Matching building centroids to nearest road nodes...")
        self._match_buildings_to_roads()

        print("[6/10] Classifying buildings...")
        # Use the classification function passed to from_point
        self.POI['place_type'] = self.POI.apply(
            self.classify_place_func, axis=1)

        print("[7/10] Annotating road graph with place types...")
        place_type_map = self.POI.set_index(
            'nearest_node')['place_type'].to_dict()
        nx.set_node_attributes(self.G_projected, place_type_map, 'place_type')

    def _match_buildings_to_roads(self):
        from scipy.spatial import KDTree
        import numpy as np

        # Get projected coordinates of road nodes
        node_xy = {
            node: (data['x'], data['y'])
            for node, data in self.G_projected.nodes(data=True)
        }
        node_ids = list(node_xy.keys())
        node_coords = np.array([node_xy[n] for n in node_ids])

        # Build KDTree for fast nearest-neighbor queries
        tree = KDTree(node_coords)

        # Get POI coords and find nearest road nodes
        poi_coords = np.array([(geom.x, geom.y) for geom in self.POI.geometry])
        _, nearest_indices = tree.query(poi_coords)
        self.POI['nearest_node'] = [node_ids[i] for i in nearest_indices]

    def _build_spatial_network(self):
        import igraph as ig
        from tqdm import tqdm

        print("[8/10] Filtering out irrelevant nodes...")
        nodes_to_keep = [n for n, d in self.G_projected.nodes(data=True)
                         if d.get('place_type') is not None and d.get('place_type') != 'other']
        G_filtered = self.G_projected.subgraph(nodes_to_keep).copy()

        if len(G_filtered.nodes) == 0:
            raise ValueError(
                "No relevant nodes remain after filtering. The resulting town graph would be empty.")

        print("[9/10] Building town graph...")
        self._compute_shortest_paths(G_filtered)

    def _compute_shortest_paths(self, G_filtered):
        import igraph as ig
        from tqdm import tqdm
        import numpy as np

        # Convert G_projected to igraph for fast distance computation
        projected_nodes = list(self.G_projected.nodes)
        node_idx_map = {node: idx for idx, node in enumerate(projected_nodes)}

        g_ig = ig.Graph(directed=False)
        g_ig.add_vertices(len(projected_nodes))

        edges = []
        weights = []

        for u, v, data in self.G_projected.edges(data=True):
            if u in node_idx_map and v in node_idx_map:
                edges.append((node_idx_map[u], node_idx_map[v]))
                weights.append(data.get("length", 1.0))

        g_ig.add_edges(edges)
        g_ig.es["weight"] = weights

        # Compute shortest paths among filtered nodes
        filtered_nodes = list(G_filtered.nodes)
        filtered_indices = [node_idx_map[n] for n in filtered_nodes]

        print("Computing shortest paths between filtered nodes...")
        dist_matrix = g_ig.distances(
            source=filtered_indices,
            target=filtered_indices,
            weights=g_ig.es["weight"])

        # Build final NetworkX town graph
        self._build_final_graph(G_filtered, filtered_nodes, dist_matrix)

    def _build_final_graph(self, G_filtered, filtered_nodes, dist_matrix):
        from tqdm import tqdm

        self.town_graph = nx.Graph()
        id_map = {old_id: new_id for new_id,
                  old_id in enumerate(filtered_nodes)}
        self.accommodation_node_ids = []

        # Add nodes with attributes
        for old_id, new_id in id_map.items():
            place_type = G_filtered.nodes[old_id].get("place_type")
            row = self.POI[self.POI['nearest_node'] == old_id]
            x, y = (row.iloc[0].geometry.x, row.iloc[0].geometry.y) if not row.empty else (
                None, None)

            if place_type == "accommodation":
                self.accommodation_node_ids.append(new_id)

            self.town_graph.add_node(new_id, place_type=place_type, x=x, y=y)

        # Add edges with shortest path distances
        print("Adding edges to final town graph...")
        for i in tqdm(range(len(filtered_nodes))):
            for j in range(i + 1, len(filtered_nodes)):
                dist = dist_matrix[i][j]
                if dist != float("inf"):
                    self.town_graph.add_edge(
                        id_map[filtered_nodes[i]],
                        id_map[filtered_nodes[j]],
                        weight=dist
                    )

        self.found_place_types = set(nx.get_node_attributes(
            self.town_graph, 'place_type').values())

    def _save_files(self, file_prefix, save_dir):
        import zipfile
        import json
        import os

        print("[10/10] Saving a compressed graph and metadata...")
        graphml_name = os.path.join(save_dir, f"{file_prefix}.graphml")
        graphmlz_name = os.path.join(save_dir, f"{file_prefix}.graphmlz")
        metadata_name = os.path.join(save_dir, f"{file_prefix}_metadata.json")

        nx.write_graphml_lxml(self.town_graph, graphml_name)

        if os.path.exists(graphmlz_name):
            overwrite = input(
                f"The file '{graphmlz_name}' already exists. Overwrite? (y/n): ").strip().lower()
            if overwrite != 'y':
                print(
                    "Input file saving operation aborted to avoid overwriting the file. Returning town object...")
                return

        with zipfile.ZipFile(graphmlz_name, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(graphml_name, arcname="graph.graphml")
        os.remove(graphml_name)  # Remove the unzipped file

        # Save metadata
        metadata = {
            "origin_point": [float(self.point[0]), float(self.point[1])],
            "dist": self.dist,
            "epsg_code": int(self.epsg_code),
            "all_place_types": self.all_place_types,
            "found_place_types": list(self.found_place_types),
            "accommodation_nodes": list(self.accommodation_node_ids),
        }
        with open(metadata_name, "w") as f:
            json.dump(metadata, f, indent=2)

    def _finalize_town_setup(self):
        # Initialize folks list for all nodes
        for node in self.town_graph.nodes:
            self.town_graph.nodes[node]["folks"] = []

        # Validate spreader nodes
        missing_nodes = [
            node for node in self.town_params.spreader_initial_nodes
            if node not in self.town_graph.nodes
        ]
        if missing_nodes:
            raise ValueError(
                f"Some spreader_initial_nodes do not exist in the town graph: {missing_nodes}"
            )

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
        """
        Create a town network from OpenStreetMap data centered on a geographic point.

        Downloads road network and building data from OpenStreetMap, processes building
        geometries, classifies places by type, and constructs a simplified graph with
        pre-computed shortest-path distances between all locations.

        Parameters
        ----------
        point : list or tuple
            Geographic coordinates [latitude, longitude] defining the center point
            for data extraction.
        dist : float
            Radius in meters around the point to extract data. Defines the spatial
            extent of the town network.
        town_params : TownParameters
            Configuration object containing population size, initial spreader count,
            and spreader node locations.
        classify_place_func : callable, optional
            Function to classify building types into place categories. Must accept
            a pandas row and return a place type string (default: classify_place).
        all_place_types : list, optional
            List of all possible place type categories. Required when using custom
            classify_place_func (default: None).
        file_prefix : str, optional
            Prefix for output files (default: "town_graph").
        save_dir : str, optional
            Directory to save compressed graph and metadata files (default: ".").

        Returns
        -------
        Town
            Town object with populated spatial network and metadata.

        Raises
        ------
        ValueError
            If point coordinates are invalid, no relevant nodes remain after
            filtering, or spreader nodes don't exist in the network.
        TypeError
            If classify_place_func is not callable or required parameters are missing.

        Examples
        --------
        >>> town_params = TownParameters(num_pop=1000, num_init_spreader=5)
        >>> town = Town.from_point(
        ...     point=[50.7753, 6.0839],  # Aachen Dom
        ...     dist=1000,
        ...     town_params=town_params,
        ...     file_prefix="aachen_dom",
        ...     save_dir="./data"
        ... )
        """

        import igraph as ig
        from tqdm import tqdm
        from scipy.spatial import KDTree

        town = cls()
        town._validate_inputs(point, classify_place_func, all_place_types)
        town._setup_basic_attributes(
            point, dist, town_params, classify_place_func, all_place_types)
        town._download_osm_data()
        town._process_buildings()
        town._build_spatial_network()
        town._save_files(file_prefix, save_dir)
        town._finalize_town_setup()

        print("Town graph successfully built and saved!")
        return town

    @classmethod
    def from_files(cls, metadata_path, town_graph_path, town_params):
        """
    Load a previously saved town network from compressed files.

    Reconstructs a Town object from GraphMLZ and JSON metadata files created
    by a previous call to from_point(). This method enables rapid simulation
    setup without re-downloading or re-processing OpenStreetMap data.

    Parameters
    ----------
    metadata_path : str
        Path to the JSON metadata file containing town configuration and
        place type information.
    town_graph_path : str
        Path to the compressed GraphMLZ file containing the spatial network.
    town_params : TownParameters
        Configuration object containing population size, initial spreader count,
        and spreader node locations for the simulation.

    Returns
    -------
    Town
        Town object with loaded spatial network and metadata.

    Raises
    ------
    ValueError
        If spreader nodes specified in town_params don't exist in the
        loaded network.
    FileNotFoundError
        If the specified files don't exist.

    Examples
    --------
    >>> town_params = TownParameters(num_pop=1000, num_init_spreader=5)
    >>> town = Town.from_files(
    ...     metadata_path="./data/aachen_dom_metadata.json",
    ...     town_graph_path="./data/aachen_dom.graphmlz",
    ...     town_params=town_params
    ... )
    """
        # 1. Unzip the graphmlz to a temp folder
        print("[1/3] Decompressing the graphmlz file...")
        with tempfile.TemporaryDirectory() as tmpdirname:
            with zipfile.ZipFile(town_graph_path, 'r') as zf:
                zf.extractall(tmpdirname)
                graphml_path = os.path.join(tmpdirname, "graph.graphml")
                G = nx.read_graphml(graphml_path)
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

        town._finalize_town_setup()

        print("Town graph successfully built from input files!")
        return town
