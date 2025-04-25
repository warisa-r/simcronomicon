from . import nx

class Town():
    def __init__(self, town_graph, literacy, num_init_spreader):
        self.literacy = literacy
        self.num_init_spreader = num_init_spreader
        if not isinstance(town_graph, nx.classes.graph.Graph) or town_graph.is_directed == True:
                raise TypeError(f"town_graph must be an undirected graph of type networkx.classes.graph.Graph!")
        
    def draw_town(self):
        nx.draw(self.town_graph)