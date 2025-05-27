import os
import zipfile
import tempfile
import h5py
import json
import plotly.express as px
import plotly.io as pio
pio.renderers.default = "browser"

import warnings
from itertools import product
import pandas as pd
import networkx as nx
from pyproj import Transformer

def _load_node_info_from_graphmlz(
        town_graph_path,
        epsg_code,
        return_place_type=False):
    with tempfile.TemporaryDirectory() as tmpdirname:
        with zipfile.ZipFile(town_graph_path, 'r') as zf:
            zf.extractall(tmpdirname)
            graphml_path = os.path.join(tmpdirname, "graph.graphml")
            G = nx.read_graphml(graphml_path)
            G = nx.relabel_nodes(G, lambda x: int(x))

    transformer = Transformer.from_crs(
        f"EPSG:{epsg_code}", "EPSG:4326", always_xy=True)

    node_positions = {}
    node_place_types = {} if return_place_type else None

    for node, data in G.nodes(data=True):
        try:
            x = float(data["x"])
            y = float(data["y"])
        except (KeyError, ValueError):
            continue

        lon, lat = transformer.transform(x, y)
        node_positions[node] = (lat, lon)

        if return_place_type:
            place_type = data.get("place_type", "unknown")
            node_place_types[node] = place_type

    if return_place_type:
        return node_positions, node_place_types
    return node_positions


def visualize_place_types_from_graphml(town_graph_path, town_metadata_path):
    """
    Visualize nodes from a .graphmlz town graph with their classified place_type using Plotly and OpenStreetMap.

    Parameters
    ----------
    town_graph_path : str
        Path to the .graphmlz file containing the town graph.
    town_metadata_path : str
        Path to the .json file containing town metadata (must include 'epsg_code').

    Returns
    -------
    None
        Displays an interactive Plotly map of nodes colored by place type.
    """
    assert town_graph_path.endswith(".graphmlz"), f"Expected a .graphmlz file for town_graph_path, got {town_graph_path}"
    assert town_metadata_path.endswith(".json"), f"Expected a .json file for town_metadata_path, got {town_metadata_path}"

    with open(town_metadata_path, "r") as f:
        metadata = json.load(f)
    epsg_code = metadata["epsg_code"]

    node_positions, node_place_types = _load_node_info_from_graphmlz(
        town_graph_path, epsg_code, return_place_type=True
    )

    # Assemble DataFrame
    data = []
    for node_id, (lat, lon) in node_positions.items():
        place_type = node_place_types.get(node_id, "unknown")
        data.append({
            "node_id": node_id,
            "lat": lat,
            "lon": lon,
            "place_type": place_type
        })

    df = pd.DataFrame(data)
    if df.empty:
        print("No valid nodes to visualize.")
        return

    fig = px.scatter_map(
        df,
        lat="lat",
        lon="lon",
        color="place_type",
        hover_data=["node_id"],
        zoom=14,
        height=700
    )

    fig.update_layout(
        mapbox_style="open-street-map",
        title="Town Graph Nodes by Place Type",
        legend_title="Place Type",
        margin={"r": 0, "t": 50, "l": 0, "b": 0}
    )
    fig.update_traces(marker=dict(size=9, opacity=0.8))
    fig.show()


def visualize_folks_on_map_from_sim(
        output_hdf5_path,
        town_graph_path,
        time_interval=None):
    """
    Visualize the movement and status of agents over time on a map using simulation output.

    Parameters
    ----------
    output_hdf5_path : str
        Path to the HDF5 file containing simulation results.
    town_graph_path : str
        Path to the .graphmlz file containing the town graph.
    time_interval : tuple or list of int, optional
        (start, end) timestep range to visualize. If None, visualize all timesteps.

    Returns
    -------
    None
        Displays an animated Plotly map showing agent locations and statuses over time.
    """
    assert output_hdf5_path.endswith(".h5"), f"Expected a .h5 file for output_hdf5_path, got {output_hdf5_path}"
    assert town_graph_path.endswith(".graphmlz"), f"Expected a .graphmlz file for town_graph_path, got {town_graph_path}"

    # Load HDF5 data
    with h5py.File(output_hdf5_path, "r") as h5:
        town_metadata_json_bytes = h5["metadata/town_metadata"][()]
        town_metadata = json.loads(town_metadata_json_bytes.decode("utf-8"))
        epsg_code = town_metadata["epsg_code"]

        folk_data = h5["individual_logs/log"][:]
        metadata_json_bytes = h5["metadata/simulation_metadata"][()]
        metadata = json.loads(metadata_json_bytes.decode("utf-8"))
        all_statuses = metadata["all_statuses"]
        step_events_order = [e['name']
                             for e in metadata.get("step_events", [])]

    # Load node positions
    node_pos = _load_node_info_from_graphmlz(town_graph_path, epsg_code)

    # Validate the user input time_interval
    if time_interval is not None:
        assert isinstance(time_interval, (tuple, list)) and all(isinstance(
            x, int) for x in time_interval), "time_interval must be a tuple or list of two integers (start, end)"
        assert time_interval[0] >= 0 and time_interval[1] > 0, "Timestep values in time_interval cannot be negative."

        max_timestep_in_data = int(folk_data["timestep"].max())

        if time_interval[1] > max_timestep_in_data:
            warnings.warn(
                f"Given end timestep {time_interval[1]} exceeds maximum timestep {max_timestep_in_data} in data. "
                f"Plotting will only include timesteps up to {max_timestep_in_data}."
            )
            time_interval = (time_interval[0], max_timestep_in_data)
        assert time_interval[1] >= time_interval[0], "Start timestep cannot be greater than end timestep."

    # Aggregate for all (or selected) timesteps
    points = []
    for entry in folk_data:
        timestep = int(entry["timestep"])

        # Filter by time_interval if given
        if time_interval is not None:
            if timestep < time_interval[0] or timestep > time_interval[1]:
                continue

        event = entry["event"].decode("utf-8")
        status = entry["status"].decode("utf-8")
        address = int(entry["address"])
        if address in node_pos:
            lat, lon = node_pos[address]
            frame_label = f"{timestep}: {event}"

            points.append({
                "frame": frame_label,
                "lat": lat,
                "lon": lon,
                "status": status,
                "size": 1
            })

    if not points:
        print("No data found in the given time interval.")
        return

    df_raw = pd.DataFrame(points)
    df_raw["timestep"] = df_raw["frame"].str.extract(r"^(\d+):")[0].astype(int)
    df_raw["event_name"] = df_raw["frame"].str.extract(r": (.*)$")[0]

    # Map event names to their order (within each day)
    event_order_map = {name: i for i, name in enumerate(step_events_order)}
    df_raw["event_order"] = df_raw["event_name"].map(event_order_map)

    # Sort by timestep then by event order
    df_raw.sort_values(by=["timestep", "event_order"], inplace=True)

    # Re-create frame column with the correct order
    df_raw["frame"] = df_raw.apply(
        lambda row: f"{
            row['timestep']}: {
            row['event_name']}",
        axis=1)

    unique_frames = df_raw["frame"].drop_duplicates().tolist()
    unique_coords = df_raw[["lat", "lon"]].drop_duplicates().values.tolist()
    full_index = list(
        product(
            unique_frames, all_statuses, [
                tuple(c) for c in unique_coords]))

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
    df_grouped = df_raw.groupby(
        ["frame", "status", "lat", "lon"], as_index=False).agg({"size": "sum"})

    df_filled = pd.concat([df_grouped, full_df], ignore_index=True).drop_duplicates(
        subset=["frame", "status", "lat", "lon"], keep="first")

    fig = px.scatter_map(
        df_filled,
        lat="lat",
        lon="lon",
        size="size",
        color="status",
        animation_frame="frame",
        category_orders={
            "status": all_statuses,
            "frame": unique_frames
        },
        size_max=20,
        zoom=13,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(title="Population status over time")
    fig.update_traces(marker=dict(opacity=0.7))
    fig.show()
