import networkx as nx

def create_town(n_house, town_density):
    if town_density > 1:
        ValueError("Please input a value of town density that is between 0 and 1!")
    else: return nx.erdos_renyi_graph(n_house, town_density)

def draw_town(town):
    if type(town) is nx.classes.graph.Graph and town.is_directed() == False:
        nx.draw(town)
    else:
        TypeError("The input of the town must be an undirected graph!")