# simcronomicon

[![codecov](https://codecov.io/gh/warisa-r/simcronomicon/graph/badge.svg?token=S13D4OWJ39)](https://codecov.io/gh/warisa-r/simcronomicon)
[![CI](https://github.com/warisa-r/simcronomicon/actions/workflows/ci.yml/badge.svg)](https://github.com/warisa-r/simcronomicon/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://warisa-r.github.io/simcronomicon/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-312/)

**simcronomicon** is a comprehensive agent-based spread simulation framework for modeling disease spread in realistic spatial environments using geographical data from OpenStreetMap.

## Key Features

### Advanced Disease Models
- **SEIR Model**: Classic Susceptible-Exposed-Infectious-Recovered compartmental modeling
- **SEIQRDV Model**: Extended model with Quarantine, Death, and Vaccination compartments
- **Spatial Dynamics**: Realistic agent movement patterns on real-world geographical networks
- **Population Dynamics**: Immigration, natural deaths, and birth rate modeling

### Realistic Simulation Environment
- **Real Geographic Data**: Import from OpenStreetMap via GraphML format
- **Complex Place Types**: Hospitals, schools, restaurants, accommodations, and more
- **Agent Heterogeneity**: Individual characteristics affecting disease transmission and movement
- **Priority Places**: Agents actively seek specific locations (e.g., healthcare for vaccination)

### Intervention Modeling
- **Vaccination Campaigns**: Limited hospital capacity, queue management, and vaccination seeking behavior
- **Quarantine Policies**: Movement restrictions for symptomatic individuals
- **Population Controls**: Immigration policies and natural population dynamics

### Analysis & Visualization
- **Real-time Tracking**: Individual agent status and location logging
- **Interactive Visualizations**: Agent movement on maps, disease progression charts
- **Statistical Analysis**: Infection rates, vaccination effectiveness, quarantine outcomes
- **Data Export**: HDF5 format for detailed analysis and reproducibility

## Quick Start

## Installation with conda

1. Clone the repository (if you haven't already):

```bash
git clone https://github.com/warisa-r/simcronomicon.git
cd simcronomicon
```

2. Create and activate the conda environment:

```bash
conda env create -f environment.yml
conda activate simcronomicon-env
```

3. Install the package normally, use:
```bash
pip install .
```

Install the package in development mode (if you want to edit the code):

```bash
pip install -e .
```

4. Verify the installation:

```bash 
python -c "import simcronomicon; print(simcronomicon.__version__)"
```

### Basic Usage

```python
import simcronomicon as scon

# Load town from real geographic data
town = scon.Town.from_files(
    config_path="config.json",
    town_graph_path="town.graphmlz",
    town_params=scon.TownParameters(population=1000, spreaders=10)
)

# Configure disease model
params = scon.SEIQRDVModelParameters(
    beta=0.3,           # Transmission rate
    alpha=0.1,          # Vaccination seeking rate
    gamma=5,            # Incubation period
    delta=3,            # Days to quarantine
    kappa=0.05,         # Disease mortality
    hospital_capacity=20 # Vaccines per facility per day
)

# Define agent interactions
step_events = [
    scon.StepEvent("daily_routine", scon.FolkSEIQRDV.interact, 
                   scon.EventType.DISPERSE, 9000, ['accommodation'])
]

# Run simulation
model = scon.SEIQRDVModel(params, step_events)
simulation = scon.Simulation(town, model, timesteps=180)  # 6 months
simulation.run()

# Analyze results
scon.plot_status_summary_from_hdf5("simulation_output.h5")
scon.visualize_folks_on_map_from_sim("simulation_output.h5", "town.graphmlz")
```

## Example Applications

### Vaccination Campaign Analysis
Model the effectiveness of different vaccination strategies:
- **Hospital capacity constraints**: How do limited resources affect vaccination rates?
- **Geographic accessibility**: Which areas have poor healthcare access?
- **Population behavior**: How does vaccination seeking behavior impact outcomes?

### Quarantine Policy Evaluation
Assess quarantine effectiveness:
- **Timing**: Optimal days from symptom onset to quarantine
- **Compliance**: Movement restriction effectiveness
- **Mortality outcomes**: Recovery vs. death rates in quarantine

### Long-term Endemic Patterns
Study disease persistence with:
- **Population turnover**: Immigration and natural deaths

## Documentation

- **[Full Documentation](https://warisa-r.github.io/simcronomicon/)**: Complete API reference and tutorials
- **[Tutorial Notebooks](examples/)**: Step-by-step examples for common use cases
- **[Model Parameters Guide](docs/models.md)**: Detailed parameter explanations

## Architecture

```
simcronomicon/
├── compartmental_models/          # Disease models (SEIR, SEIQRDV)
├── town.py          # Geographic environment and agent management  
├── sim.py          # Simulation engine and event handling
└── visualization/  # Plotting and interactive visualizations
```

## Testing

Run the test suite:
```bash
pytest --cov=.
```

View coverage report:
```bash
pytest --cov=. --cov-report=html
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/simcronomicon.git`
3. Create a feature branch: `git checkout -b feature-name`
4. Make your changes and add tests
5. Submit a pull request

## Development TODO

- [ ] Reduce redundancy in test modules
- [ ] Write test for visualization
- [ ] Parameter comparison and "meta" of it all. Optimizing parameter.
- [ ] Result analysis module 
    - [ ] Identify peak infection time, peak length ([StackOverflow: Peak signal detection in realtime timeseries data](https://stackoverflow.com/questions/22583391/peak-signal-detection-in-realtime-timeseries-data))
    - [ ] Identify overall infection probability if you live in a node

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Authors

- **Warisa Roongaraya** - *Development Lead* - [GitHub](https://github.com/warisa-r)

See [AUTHORS.md](AUTHORS.md) for the full list of contributors.

## Citation

If you use simcronomicon in your research, please cite:

```bibtex
@software{simcronomicon2024,
  title={simcronomicon: Agent-based Epidemiological Simulation Framework},
  author={Roongaraya, Warisa},
  year={2025},
  url={https://github.com/warisa-r/simcronomicon}
}
```
---