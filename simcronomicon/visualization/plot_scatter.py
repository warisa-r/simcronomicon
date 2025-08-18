import json
import warnings
from itertools import product

import h5py
import pandas as pd
import plotly.express as px

from .visualization_util import (_load_node_info_from_graphmlz,
                                 _set_plotly_renderer,
                                 _validate_and_merge_colormap)


def plot_place_types_scatter(town_graph_path, town_config_path, colormap=None):
    """
    Visualizes nodes from a .graphmlz town graph file as colored points with colors representing
    different place types (e.g., accommodation, commercial, education), using Plotly and OpenStreetMap..

    Parameters
    ----------
    town_graph_path : str
        Path to the .graphmlz file containing the town graph with node coordinates
        and place_type classifications.
    town_config_path : str
        Path to the .json file containing town metadata with 'epsg_code' for coordinate
        conversion and 'place_types' list defining valid place types.
    colormap : dict, optional
        Custom color mapping {'place_type': '#HEXCOLOR'}. If None, uses defaults.
        Custom colors override defaults for matching place types.

    Returns
    -------
    None
        Displays an interactive Plotly scatter map with colored points, legend,
        and hover information showing node IDs.

    Raises
    ------
    AssertionError
        If file extensions are incorrect (.graphmlz and .json required).
    KeyError
        If town_config_path doesn't contain required 'epsg_code' field.
    ValueError
        If colormap doesn't provide colors for all place types defined in
        town_config_path's 'place_types' list.
    FileNotFoundError
        If specified file paths don't exist.

    Notes
    -----
    - Default colors provided for: accommodation, commercial, religious, education,
      workplace, healthcare_facility
    - Nodes with undefined place types are colored gray (#CCCCCC)
    - Requires internet connection for OpenStreetMap tiles
    """
    assert town_graph_path.endswith(
        ".graphmlz"), f"Expected a .graphmlz file for town_graph_path, got {town_graph_path}"
    assert town_config_path.endswith(
        ".json"), f"Expected a .json file for town_config_path, got {town_config_path}"

    with open(town_config_path, 'r') as f:
        config = json.load(f)

    # Set a correct render for the environment the script is being run
    _set_plotly_renderer()

    # Get valid place types from config
    valid_place_types = config.get('place_types', [])
    epsg_code = config["epsg_code"]  # Also epsg code

    # Default colormap that supports the place types defined in the
    # default place classification function
    default_colormap = {
        "accommodation": "#FFD700",
        "commercial": "#FFA07A",
        "religious": "#9370DB",
        "education": "#00BFFF",
        "workplace": "#4682B4",
        "healthcare_facility": "#17EEA6",
    }

    # Validate and merge colormaps
    color_map = _validate_and_merge_colormap(
        default_colormap,
        colormap,
        valid_place_types,
        "place type"
    )

    node_positions, node_place_types = _load_node_info_from_graphmlz(
        town_graph_path, epsg_code, return_place_type=True
    )

    # Assemble DataFrame
    node_data_list = []
    for node_id, (lat, lon) in node_positions.items():
        place_type = node_place_types.get(node_id, "other")
        node_data_list.append({
            "node_id": node_id,
            "lat": lat,
            "lon": lon,
            "place_type": place_type,
            # Default gray for 'other' or unknown types
            "color": color_map.get(place_type, "#CCCCCC")
        })

    df = pd.DataFrame(node_data_list)

    fig = px.scatter_map(
        df,
        lat="lat",
        lon="lon",
        color="place_type",
        color_discrete_map=color_map,
        hover_name="node_id",
        zoom=13,
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


def plot_agents_scatter(
        output_hdf5_path,
        town_graph_path,
        time_interval=None):
    """
    Visualize the movement and status of agents over time on a map using simulation output using Plotly and OpenStreetMap.

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
        Displays an Plotly map with a time slider showing agent locations and statuses over time.

    Notes
    -----
    - Each status is represented by a random color (A colormap parameter is a to-be-implemented)
    - Requires internet connection for OpenStreetMap tiles
    """
    assert output_hdf5_path.endswith(
        ".h5"), f"Expected a .h5 file for output_hdf5_path, got {output_hdf5_path}"
    assert town_graph_path.endswith(
        ".graphmlz"), f"Expected a .graphmlz file for town_graph_path, got {town_graph_path}"

    # Set a correct render for the environment the script is being run
    _set_plotly_renderer()

    # Load HDF5 data
    with h5py.File(output_hdf5_path, "r") as h5:
        town_config_json_bytes = h5["config/town_config"][()]
        town_config = json.loads(town_config_json_bytes.decode("utf-8"))
        epsg_code = town_config["epsg_code"]

        folk_data = h5["individual_logs/log"][:]
        metadata_json_bytes = h5["config/simulation_config"][()]
        metadata = json.loads(metadata_json_bytes.decode("utf-8"))
        all_statuses = metadata["all_statuses"]
        step_events_order = [e['name']
                             for e in metadata.get("step_events", [])]

    # Load node positions
    node_pos = _load_node_info_from_graphmlz(town_graph_path, epsg_code)

    # Validate the user input time_interval
    if time_interval is not None:
        assert isinstance(time_interval, (tuple, list)) and len(
            time_interval) == 2, "time_interval must be a tuple or list of two integers (start, end)"
        assert all(isinstance(x, int)
                   for x in time_interval), "time_interval must contain only integers"
        assert time_interval[0] >= 0 and time_interval[1] > 0, "Timestep values in time_interval cannot be negative."
        assert time_interval[1] >= time_interval[0], "Start timestep cannot be greater than end timestep."

        max_timestep_in_data = int(folk_data["timestep"].max())

        if time_interval[1] > max_timestep_in_data:
            warnings.warn(
                f"Given end timestep {time_interval[1]} exceeds maximum timestep {max_timestep_in_data} in data. "
                f"Plotting will only include timesteps up to {max_timestep_in_data}."
            )
            time_interval = (time_interval[0], max_timestep_in_data)

            # Check again after adjustment - if start > adjusted end, it's an
            # error
            if time_interval[0] > time_interval[1]:
                raise ValueError(
                    f"Start timestep {time_interval[0]} is greater than maximum available timestep {max_timestep_in_data}. "
                    f"Please specify a start timestep <= {max_timestep_in_data}."
                )
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
        height=600,
        hover_data={"size": True}
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(
        title="Population status over time with marker size representing the number of people of that status at each time frame")
    fig.update_traces(marker=dict(opacity=0.7))
    fig.show()
