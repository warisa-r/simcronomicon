import simcronomicon as scon
import matplotlib.pyplot as plt

town_graph = scon.create_town_graph(8, 0.6)
town = scon.Town(town_graph, 0.4, 4)
sim_params = scon.SimulationParameters(0.4, 0.5, 0.5, 0.4, 0.7, 0.5, 0.8, 0.3)
sim = scon.Simulation(town, sim_params, 100)
sim.run()