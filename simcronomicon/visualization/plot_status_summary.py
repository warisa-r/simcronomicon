import json

import h5py
import matplotlib.pyplot as plt


def _plot_status_summary_data(
        status_keys,
        timesteps,
        data_dict,
        status_type,
        ylabel="Density"):
    # A helper function to plot simulation status data over time using matplotlib.
    # Selects and validates which status types to plot, then generates the line plot.
    # Validate and select keys to plot

    if status_type is None:
        keys_to_plot = status_keys
    elif isinstance(status_type, str):
        if status_type not in status_keys:
            raise ValueError(
                f"Invalid status_type '{status_type}'. Must be one of {status_keys}.")
        keys_to_plot = [status_type]
    elif isinstance(status_type, list):
        invalid = [k for k in status_type if k not in status_keys]
        if invalid:
            raise ValueError(
                f"Invalid status types {invalid}. Must be from {status_keys}.")
        keys_to_plot = status_type
    else:
        raise TypeError(
            f"status_type must be None, str, or list of str, got {
                type(status_type).__name__}.")

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
    """
    Plot the normalized status summary (density) over time from a simulation HDF5 output file.

    This function reads the simulation status summary from the specified HDF5 file,
    normalizes each status by the total population, and plots the density of each status
    (or a subset of statuses) over simulation timesteps.

    Parameters
    ----------
    output_hdf5_path : str
        Path to the HDF5 file containing simulation results.
    status_type : str or list of str or None, optional
        If None (default), plot all status types.
        If str, plot only the specified status type.
        If list of str, plot only the specified status types.

    Raises
    ------
    ValueError
        If the HDF5 file contains no status data or if the total population is zero.
        If an invalid status_type is provided.
    TypeError
        If status_type is not None, str, or list of str.

    Returns
    -------
    None
        Displays a matplotlib plot of the status densities over time.
    """
    with h5py.File(output_hdf5_path, "r") as h5file:
        status_ds = h5file["status_summary/summary"]
        if len(status_ds) == 0:
            raise ValueError("No status data found in HDF5 file.")

        # Extract status keys from dtype
        all_keys = [
            name for name in status_ds.dtype.names if name not in (
                "timestep", "current_event")]

        # Extract total population from metadata
        metadata_str = h5file["config/simulation_config"][()
                                                          ].decode("utf-8")
        metadata = json.loads(metadata_str)
        total_population = metadata["population"]
        if total_population == 0:
            raise ValueError("Total population in configurations is zero.")

        # Prepare data dicts
        last_entry_by_timestep = {}
        for row in status_ds:
            timestep = int(row["timestep"])
            # Always keep the last one seen per timestep
            last_entry_by_timestep[timestep] = row

        final_timesteps = sorted(last_entry_by_timestep.keys())
        final_status_data = {key: [] for key in all_keys}

        for ts in final_timesteps:
            row = last_entry_by_timestep[ts]
            for key in all_keys:
                final_status_data[key].append(row[key] / total_population)

    _plot_status_summary_data(
        all_keys,
        final_timesteps,
        final_status_data,
        status_type,
        ylabel="Density")
