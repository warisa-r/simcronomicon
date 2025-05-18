from . import plt
import csv
import h5py
import json
import plotly.express as px
import plotly.io as pio
pio.renderers.default = "browser"
import osmnx as ox
import pandas as pd
from itertools import product

def _plot_status_summary_data(status_keys, timesteps, data_dict, status_type, ylabel="Density"):
    # Validate and select keys to plot
    if status_type is None:
        keys_to_plot = status_keys
    elif isinstance(status_type, str):
        if status_type not in status_keys:
            raise ValueError(f"Invalid status_type '{status_type}'. Must be one of {status_keys}.")
        keys_to_plot = [status_type]
    elif isinstance(status_type, list):
        invalid = [k for k in status_type if k not in status_keys]
        if invalid:
            raise ValueError(f"Invalid status types {invalid}. Must be from {status_keys}.")
        keys_to_plot = status_type
    else:
        raise TypeError(f"status_type must be None, str, or list of str, got {type(status_type).__name__}.")

    # Plotting
    plt.figure(figsize=(10, 6))
    for key in keys_to_plot:
        plt.plot(timesteps, data_dict[key], label=key)

    plt.xlabel("Timestep")
    plt.ylabel(ylabel)
    plt.title("Simulation Status Over Timesteps")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_status_summary_from_hdf5(output_hdf5_path, status_type=None):
    with h5py.File(output_hdf5_path, "r") as h5file:
        status_ds = h5file["status_summary/summary"]
        if len(status_ds) == 0:
            raise ValueError("No status data found in HDF5 file.")

        # Extract status keys from dtype
        all_keys = [name for name in status_ds.dtype.names if name not in ("timestep", "current_event")]

        # Extract total population from metadata
        metadata_str = h5file["metadata/simulation_metadata"][()].decode("utf-8")
        metadata = json.loads(metadata_str)
        total_population = metadata["population"]
        if total_population == 0:
            raise ValueError("Total population in metadata is zero.")

        # Prepare data dicts
        last_entry_by_timestep = {}
        for row in status_ds:
            timestep = int(row["timestep"])
            last_entry_by_timestep[timestep] = row  # Always keep the last one seen per timestep

        final_timesteps = sorted(last_entry_by_timestep.keys())
        final_status_data = {key: [] for key in all_keys}

        for ts in final_timesteps:
            row = last_entry_by_timestep[ts]
            for key in all_keys:
                final_status_data[key].append(row[key] / total_population)

    _plot_status_summary_data(all_keys, final_timesteps, final_status_data, status_type, ylabel="Density")

def plot_status_summary_from_csv(file_path, status_type=None):
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        all_keys = reader.fieldnames

        # Identify status columns
        status_keys = [key for key in all_keys if key not in ('timestep', 'current_event')]
        rows = list(reader)

        if not rows:
            raise ValueError("The CSV file is empty.")

        # Calculate total population from the first row
        total_population = sum(int(rows[0][key]) for key in status_keys)
        if total_population == 0:
            raise ValueError("Total population is zero in the first row.")

        last_entry_by_timestep = {}
        for row in rows:
            timestep = int(row['timestep'])
            last_entry_by_timestep[timestep] = row  # Always overwrite, so we get the last status entry of that day

        # Sort by timestep
        final_timesteps = sorted(last_entry_by_timestep.keys())
        final_status_data = {key: [] for key in status_keys}

        for ts in final_timesteps:
            row = last_entry_by_timestep[ts]
            for key in status_keys:
                final_status_data[key].append(int(row[key]) / total_population)

    _plot_status_summary_data(status_keys, final_timesteps, final_status_data, status_type, ylabel="Density")

def _load_projected_node_positions(projected_graph_path, epsg_code):
    G = ox.load_graphml(projected_graph_path)
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


def visualize_folks_on_map(output_hdf5_path, projected_graph_path, metadata_json_path, time_interval=None):
    #TODO: Write a check that time interval exists -> raise error otherwise
    # Load metadata JSON
    with open(metadata_json_path) as f:
        metadata = json.load(f)
    epsg_code = metadata.get("epsg_code", 4326)
    raw_to_simplified = metadata.get("id_map", {})
    simplified_to_raw = {str(v): str(k) for k, v in raw_to_simplified.items()}

    # Load node positions
    node_pos = _load_projected_node_positions(projected_graph_path, epsg_code)

    # Load HDF5 data
    with h5py.File(output_hdf5_path, "r") as h5:
        folk_data = h5["individual_logs/log"][:]
        metadata_json_bytes = h5["metadata/simulation_metadata"][()]
        metadata = json.loads(metadata_json_bytes.decode("utf-8"))
        all_statuses = metadata["all_statuses"]

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
        address = str(entry["address"])
        raw_id = simplified_to_raw.get(address)
        if raw_id in node_pos:
            lat, lon = node_pos[raw_id]
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
    unique_frames = df_raw["frame"].unique()
    unique_coords = df_raw[["lat", "lon"]].drop_duplicates().values.tolist()
    full_index = list(product(unique_frames, all_statuses, [tuple(c) for c in unique_coords]))

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
        category_orders={"status": all_statuses},
        size_max=20,
        zoom=13,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(title="Population status over time")
    fig.update_traces(marker=dict(opacity=0.7))
    fig.show()