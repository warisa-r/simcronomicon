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
import pandas as pd
from itertools import product
from collections import defaultdict



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


def visualize_folks_on_map(hdf5_path, graphml_path, metadata_json_path):
    # Load metadata JSON
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
        metadata_json_bytes = h5["metadata/simulation_metadata"][()]
        metadata = json.loads(metadata_json_bytes.decode("utf-8"))
        all_statuses = metadata["all_statuses"]

    # Aggregate for all timesteps
    points = []
    for entry in folk_data:
        timestep = int(entry["timestep"])
        event = entry["event"].decode("utf-8")
        status = entry["status"].decode("utf-8")
        address = str(entry["address"])
        raw_id = simplified_to_raw.get(address)
        if raw_id in node_pos:
            lat, lon = node_pos[raw_id]
            frame_label = f"{timestep}: {event}"

            points.append({
                "frame":frame_label,
                "lat": lat,
                "lon": lon,
                "status": status,
                "size": 1
            })

    if not points:
        print("No data found.")
        return
        

    # Get all unique frame labels and coordinates
    df_raw = pd.DataFrame(points)
    unique_frames = df_raw["frame"].unique()
    unique_coords = df_raw[["lat", "lon"]].drop_duplicates().values.tolist()
    full_index = list(product(unique_frames, all_statuses, [tuple(c) for c in unique_coords]))

    # Fill missing combinations
    full_df = pd.DataFrame([
        {
            "frame": f,
            "status": s,
            "lat": lat,
            "lon": lon,
            "size": 0
        }
        for f, s, (lat, lon) in full_index
    ])
    df_grouped = df_raw.groupby(["frame", "status", "lat", "lon"], as_index=False).agg({"size": "sum"})

    # Merge real + filler
    df_filled = pd.concat([df_grouped, full_df], ignore_index=True).drop_duplicates(
        subset=["frame", "status", "lat", "lon"], keep="first"
    )

    fig = px.scatter_map(
        df_filled,
        lat="lat",
        lon="lon",
        size="size",
        color="status",
        animation_frame="frame",
        category_orders={"status": all_statuses},  # enforce full legend
        size_max=20,
        zoom=13,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(title="Population status over time")
    fig.update_traces(marker=dict(opacity=0.7))

    fig.show()
    
if __name__ == "__main__":
    # Adjust these paths accordingly
    hdf5_path = "simulation_output.h5"
    graphml_path = "test/test_data/raw_projected_graph_aachen.graphml"
    metadata_json_path = "test/test_data/town_graph_metadata_aachen.json"

    timestep = 2
    status = "S"  # Change based on your status labels

    visualize_folks_on_map(hdf5_path, graphml_path, metadata_json_path)