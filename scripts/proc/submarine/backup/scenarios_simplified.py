"""
Simplified scenarios for clearer analysis
"""

from scenarios import Scenario, Goal, Constraint, Transition, PRIMITIVES
from generic_model import ModelGraph, ResourceType, FileType, Permission
from graph_transformations import NodeTransformations, EdgeTransformations


def build_minimal_shared_resource_graph():
    """Build the simplest possible shared resource scenario"""
    graph = ModelGraph()
    
    # Add two protection domains
    pd1 = NodeTransformations.add_pd_node(graph, "user_process")
    pd2 = NodeTransformations.add_pd_node(graph, "database_server")
    
    # Add FILE space
    file_space = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    
    # Add ONLY the shared file - no other files
    shared_file = NodeTransformations.add_file_resource(
        graph, file_space, FileType.TEMP, "/tmp/shared_buffer.tmp", 2048
    )
    
    # Both PDs hold the shared file
    EdgeTransformations.add_hold_edge(graph, Permission.RW, pd1, ResourceType.FILE, file_space, shared_file)
    EdgeTransformations.add_hold_edge(graph, Permission.RW, pd2, ResourceType.FILE, file_space, shared_file)
    
    return graph


# Add the simplified scenario
SIMPLIFIED_SCENARIOS = {
    "minimal_sharing": Scenario(
        name="Minimal Resource Sharing",
        description="Simplest case: 2 PDs sharing 1 file, no other files",
        goals=[
            Goal("RSI", 0.0, "minimize", "PD_1,PD_2"),  # Perfect isolation
            Goal("ASR", 1.0, "minimize"),               # Minimal attack surface
            Goal("TCB", 0, "minimize", "PD_1"),         # No dependencies
        ],
        constraints=[
            # Both PDs need access to the shared file
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "TEMP", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "TEMP", "min_size_kb": 1}),
        ],
        allowed_primitives=PRIMITIVES,  # All atomic graph operations
        allowed_multistep=[],  # No multi-step allowed
        graph_builder=build_minimal_shared_resource_graph
    )
}


def get_simplified_scenario(name):
    """Get a simplified scenario by name"""
    if name not in SIMPLIFIED_SCENARIOS:
        available = ", ".join(SIMPLIFIED_SCENARIOS.keys())
        raise ValueError(f"Simplified scenario '{name}' not found. Available: {available}")
    
    return SIMPLIFIED_SCENARIOS[name]


def list_simplified_scenarios():
    """List all available simplified scenarios"""
    print("Available simplified scenarios:")
    for name, scenario in SIMPLIFIED_SCENARIOS.items():
        print(f"  {name}: {scenario.description}")


if __name__ == "__main__":
    # Test the simplified scenario
    list_simplified_scenarios()
    
    scenario = get_simplified_scenario("minimal_sharing")
    print(f"\nTesting scenario: {scenario.name}")
    
    graph = scenario.build_graph()
    print(f"Graph built: {graph.g.number_of_nodes()} nodes, {graph.g.number_of_edges()} edges")
    
    # Show graph structure
    print("\nGraph structure:")
    for node, data in graph.g.nodes(data=True):
        print(f"  {node}: {data}")
    
    print("\nEdges:")
    for from_node, to_node, data in graph.g.edges(data=True):
        print(f"  {from_node} -> {to_node}: {data}")