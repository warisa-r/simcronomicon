from . import plt
import csv

def _plot_status_data(timesteps, data_dict, status_type, ylabel="Density"):
    all_keys = ['S', 'Is', 'Ir', 'R', 'E']

    # Validate and select keys to plot
    if status_type is None:
        keys_to_plot = all_keys
    elif isinstance(status_type, str):
        if status_type not in all_keys:
            raise ValueError(f"Invalid status_type '{status_type}'. Must be one of {all_keys}.")
        keys_to_plot = [status_type]
    elif isinstance(status_type, list):
        invalid = [k for k in status_type if k not in all_keys]
        if invalid:
            raise ValueError(f"Invalid status types {invalid}. Must be from {all_keys}.")
        keys_to_plot = status_type
    else:
        raise TypeError(f"status_type must be None, str, or list of str, got {type(status_type).__name__}.")

    # Plotting
    plt.figure(figsize=(10, 6))
    for key in keys_to_plot:
        plt.plot(timesteps, data_dict[key], label=key)

    plt.xlabel("Timestep")
    plt.ylabel(ylabel)
    plt.title("Simulation Status Over Time")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_results(file_path, status_type=None):
    timesteps = []
    status_data = {key: [] for key in ['S', 'Is', 'Ir', 'R', 'E']}

    total_population = None

    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for i, row in enumerate(reader):
            timestep = int(row['timestep'])
            timesteps.append(timestep)

            if i == 0:
                total_population = sum(int(row[key]) for key in status_data)
                if total_population == 0:
                    raise ValueError("Total population is zero in the first row.")

            for key in status_data:
                status_data[key].append(int(row[key]) / total_population)

    _plot_status_data(timesteps, status_data, status_type, ylabel="Density")