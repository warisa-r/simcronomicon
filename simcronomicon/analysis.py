from . import json
from . import csv
from . import np

from scipy.optimize import curve_fit
from scipy.stats import norm
import os

def skewed_gaussian(x, xi, omega, alpha):
    # Standard normal PDF and CDF
    pdf = norm.pdf((x - xi) / omega)
    cdf = norm.cdf(alpha * (x - xi) / omega)
    return pdf * cdf # Without normalization

class StatisticalAnalysis():
    def __init__(self, sim=None, sim_metadata_json=None, sim_results_csv_path=None):
        if sim is None:
            # If sim is None, we expect the other two arguments to be provided
            if sim_metadata_json is None or sim_results_csv_path is None:
                raise ValueError("If 'sim' is not provided, both 'sim_metadata_json' and 'sim_results_csv_path' must be specified.")
            # Load the metadata from the json file
            self.metadata = self._load_metadata(sim_metadata_json)
            self.status_dicts, self.timesteps = self._read_simulation_results(sim_results_csv_path)
        else:
            # If sim is provided, use the Simulation object and extract parameters
            self.sim = sim
            self.param = sim.param
            self.status_dicts = sim.status_dicts
            self.time_steps = sim.time_steps

    def _load_metadata(self, sim_metadata_json):
        """ Load only the relevant parameters from the metadata JSON file. """
        if not os.path.exists(sim_metadata_json):
            raise FileNotFoundError(f"The metadata file {sim_metadata_json} does not exist.")
        
        with open(sim_metadata_json, 'r') as f:
            metadata = json.load(f)
        
        # Extract only the relevant parameters from the JSON file
        parameters = metadata.get('parameters', {})
        extracted_params = {
            'alpha': parameters.get('alpha'),
            'gamma': parameters.get('gamma'),
            'phi': parameters.get('phi'),
            'theta': parameters.get('theta'),
            'mu': parameters.get('mu'),
            'eta1': parameters.get('eta1'),
            'eta2': parameters.get('eta2'),
            'mem_span': parameters.get('mem_span'),
        }
        
        # Optionally, validate if all required parameters are present
        missing_params = [key for key, value in extracted_params.items() if value is None]
        if missing_params:
            raise ValueError(f"Missing parameters in metadata: {', '.join(missing_params)}")

        return extracted_params
    def _read_simulation_results(self, sim_results_csv_path):
        """ Read the simulation results from the .csv file and store them in self.status_dicts. """
        if not os.path.exists(sim_results_csv_path):
            raise FileNotFoundError(f"The simulation results file {sim_results_csv_path} does not exist.")
        
        status_dicts = []
        timesteps = 0

        with open(sim_results_csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                timestep = int(row['timestep'])
                # Create a dictionary for the status values at this timestep
                status = {
                    'timestep': timestep,
                    'S': int(row['S']),
                    'Is': int(row['Is']),
                    'Ir': int(row['Ir']),
                    'R': int(row['R']),
                    'E': int(row['E'])
                }
                status_dicts.append(status)
                timesteps += 1
        
        return status_dicts, timesteps
    
    def fit_skewed_gaussian_curve(self, status):
        # https://en.wikipedia.org/wiki/Skew_normal_distribution
        xdata = np.linspace(0, self.timesteps, self.timesteps + 1)
        ydata = self.status_dicts[status]

        parameters, covariance = curve_fit(skewed_gaussian, xdata, ydata)
        fit = skewed_gaussian(xdata, parameters[0], parameters[1], parameters[2])
        return fit, parameters, covariance

    # TODO Calculate skewness, kurtosis and so on so forth
    # TODO: I think that R is a CDF of normal distribution
    # TODO: Calculate peak time
    # TODO: Find nice way to present a summarized data
