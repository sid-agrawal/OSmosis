"""
IsoSearch Scenario Definitions

This file contains different starting scenarios for the IsoSearch algorithm.
Each scenario defines a starting graph, goals, constraints, and allowed transitions.
"""

from graph_transformations import NodeTransformations, EdgeTransformations
from generic_model import ModelGraph, ResourceType, VmrType, Permission


class Goal:
    """Goal structure for design space exploration with targeted metrics"""
    def __init__(self, metric_name, target_value, direction="minimize", target_spec=None):
        self.metric_name = metric_name  # e.g., "RSI", "TCB", "FR", "ASR"
        self.target_value = target_value  # e.g., 0.5, 10, etc.
        self.direction = direction  # "minimize" or "maximize"
        self.target_spec = target_spec  # For targeted goals: PD for TCB, PD pair for RSI/FR, None for ASR
    
    def __str__(self):
        if self.target_spec:
            return f"Goal({self.direction} {self.metric_name}[{self.target_spec}] to {self.target_value})"
        else:
            return f"Goal({self.direction} {self.metric_name} to {self.target_value})"


class Constraint:
    """Simple constraint structure for functional requirements"""
    def __init__(self, constraint_type, pd_id, resource_info=None):
        self.constraint_type = constraint_type  # e.g., "requires_resource", "must_communicate"
        self.pd_id = pd_id  # The PD this constraint applies to
        self.resource_info = resource_info  # Additional info (resource type, target PD, etc.)
    
    def __str__(self):
        return f"Constraint({self.constraint_type} for PD{self.pd_id}: {self.resource_info})"


class Transition:
    """Simple transition structure for allowed graph modifications"""
    def __init__(self, transition_type, description=""):
        self.transition_type = transition_type  # e.g., "privatize_resource", "add_mediator_pd"
        self.description = description  # Human-readable description
    
    def __str__(self):
        return f"Transition({self.transition_type}: {self.description})"


class Scenario:
    """Complete scenario definition for IsoSearch exploration"""
    def __init__(self, name, description, goals, constraints, transitions, graph_builder):
        self.name = name
        self.description = description
        self.goals = goals
        self.constraints = constraints
        self.transitions = transitions
        self.graph_builder = graph_builder  # Function that builds the starting graph
    
    def build_graph(self):
        """Build and return the starting graph for this scenario"""
        return self.graph_builder()
    
    def __str__(self):
        return f"Scenario({self.name}: {len(self.goals)} goals, {len(self.constraints)} constraints, {len(self.transitions)} transitions)"


# Graph builder functions for different scenarios

def build_basic_shared_resource_graph():
    """Build a basic graph with 2 PDs sharing 1 VMR resource + mediator"""
    graph = ModelGraph()
    
    # Add two protection domains
    pd1 = NodeTransformations.add_pd_node(graph, "user_process")
    pd2 = NodeTransformations.add_pd_node(graph, "database_server")
    
    # Add a VMR space and resource
    vmr_space = NodeTransformations.add_resource_space(graph, ResourceType.VMR)
    vmr_resource = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.HEAP, 10, 0x1000)
    
    # Add another VMR resource that will be shared
    shared_vmr = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.STACK, 5, 0x2000)
    
    # PD1 and PD2 both hold the shared resource (resource sharing dependency)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.VMR, vmr_space, shared_vmr)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.VMR, vmr_space, shared_vmr)
    
    # Add a mediator PD to create authority relationships
    mediator_pd = NodeTransformations.add_pd_node(graph, "mediator")
    
    # Mediator holds the first resource
    EdgeTransformations.add_hold_edge(graph, Permission.R, mediator_pd, ResourceType.VMR, vmr_space, vmr_resource)
    
    # PD1 requests access through mediator (authority relationship)
    EdgeTransformations.add_request_edge(graph, pd1, mediator_pd, ResourceType.VMR, vmr_space)
    
    return graph


def build_high_sharing_graph():
    """Build a graph with 3 PDs sharing multiple resources"""
    graph = ModelGraph()
    
    # Add three protection domains
    pd1 = NodeTransformations.add_pd_node(graph, "web_server")
    pd2 = NodeTransformations.add_pd_node(graph, "database")
    pd3 = NodeTransformations.add_pd_node(graph, "cache_service")
    
    # Add VMR space and multiple shared resources
    vmr_space = NodeTransformations.add_resource_space(graph, ResourceType.VMR)
    shared_heap = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.HEAP, 20, 0x1000)
    shared_stack = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.STACK, 10, 0x2000)
    shared_lib = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.LIB, 15, 0x3000)
    
    # All PDs share the heap
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.VMR, vmr_space, shared_heap)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.VMR, vmr_space, shared_heap)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd3, ResourceType.VMR, vmr_space, shared_heap)
    
    # PD1 and PD2 share the stack
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.VMR, vmr_space, shared_stack)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.VMR, vmr_space, shared_stack)
    
    # PD2 and PD3 share the library
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.VMR, vmr_space, shared_lib)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd3, ResourceType.VMR, vmr_space, shared_lib)
    
    return graph


def build_authority_chain_graph():
    """Build a graph with a chain of authority relationships"""
    graph = ModelGraph()
    
    # Add four protection domains in authority hierarchy
    user_pd = NodeTransformations.add_pd_node(graph, "user_app")
    service_pd = NodeTransformations.add_pd_node(graph, "service_manager")
    kernel_pd = NodeTransformations.add_pd_node(graph, "kernel_module")
    root_pd = NodeTransformations.add_pd_node(graph, "root_authority")
    
    # Add VMR space and resources
    vmr_space = NodeTransformations.add_resource_space(graph, ResourceType.VMR)
    user_resource = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.HEAP, 5, 0x1000)
    service_resource = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.PROGRAM, 10, 0x2000)
    kernel_resource = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.STACK, 15, 0x3000)
    
    # Each PD holds its own resource
    EdgeTransformations.add_hold_edge(graph, Permission.R, user_pd, ResourceType.VMR, vmr_space, user_resource)
    EdgeTransformations.add_hold_edge(graph, Permission.R, service_pd, ResourceType.VMR, vmr_space, service_resource)
    EdgeTransformations.add_hold_edge(graph, Permission.R, kernel_pd, ResourceType.VMR, vmr_space, kernel_resource)
    
    # Create authority chain: user -> service -> kernel -> root
    EdgeTransformations.add_request_edge(graph, user_pd, service_pd, ResourceType.VMR, vmr_space)
    EdgeTransformations.add_request_edge(graph, service_pd, kernel_pd, ResourceType.VMR, vmr_space)
    EdgeTransformations.add_request_edge(graph, kernel_pd, root_pd, ResourceType.VMR, vmr_space)
    
    return graph


def build_high_attack_surface_graph():
    """Build a graph with many attack paths (high ASR) that can be systematically reduced"""
    graph = ModelGraph()
    
    # Add 4 protection domains representing different system components
    web_pd = NodeTransformations.add_pd_node(graph, "web_frontend")
    api_pd = NodeTransformations.add_pd_node(graph, "api_server") 
    db_pd = NodeTransformations.add_pd_node(graph, "database")
    admin_pd = NodeTransformations.add_pd_node(graph, "admin_panel")
    
    # Add VMR space and multiple shared resources (creates many HOLD edges = attack paths)
    vmr_space = NodeTransformations.add_resource_space(graph, ResourceType.VMR)
    
    # Shared memory for inter-service communication (high attack surface)
    shared_memory = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.HEAP, 30, 0x1000)
    
    # Shared configuration space
    config_space = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.LIB, 20, 0x2000)
    
    # Shared log buffer
    log_buffer = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.STACK, 15, 0x3000)
    
    # Database connection pool (shared by multiple services)
    db_pool = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.HEAP, 25, 0x4000)
    
    # Session store (shared by web and admin)
    session_store = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.LIB, 10, 0x5000)
    
    # Create many HOLD edges (attack paths) - all services access shared resources
    # Web frontend accesses: shared memory, config, log buffer, session store
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.VMR, vmr_space, shared_memory)
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.VMR, vmr_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.VMR, vmr_space, log_buffer)
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.VMR, vmr_space, session_store)
    
    # API server accesses: shared memory, config, log buffer, db pool
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.VMR, vmr_space, shared_memory)
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.VMR, vmr_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.VMR, vmr_space, log_buffer)
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.VMR, vmr_space, db_pool)
    
    # Database accesses: config, log buffer, db pool
    EdgeTransformations.add_hold_edge(graph, Permission.R, db_pd, ResourceType.VMR, vmr_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, db_pd, ResourceType.VMR, vmr_space, log_buffer)
    EdgeTransformations.add_hold_edge(graph, Permission.R, db_pd, ResourceType.VMR, vmr_space, db_pool)
    
    # Admin panel accesses: config, session store, shared memory
    EdgeTransformations.add_hold_edge(graph, Permission.R, admin_pd, ResourceType.VMR, vmr_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, admin_pd, ResourceType.VMR, vmr_space, session_store)
    EdgeTransformations.add_hold_edge(graph, Permission.R, admin_pd, ResourceType.VMR, vmr_space, shared_memory)
    
    # Add some REQUEST edges (authority relationships) for additional attack paths
    # Web requests from API, API requests from DB, Admin has authority over all
    EdgeTransformations.add_request_edge(graph, web_pd, api_pd, ResourceType.VMR, vmr_space)
    EdgeTransformations.add_request_edge(graph, api_pd, db_pd, ResourceType.VMR, vmr_space)
    EdgeTransformations.add_request_edge(graph, admin_pd, web_pd, ResourceType.VMR, vmr_space)
    EdgeTransformations.add_request_edge(graph, admin_pd, api_pd, ResourceType.VMR, vmr_space)
    
    return graph


# Standard transition sets

BASIC_TRANSITIONS = [
    Transition("privatize_resource", "Make a shared resource private"),
    Transition("add_mediator_pd", "Add a PD between two communicating PDs"),
    Transition("remove_hold_edge", "Remove a hold relationship")
]

EXTENDED_TRANSITIONS = [
    Transition("privatize_resource", "Make a shared resource private"),
    Transition("add_mediator_pd", "Add a PD between two communicating PDs"),
    Transition("remove_hold_edge", "Remove a hold relationship"),
    # Future: could add more sophisticated transitions
]


# Scenario definitions

SCENARIOS = {
    "basic_sharing": Scenario(
        name="Basic Resource Sharing",
        description="2 PDs sharing 1 VMR resource with 1 mediator PD",
        goals=[
            Goal("RSI", 0.3, "minimize", "PD_1,PD_2"),  # Target specific PD pair
            Goal("TCB", 0, "minimize", "PD_1"),         # Target specific PD
            Goal("ASR", 1.0, "minimize")                # System-wide goal
        ],
        constraints=[
            Constraint("requires_resource", 1, "VMR")
        ],
        transitions=BASIC_TRANSITIONS,
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "high_sharing": Scenario(
        name="High Resource Sharing",
        description="3 PDs sharing multiple VMR resources with complex sharing patterns",
        goals=[
            Goal("RSI", 0.2, "minimize", "PD_1,PD_2"),  # Target specific high-sharing pair
            Goal("ASR", 2.0, "minimize"),               # System-wide goal
            Goal("TCB", 1, "minimize", "PD_1")          # Target specific PD
        ],
        constraints=[
            Constraint("requires_resource", 1, "VMR"),
            Constraint("requires_resource", 2, "VMR")
        ],
        transitions=BASIC_TRANSITIONS,
        graph_builder=build_high_sharing_graph
    ),
    
    "authority_chain": Scenario(
        name="Authority Chain",
        description="4 PDs in authority hierarchy to test fault radius optimization",
        goals=[
            Goal("FR", 3, "minimize", "PD_1,PD_4"),     # Target specific PD pair with long chain
            Goal("TCB", 2, "minimize", "PD_1"),         # Target leaf PD
            Goal("ASR", 1.5, "minimize")                # System-wide goal
        ],
        constraints=[
            Constraint("requires_resource", 1, "VMR")
        ],
        transitions=BASIC_TRANSITIONS,
        graph_builder=build_authority_chain_graph
    ),
    
    "rsi_focused": Scenario(
        name="RSI Optimization",
        description="Focus on minimizing resource sharing index",
        goals=[
            Goal("RSI", 0.1, "minimize", "PD_1,PD_2")   # Target the sharing pair
        ],
        constraints=[],
        transitions=BASIC_TRANSITIONS,
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "multi_objective": Scenario(
        name="Multi-Objective Optimization",
        description="Simultaneously optimize all metrics",
        goals=[
            Goal("RSI", 0.3, "minimize", "PD_1,PD_2"),  # Target sharing pair
            Goal("ASR", 1.0, "minimize"),               # System-wide
            Goal("TCB", 1, "minimize", "PD_1"),         # Target specific PD
            Goal("FR", 4, "minimize", "PD_1,PD_3")      # Target specific PD pair
        ],
        constraints=[
            Constraint("requires_resource", 1, "VMR")
        ],
        transitions=BASIC_TRANSITIONS,
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "attack_surface_reduction": Scenario(
        name="Attack Surface Reduction",
        description="Demonstrate systematic reduction of attack surface (ASR) in a complex multi-service system",
        goals=[
            Goal("ASR", 2.5, "minimize")   # System-wide ASR goal
        ],
        constraints=[
            Constraint("requires_resource", 1, "VMR"),  # Web frontend needs access
            Constraint("requires_resource", 2, "VMR")   # API server needs access
        ],
        transitions=BASIC_TRANSITIONS,
        graph_builder=build_high_attack_surface_graph
    )
}


def get_scenario(name):
    """Get a scenario by name"""
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Scenario '{name}' not found. Available scenarios: {available}")
    return SCENARIOS[name]


def list_scenarios():
    """List all available scenarios"""
    print("Available scenarios:")
    for name, scenario in SCENARIOS.items():
        print(f"  {name}: {scenario.description}")


if __name__ == "__main__":
    # Test scenario creation
    list_scenarios()
    
    # Test building a scenario
    scenario = get_scenario("basic_sharing")
    print(f"\nTesting scenario: {scenario}")
    graph = scenario.build_graph()
    print(f"Graph built: {graph.g.number_of_nodes()} nodes, {graph.g.number_of_edges()} edges")