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


def visualize_folks_on_map(hdf5_path, graphml_path, metadata_json_path, timestep_to_plot, target_status):
    # Load town metadata for EPSG code and node mapping
    with open(metadata_json_path) as f:
        metadata = json.load(f)
    epsg_code = metadata.get("epsg_code", 4326)
    raw_to_simplified = metadata.get("id_map", {})

    # Reverse the mapping: simplified -> raw
    simplified_to_raw = {str(v): str(k) for k, v in raw_to_simplified.items()}

    # Load node positions from projected graph
    node_pos = load_projected_node_positions(graphml_path, epsg_code)

    # Load HDF5 data
    with h5py.File(hdf5_path, "r") as h5:
        folk_data = h5["individual_logs/log"][:]

    # Count infected folks per raw node
    node_counts = {}
    for entry in folk_data:
        timestep = entry["timestep"]
        status = entry["status"].decode("utf-8")
        address = str(entry["address"])

        if timestep != timestep_to_plot or status != target_status:
            continue

        raw_id = simplified_to_raw.get(address)
        if raw_id in node_pos:
            node_counts[raw_id] = node_counts.get(raw_id, 0) + 1

    if not node_counts:
        print(f"No matching positions found at timestep {timestep_to_plot}.")
        return

    # Prepare GeoDataFrame for plotting
    points = []
    for raw_id, count in node_counts.items():
        lat, lon = node_pos[raw_id]
        points.append({
            "lat": lat,
            "lon": lon,
            "count": count,
            "status": target_status,   # fixed color
            "size": count     # size scales with count
        })

    df = gpd.GeoDataFrame(points)

    fig = px.scatter_map(
    df,
    lat="lat",
    lon="lon",
    size="size",
    size_max=20,
    zoom=13,
    height=600
    )

    # Manually override all marker colors to red
    fig.update_traces(marker=dict(color='red', opacity=0.7))

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(title=f"'{target_status}' folks at timestep {timestep_to_plot}")
    fig.show()

if __name__ == "__main__":
    # Adjust these paths accordingly
    hdf5_path = "simulation_output.h5"
    graphml_path = "test/test_data/raw_projected_graph_aachen.graphml"
    metadata_json_path = "test/test_data/town_graph_metadata_aachen.json"

    timestep = 2
    status = "S"  # Change based on your status labels

    visualize_folks_on_map(hdf5_path, graphml_path, metadata_json_path, timestep, status)