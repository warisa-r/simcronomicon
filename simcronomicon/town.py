from . import nx

def create_town_graph(num_pop, town_density):
    #TODO: This is an input function -> must write check for all inputs
    return nx.erdos_renyi_graph(num_pop, town_density)

class Town():
    def __init__(self, town_graph, literacy, num_init_spreader):
        #TODO: This is an input function -> must write check for all inputs
        self.literacy = literacy
        self.num_init_spreader = num_init_spreader
        if not isinstance(town_graph, nx.classes.graph.Graph) or town_graph.is_directed == True:
            raise TypeError(f"town_graph must be an undirected graph of type networkx.classes.graph.Graph!")
        self.town_graph = town_graph
    def draw_town(self):
        nx.draw(self.town_graph)