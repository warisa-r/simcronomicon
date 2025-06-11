# Simcronomicon Examples

This folder contains hands-on tutorials and examples demonstrating the capabilities of the `simcronomicon` package for agent-based epidemiological modeling on spatial networks.

**We mostly use interactive plots via Plotly. Please make sure you have Plotly in your PC!**

## Available Tutorials

### Core Disease Modeling
- **[`basic_disease_spread.ipynb`](basic_disease_spread.ipynb)** - Introduction to SEIR compartmental modeling
  - Learn to create spatial networks from OpenStreetMap data
  - Understand agent-based disease transmission mechanics
  - Compare ABM results with theoretical ODE predictions
  - Visualize epidemic dynamics on real geographic networks

- **[`disease_spread_mobility.ipynb`](disease_spread_mobility.ipynb)** - Advanced mobility patterns and their impact on disease spread
  - Explore different mobility models (log-normal, exponential)

### Specialized Models
- **[`standard_disease_spread_vaccination.py`](standard_disease_spread_vaccination.py)** - SEIQRDV model with vaccination strategies
  - Vaccination campaign modeling
  - Hospital capacity constraints
  - Quarantine policy implementation

### Information Spread
- **[`rumor_spread.py`](rumor_spread.py)** - SEIsIrR model for information/rumor propagation
  - Social network information dynamics
  - Belief state transitions
  - Literacy and memory effects on information spread