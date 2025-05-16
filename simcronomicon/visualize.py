from . import plt
import csv
import h5py
import json

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

def plot_status_summary_from_hdf5(hdf5_path, status_type=None):
    with h5py.File(hdf5_path, "r") as h5file:
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