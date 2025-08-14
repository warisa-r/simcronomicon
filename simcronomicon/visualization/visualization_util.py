import os
import re
import tempfile
import warnings
import zipfile

import networkx as nx
import plotly.io as pio
from IPython import get_ipython
from pyproj import Transformer


def _validate_and_merge_colormap(default_map, user_map, valid_keys, parameter_name):
    # A helper function used to validate and merge the colormap for plotly visualization
    # if the user gives us a custom color map.

    # Start with the default colormap
    result = default_map.copy()

    # If user map provided, merge it
    # This is for the case where user might not provide all the colors for all the place types
    # in their location of interest. The place type without user specified color will fall back
    # to using default color.
    if user_map is not None:
        # Check user entries
        for key, color in user_map.items():
            if key not in valid_keys:
                warnings.warn(
                    f"Warning: '{key}' is not a valid {parameter_name}. "
                    f"Valid values are: {', '.join(valid_keys)}"
                )

            # Basic validation for hex color codes
            if not isinstance(color, str) or not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
                warnings.warn(
                    f"Warning: '{color}' for {key} is not a valid hex color. "
                    "Expected format: '#RRGGBB' or '#RGB'"
                )

            # Add to result anyway (user's responsibility)
            result[key] = color

    # AFTER merging, check if there are still valid keys without colors
    # If the place type - color mapping doesn't exist in the default map and the custom map,
    # tell the user to provide it.
    missing_colors = set(valid_keys) - set(result.keys())
    if missing_colors:
        raise ValueError(
            f"Missing colors for valid {parameter_name}(s): {', '.join(sorted(missing_colors))}. "
            f"Please provide colors for these in the colormap parameter."
        )

    return result


def _set_plotly_renderer():
    # A helper function to determine on which platform plotly is supposed to
    # render the plot
    try:
        # Check if running in a Jupyter notebook
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            pio.renderers.default = "notebook"
        else:
            pio.renderers.default = "browser"
    except NameError:
        # Not running in IPython/Jupyter
        pio.renderers.default = "browser"


def _load_node_info_from_graphmlz(
        town_graph_path,
        epsg_code,
        return_place_type=False):
    # A helper function that loads the information necessary for plotting 
    # from the compressed input graph file
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
        x = float(data["x"])
        y = float(data["y"])

        lon, lat = transformer.transform(x, y)
        node_positions[node] = (lat, lon)

        if return_place_type:
            place_type = data.get("place_type", "unknown")
            node_place_types[node] = place_type

    if return_place_type:
        return node_positions, node_place_types
    return node_positions
