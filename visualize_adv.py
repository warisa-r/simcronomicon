import h5py
import json
import os
import numpy as np
import plotly.express as px
import plotly.io as pio
pio.renderers.default = "browser"
import networkx as nx
import osmnx as ox
import geopandas as gpd


def load_projected_node_positions(graphml_path, epsg_code):
    G = ox.load_graphml(graphml_path)
    nodes = ox.graph_to_gdfs(G, edges=False)

    if epsg_code != 4326:
        nodes_latlon = nodes.to_crs(epsg=4326)
    else:
        nodes_latlon = nodes

    node_positions = {
        str(node): (row.geometry.y, row.geometry.x)
        for node, row in nodes_latlon.iterrows()
    }
    return node_positions


def visualize_folks_on_map(hdf5_path, graphml_path, metadata_json_path, timestep_to_plot):
    # Load town metadata for EPSG code and node mapping
    with open(metadata_json_path) as f:
        metadata = json.load(f)
    epsg_code = metadata.get("epsg_code", 4326)
    raw_to_simplified = metadata.get("id_map", {})
    simplified_to_raw = {str(v): str(k) for k, v in raw_to_simplified.items()}

    # Load node positions
    node_pos = load_projected_node_positions(graphml_path, epsg_code)

    # Load HDF5 data
    with h5py.File(hdf5_path, "r") as h5:
        folk_data = h5["individual_logs/log"][:]

    # Aggregate people by (raw_id, status)
    node_status_counts = {}
    for entry in folk_data:
        timestep = entry["timestep"]
        status = entry["status"].decode("utf-8")
        address = str(entry["address"])

        if timestep != timestep_to_plot:
            continue

        raw_id = simplified_to_raw.get(address)
        if raw_id in node_pos:
            key = (raw_id, status)
            node_status_counts[key] = node_status_counts.get(key, 0) + 1

    if not node_status_counts:
        print(f"No matching data found at timestep {timestep_to_plot}.")
        return

    # Build DataFrame
    points = []
    for (raw_id, status), count in node_status_counts.items():
        lat, lon = node_pos[raw_id]
        points.append({
            "lat": lat,
            "lon": lon,
            "count": count,
            "status": status,
            "size": count
        })

    df = gpd.GeoDataFrame(points)

    # Plot with color by status
    fig = px.scatter_map(
        df,
        lat="lat",
        lon="lon",
        size="size",
        color="status",
        size_max=20,
        zoom=13,
        height=600
    )

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(title=f"Population status at timestep {timestep_to_plot}")
    fig.update_traces(marker=dict(opacity=0.7))

    fig.show()

if __name__ == "__main__":
    # Adjust these paths accordingly
    hdf5_path = "simulation_output.h5"
    graphml_path = "test/test_data/raw_projected_graph_aachen.graphml"
    metadata_json_path = "test/test_data/town_graph_metadata_aachen.json"

    timestep = 2
    status = "S"  # Change based on your status labels

    visualize_folks_on_map(hdf5_path, graphml_path, metadata_json_path, timestep)