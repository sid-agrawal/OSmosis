"""
Input: 
* Two PDs
* Chain of RS --> RS 


Enumerate (PD1, PD2, chain = VA --> PA --> PPage, initial_rs = C, H, S, L)

# PASS_1
# Pick the depth of things
Enumerate (N1, N2, 
					 chain, 
					 initial_rs) --> list [G]:

assert N1.Type == N2.Type
	
	Shared RS:
			
				Gs = generate(N1.Type). # This will generate 6^K options.
				glist.append(Gs)
			
			for G in glist.append():
				G.add (rest of chain)
			
	Separate RS:
			if chain.len = 1:
				create last RS Node, add map edges.
				return
			# else
			
			RS1, RS2 = create 2 RSes
			- Create HOLD edges from N1 and N2 to the initial set of 
			resources to RS1 and RS2.
			- Create new resources(nodes) in the next layer)
			
			G = Enumerate (RS1, RS2, PA->page, 
			               initial = list of resources in the next layer)
			glist.append(G)
				
		return G
		
		
		
	generate (..)
	
	
		if type PDs
			Cycle through all combination of resources to PDs
	
		elif type RS
			Just mapp simple map edges?
"""

import networkx as nx
import matplotlib.pyplot as plt

class ModelGraph:
    def __init__(self):
        self.g = nx.MultiGraph()

    def add_node(self, node_id, **attributes):
        """
        Add a node to the graph with optional attributes and return the graph object for chaining.

        :param node_id: The unique identifier for the node
        :param attributes: Additional attributes to store in the node
        :return: self
        """
        self.g.add_node(node_id, **attributes)
        return self

    def add_edge(self, from_node, to_node, **attributes):
        """
        Add an edge to the graph with optional attributes and return the graph object for chaining.

        :param from_node: The starting node of the edge
        :param to_node: The ending node of the edge
        :param attributes: Additional attributes to store in the edge
        :return: self
        """
        self.g.add_edge(from_node, to_node, **attributes)
        return self

    def draw_graph(self, ax):
        # Draw the graph
        pos = nx.spring_layout(self.g)
        nx.draw(
            self.g,
            pos,
            with_labels=True,
            node_color="lightblue",
            edge_color="gray",
            node_size=2000,
            font_size=15,
            ax=ax
        )

def enumerate(
        n1: ModelGraph,
        n2: ModelGraph,
        chain: ModelGraph,
        ir: ModelGraph
) -> list[ModelGraph]:
    """



    
    : param n1 leaf node an existing graph. PD | Resource Space
    : param n2 leaf node an existing graph. PD | Resource Space
    : param chain Resource Space, for now assume it a linked list
    : param ir Initial set of resources
    
    :return return all the graphs possible
    
    
    """
    return [n1, n2, chain, ir]


if __name__ == "__main__":
    n1 = ModelGraph().add_node("P1")
    n2 = ModelGraph().add_node("P2")
    chain = (
        ModelGraph()
        .add_node("VA")
        .add_node("PA")
        .add_node("PPage")
        .add_edge("PA", "VA")
        .add_edge("PA", "PPage")
    )
    ir = ModelGraph().add_node("code").add_node("heap").add_node("stack")

    g_list = enumerate (n1, n2, chain, ir)

    fig, axs = plt.subplots(1, 4, figsize=(12, 6))
    for idx in range(len(g_list)):
        g = g_list[idx]
        print (f"printing: {type(g)}")
        g.draw_graph(axs[idx])
    plt.show()
