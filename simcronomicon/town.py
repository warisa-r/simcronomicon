from . import plt
import scipy
from . import nx

def create_town_graph_erdos_renyi(num_pop, town_density):
    if not isinstance(town_density, float) or not (0 <= town_density <= 1):
        raise TypeError("town_density must be a float between 0 and 1 (inclusive)!")

    if not isinstance(num_pop, int) or num_pop < 2:
        raise TypeError("num_pop must be an integer greater than or equal to 2!")
    
    return nx.erdos_renyi_graph(num_pop, town_density)

def create_town_graph_barabasi_albert(num_pop, m):
    if not isinstance(num_pop, int) or num_pop < 2:
        raise TypeError("num_pop must be an integer greater than or equal to 2!")
    return nx.barabasi_albert_graph(num_pop, m)

def create_town_graph_watts_strogatz(num_pop, k, p):
    if not isinstance(num_pop, int) or num_pop < 2:
        raise TypeError("num_pop must be an integer greater than or equal to 2!")
    return nx.watts_strogatz_graph(num_pop, k, p)

class Town():
    def __init__(self, town_graph, literacy, num_init_spreader, network_type = None):
        if not isinstance(town_graph, nx.classes.graph.Graph) or town_graph.is_directed():
            raise TypeError("town_graph must be an undirected graph of type networkx.classes.graph.Graph!")

        if not isinstance(literacy, float) or not (0 <= literacy <= 1):
            raise TypeError("literacy must be a float between 0 and 1 (inclusive)!")

        if not isinstance(num_init_spreader, int) or num_init_spreader < 1:
            raise TypeError("num_init_spreader must be an integer greater than or equal to 1!")

        self.literacy = literacy
        self.num_init_spreader = num_init_spreader
        
        self.town_graph = town_graph
        self.network_type = network_type

         # Initialize every node's 'folk' attribute to an empty list
        for node in self.town_graph.nodes():
            self.town_graph.nodes[node]['folk'] = []
    def draw_town(self):
        nx.draw(self.town_graph)
        plt.show()