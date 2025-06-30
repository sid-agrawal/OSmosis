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
    """Enhanced constraint structure for functional requirements"""
    def __init__(self, constraint_type, pd_id, resource_info=None, target_pd=None, properties=None):
        self.constraint_type = constraint_type  # e.g., "requires_vmr_access", "requires_communication"
        self.pd_id = pd_id  # The PD this constraint applies to
        self.resource_info = resource_info  # Resource specifications (type, properties, etc.)
        self.target_pd = target_pd  # For authority/communication constraints
        self.properties = properties or {}  # Additional constraint properties
    
    def __str__(self):
        if self.target_pd:
            return f"Constraint({self.constraint_type} for PD_{self.pd_id} -> PD_{self.target_pd}: {self.resource_info})"
        elif self.properties:
            return f"Constraint({self.constraint_type} for PD_{self.pd_id}: {self.resource_info}, {self.properties})"
        else:
            return f"Constraint({self.constraint_type} for PD_{self.pd_id}: {self.resource_info})"


class Primitive:
    """Single primitive operation for graph modification"""
    def __init__(self, operation, **params):
        self.operation = operation  # e.g., "add_pd", "remove_hold_edge"
        self.params = params  # Parameters with $ placeholders for binding
    
    def bind_parameters(self, param_values):
        """Replace $ placeholders with actual values"""
        bound_params = {}
        for key, value in self.params.items():
            if isinstance(value, str) and value.startswith('$'):
                param_name = value[1:]  # Remove $
                if param_name in param_values:
                    bound_params[key] = param_values[param_name]
                else:
                    raise ValueError(f"Missing parameter value for {param_name}")
            else:
                bound_params[key] = value
        return bound_params
    
    def __str__(self):
        return f"Primitive({self.operation}, {self.params})"


class Transition:
    """Unified transition structure for both primitive and multi-step operations"""
    def __init__(self, name, description, transition_type, primitives=None, parameters=None):
        self.name = name
        self.description = description
        self.transition_type = transition_type  # "primitive" or "multistep"
        self.primitives = primitives or []  # List of Primitive objects for multistep
        self.parameters = parameters or []  # Required parameters for multistep
    
    def find_candidates(self, graph, constraints):
        """Find all valid parameter bindings for this transition"""
        if self.transition_type == "primitive":
            return self._find_primitive_candidates(graph, constraints)
        else:
            return self._find_multistep_candidates(graph, constraints)
    
    def _find_primitive_candidates(self, graph, constraints):
        """Find candidates for primitive operations"""
        if self.name == "remove_hold_edge":
            return self._find_remove_hold_edge_candidates(graph, constraints)
        elif self.name == "add_pd":
            return self._find_add_pd_candidates(graph, constraints)
        # Add other primitives as needed
        return []
    
    def _find_multistep_candidates(self, graph, constraints):
        """Find candidates for multi-step operations"""
        if self.name == "privatize_resource":
            return self._find_privatize_resource_candidates(graph, constraints)
        elif self.name == "add_mediator":
            return self._find_add_mediator_candidates(graph, constraints)
        return []
    
    def _find_remove_hold_edge_candidates(self, graph, constraints):
        """Find HOLD edges that can be safely removed"""
        candidates = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'HOLD':
                # Check if removal violates constraints
                can_remove = True
                for constraint in constraints:
                    if constraint.constraint_type == "requires_vmr_access":
                        pd_string = f"PD_{constraint.pd_id}"
                        if pd_string == from_node and to_node.startswith('VMR_'):
                            can_remove = False
                            break
                
                if can_remove:
                    candidates.append({
                        'param_values': {'from_node': from_node, 'to_node': to_node},
                        'target_description': f"remove {from_node} -> {to_node} HOLD edge"
                    })
        return candidates
    
    def _find_add_pd_candidates(self, graph, constraints):
        """Find opportunities to add new PDs"""
        # Simple implementation - always allow adding one PD
        return [{
            'param_values': {'pd_type': 'new_component'},
            'target_description': "add new protection domain"
        }]
    
    def _find_privatize_resource_candidates(self, graph, constraints):
        """Find shared resources that can be privatized"""
        candidates = []
        resource_holders = {}
        
        # Find shared resources
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'HOLD' and to_node.startswith('VMR_'):
                if to_node not in resource_holders:
                    resource_holders[to_node] = []
                resource_holders[to_node].append(from_node)
        
        # Find resources shared by exactly 2 PDs
        for resource, holders in resource_holders.items():
            if len(holders) == 2:
                candidates.append({
                    'param_values': {
                        'resource': resource,
                        'pd1': holders[0], 
                        'pd2': holders[1],
                        'resource_space': 'VMR_SPACE_1'  # Simplified
                    },
                    'target_description': f"privatize {resource} shared by {holders[0]}, {holders[1]}"
                })
        
        return candidates
    
    def _find_add_mediator_candidates(self, graph, constraints):
        """Find resources that could benefit from mediation"""
        candidates = []
        resource_holders = {}
        
        # Find shared resources
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'HOLD' and to_node.startswith('VMR_'):
                if to_node not in resource_holders:
                    resource_holders[to_node] = []
                resource_holders[to_node].append(from_node)
        
        # Find resources shared by exactly 2 PDs
        for resource, holders in resource_holders.items():
            if len(holders) == 2:
                candidates.append({
                    'param_values': {
                        'resource': resource,
                        'pd1': holders[0],
                        'pd2': holders[1],
                        'mediator_pd': f"PD_{len([n for n in graph.g.nodes() if n.startswith('PD_')]) + 1}"
                    },
                    'target_description': f"add mediator for {resource} between {holders[0]}, {holders[1]}"
                })
        
        return candidates
    
    def apply(self, graph, param_values):
        """Apply the transition with given parameter values"""
        if self.transition_type == "primitive":
            return self._apply_primitive(graph, param_values)
        else:
            return self._apply_multistep(graph, param_values)
    
    def _apply_primitive(self, graph, param_values):
        """Apply primitive operation"""
        try:
            if self.name == "remove_hold_edge":
                from graph_transformations import EdgeTransformations
                from generic_model import EdgeType
                EdgeTransformations.remove_edge(
                    graph,
                    param_values['from_node'],
                    param_values['to_node'], 
                    EdgeType.HOLD
                )
                return True
            elif self.name == "add_pd":
                from graph_transformations import NodeTransformations
                NodeTransformations.add_pd_node(graph, param_values.get('pd_type', 'new_component'))
                return True
            # Add other primitive implementations as needed
            else:
                print(f"Primitive {self.name} not yet implemented")
                return False
        except Exception as e:
            print(f"Error applying primitive {self.name}: {e}")
            return False
    
    def _apply_multistep(self, graph, param_values):
        """Apply sequence of primitives"""
        try:
            if self.name == "privatize_resource":
                return self._apply_privatize_resource(graph, param_values)
            elif self.name == "add_mediator":
                return self._apply_add_mediator(graph, param_values)
            else:
                print(f"Multi-step {self.name} not yet implemented")
                return False
        except Exception as e:
            print(f"Error applying multi-step {self.name}: {e}")
            return False
    
    def _apply_privatize_resource(self, graph, param_values):
        """Apply privatize_resource transformation"""
        from graph_transformations import NodeTransformations, EdgeTransformations
        from generic_model import EdgeType, ResourceType, VmrType, Permission
        
        try:
            resource = param_values['resource']
            pd1 = param_values['pd1'] 
            pd2 = param_values['pd2']
            
            # Get original resource properties (simplified)
            original_data = graph.g.nodes[resource]
            
            # Remove existing HOLD edges
            EdgeTransformations.remove_edge(graph, pd1, resource, EdgeType.HOLD)
            EdgeTransformations.remove_edge(graph, pd2, resource, EdgeType.HOLD)
            
            # Find existing VMR space or create one
            vmr_spaces = [node for node, data in graph.g.nodes(data=True) 
                         if data.get('type') == 'RESOURCE_SPACE' and data.get('data') == 'VMR']
            
            if vmr_spaces:
                # Extract space ID from node name (e.g., "VMR_SPACE_1" -> 1)
                space_id = int(vmr_spaces[0].split('_')[-1])
            else:
                # Create new VMR space if none exists
                space_id = NodeTransformations.add_resource_space(graph, ResourceType.VMR)
            
            # Create new private resources
            new_resource1 = NodeTransformations.add_vmr_resource(graph, space_id, VmrType.HEAP, 10, 0x3000)
            new_resource2 = NodeTransformations.add_vmr_resource(graph, space_id, VmrType.HEAP, 10, 0x4000)
            
            # Add new HOLD edges
            pd1_id = int(pd1.split('_')[1])
            pd2_id = int(pd2.split('_')[1])
            EdgeTransformations.add_hold_edge(graph, Permission.R, pd1_id, ResourceType.VMR, space_id, new_resource1)
            EdgeTransformations.add_hold_edge(graph, Permission.R, pd2_id, ResourceType.VMR, space_id, new_resource2)
            
            return True
        except Exception as e:
            print(f"Error in privatize_resource: {e}")
            return False
    
    def _apply_add_mediator(self, graph, param_values):
        """Apply add_mediator transformation"""
        from graph_transformations import NodeTransformations, EdgeTransformations
        from generic_model import EdgeType, ResourceType, Permission
        
        try:
            resource = param_values['resource']
            pd1 = param_values['pd1']
            pd2 = param_values['pd2']
            
            # Create mediator PD
            mediator_pd = NodeTransformations.add_pd_node(graph, "mediator")
            
            # Remove direct access
            EdgeTransformations.remove_edge(graph, pd1, resource, EdgeType.HOLD)
            EdgeTransformations.remove_edge(graph, pd2, resource, EdgeType.HOLD)
            
            # Find existing VMR space
            vmr_spaces = [node for node, data in graph.g.nodes(data=True) 
                         if data.get('type') == 'RESOURCE_SPACE' and data.get('data') == 'VMR']
            
            if vmr_spaces:
                space_id = int(vmr_spaces[0].split('_')[-1])
            else:
                space_id = NodeTransformations.add_resource_space(graph, ResourceType.VMR)
            
            # Add mediator access to resource
            resource_num = int(resource.split('_')[-1])
            EdgeTransformations.add_hold_edge(graph, Permission.R, mediator_pd, ResourceType.VMR, space_id, resource_num)
            
            # Add REQUEST edges
            pd1_id = int(pd1.split('_')[1])
            pd2_id = int(pd2.split('_')[1])
            EdgeTransformations.add_request_edge(graph, pd1_id, mediator_pd, ResourceType.VMR, space_id)
            EdgeTransformations.add_request_edge(graph, pd2_id, mediator_pd, ResourceType.VMR, space_id)
            
            return True
        except Exception as e:
            print(f"Error in add_mediator: {e}")
            return False
    
    def __str__(self):
        if self.transition_type == "primitive":
            return f"Transition({self.name}: {self.description})"
        else:
            return f"MultiStepTransition({self.name}: {len(self.primitives)} steps)"


class Scenario:
    """Complete scenario definition for IsoSearch exploration"""
    def __init__(self, name, description, goals, constraints, allowed_primitives=None, allowed_multistep=None, graph_builder=None):
        self.name = name
        self.description = description
        self.goals = goals
        self.constraints = constraints
        self.allowed_primitives = allowed_primitives or []
        self.allowed_multistep = allowed_multistep or []
        self.graph_builder = graph_builder  # Function that builds the starting graph
    
    def build_graph(self):
        """Build and return the starting graph for this scenario"""
        return self.graph_builder()
    
    def get_allowed_transitions(self):
        """Get all allowed transitions for this scenario"""
        transitions = []
        
        # Add allowed primitives
        for primitive_name in self.allowed_primitives:
            if primitive_name in PRIMITIVE_TRANSITIONS:
                transitions.append(PRIMITIVE_TRANSITIONS[primitive_name])
        
        # Add allowed multi-step
        for multistep_name in self.allowed_multistep:
            if multistep_name in MULTISTEP_TRANSITIONS:
                transitions.append(MULTISTEP_TRANSITIONS[multistep_name])
        
        return transitions
    
    def __str__(self):
        total_transitions = len(self.allowed_primitives) + len(self.allowed_multistep)
        return f"Scenario({self.name}: {len(self.goals)} goals, {len(self.constraints)} constraints, {total_transitions} transitions)"


# Primitive Transition Definitions
PRIMITIVE_TRANSITIONS = {
    # Node Operations
    "add_pd": Transition(
        name="add_pd",
        description="Create new Protection Domain",
        transition_type="primitive"
    ),
    "remove_pd": Transition(
        name="remove_pd", 
        description="Remove existing Protection Domain",
        transition_type="primitive"
    ),
    "add_vmr_resource": Transition(
        name="add_vmr_resource",
        description="Create new VMR resource", 
        transition_type="primitive"
    ),
    "remove_vmr_resource": Transition(
        name="remove_vmr_resource",
        description="Remove VMR resource",
        transition_type="primitive"
    ),
    "add_resource_space": Transition(
        name="add_resource_space",
        description="Create new resource space",
        transition_type="primitive"
    ),
    
    # Edge Operations
    "add_hold_edge": Transition(
        name="add_hold_edge",
        description="Create PD → Resource relationship",
        transition_type="primitive"
    ),
    "remove_hold_edge": Transition(
        name="remove_hold_edge",
        description="Remove PD → Resource relationship", 
        transition_type="primitive"
    ),
    "add_request_edge": Transition(
        name="add_request_edge",
        description="Create PD → PD authority relationship",
        transition_type="primitive"
    ),
    "remove_request_edge": Transition(
        name="remove_request_edge",
        description="Remove PD → PD authority relationship",
        transition_type="primitive"
    )
}

# Multi-Step Transition Definitions
MULTISTEP_TRANSITIONS = {
    "privatize_resource": Transition(
        name="privatize_resource",
        description="Remove shared access and create private copies",
        transition_type="multistep",
        primitives=[
            Primitive("remove_hold_edge", source="$pd1", target="$resource"),
            Primitive("remove_hold_edge", source="$pd2", target="$resource"),
            Primitive("add_vmr_resource", space="$resource_space", vmr_type="$vmr_type", pages="$pages", va="$va1"),
            Primitive("add_vmr_resource", space="$resource_space", vmr_type="$vmr_type", pages="$pages", va="$va2"),
            Primitive("add_hold_edge", source="$pd1", target="$new_resource1"),
            Primitive("add_hold_edge", source="$pd2", target="$new_resource2")
        ],
        parameters=["pd1", "pd2", "resource", "resource_space", "vmr_type", "pages", "va1", "va2", "new_resource1", "new_resource2"]
    ),
    
    "add_mediator": Transition(
        name="add_mediator", 
        description="Insert mediator PD between sharers",
        transition_type="multistep",
        primitives=[
            Primitive("add_pd", pd_type="mediator"),
            Primitive("remove_hold_edge", source="$pd1", target="$resource"),
            Primitive("remove_hold_edge", source="$pd2", target="$resource"),
            Primitive("add_hold_edge", source="$mediator_pd", target="$resource"),
            Primitive("add_request_edge", source="$pd1", target="$mediator_pd"),
            Primitive("add_request_edge", source="$pd2", target="$mediator_pd")
        ],
        parameters=["pd1", "pd2", "resource", "mediator_pd"]
    )
}

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


# Standard transition sets for easy reuse
BASIC_PRIMITIVES = ["add_pd", "remove_pd", "add_hold_edge", "remove_hold_edge", "add_request_edge", "remove_request_edge"]
BASIC_MULTISTEP = ["privatize_resource", "add_mediator"]
EXTENDED_PRIMITIVES = BASIC_PRIMITIVES + ["add_vmr_resource", "remove_vmr_resource", "add_resource_space"]
EXTENDED_MULTISTEP = BASIC_MULTISTEP


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
            # Specific VMR access requirements
            Constraint("requires_vmr_access", 1, "VMR", properties={"vmr_type": "STACK", "min_pages": 1}),
            Constraint("requires_vmr_access", 2, "VMR", properties={"vmr_type": "any", "min_pages": 1}),
            # Communication requirements  
            Constraint("requires_communication", 1, "REQUEST", target_pd=3),  # PD_1 must communicate with PD_3
        ],
        allowed_primitives=[],  # No primitives allowed
        allowed_multistep=["privatize_resource", "add_mediator"],  # Only multi-step transformations
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
            # Specific resource access requirements
            Constraint("requires_vmr_access", 1, "VMR", properties={"vmr_type": "HEAP", "min_pages": 5}),
            Constraint("requires_vmr_access", 2, "VMR", properties={"vmr_type": "any", "min_pages": 3}),
            Constraint("requires_vmr_access", 3, "VMR", properties={"vmr_type": "LIB", "min_pages": 1}),
        ],
        allowed_primitives=BASIC_PRIMITIVES,  # Only primitive operations
        allowed_multistep=[],  # No multi-step allowed
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
            # VMR access requirements
            Constraint("requires_vmr_access", 1, "VMR", properties={"vmr_type": "HEAP", "min_pages": 1}),
            # Authority chain requirements (user_app -> service_manager -> kernel_module -> root_authority)
            Constraint("requires_communication", 1, "REQUEST", target_pd=2),  # PD_1 -> PD_2
            Constraint("requires_communication", 2, "REQUEST", target_pd=3),  # PD_2 -> PD_3  
            Constraint("requires_communication", 3, "REQUEST", target_pd=4),  # PD_3 -> PD_4
        ],
        allowed_primitives=BASIC_PRIMITIVES,  # Only primitive operations
        allowed_multistep=[],  # No multi-step allowed
        graph_builder=build_authority_chain_graph
    ),
    
    "rsi_focused": Scenario(
        name="RSI Optimization",
        description="Focus on minimizing resource sharing index",
        goals=[
            Goal("RSI", 0.1, "minimize", "PD_1,PD_2")   # Target the sharing pair
        ],
        constraints=[
            # Minimal constraints - allow maximum optimization freedom
            Constraint("requires_vmr_access", 1, "VMR", properties={"vmr_type": "any", "min_pages": 1}),
            Constraint("requires_vmr_access", 2, "VMR", properties={"vmr_type": "any", "min_pages": 1}),
        ],
        allowed_primitives=[],  # No primitives allowed
        allowed_multistep=["privatize_resource"],  # Only privatization for RSI focus
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "mediator_test": Scenario(
        name="Mediator Test",
        description="Test add_mediator functionality specifically",
        goals=[
            Goal("RSI", 0.8, "minimize", "PD_1,PD_2")   # High threshold to allow mediator
        ],
        constraints=[
            Constraint("requires_vmr_access", 1, "VMR", properties={"vmr_type": "any", "min_pages": 1}),
            Constraint("requires_vmr_access", 2, "VMR", properties={"vmr_type": "any", "min_pages": 1}),
        ],
        allowed_primitives=[],  # No primitives allowed
        allowed_multistep=["add_mediator"],  # Only mediator
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
            # Balanced constraints for multi-objective optimization
            Constraint("requires_vmr_access", 1, "VMR", properties={"vmr_type": "STACK", "min_pages": 2}),
            Constraint("requires_vmr_access", 2, "VMR", properties={"vmr_type": "any", "min_pages": 1}),
            # Communication constraint that creates the TCB challenge
            Constraint("requires_communication", 1, "REQUEST", target_pd=3),
        ],
        allowed_primitives=BASIC_PRIMITIVES,  # Both primitive and multi-step allowed
        allowed_multistep=BASIC_MULTISTEP,    # Full flexibility for multi-objective
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "attack_surface_reduction": Scenario(
        name="Attack Surface Reduction",
        description="Demonstrate systematic reduction of attack surface (ASR) in a complex multi-service system",
        goals=[
            Goal("ASR", 2.5, "minimize")   # System-wide ASR goal
        ],
        constraints=[
            # Service-specific resource requirements
            Constraint("requires_vmr_access", 1, "VMR", properties={"vmr_type": "HEAP", "min_pages": 10}),  # Web frontend
            Constraint("requires_vmr_access", 2, "VMR", properties={"vmr_type": "any", "min_pages": 15}),   # API server
            Constraint("requires_vmr_access", 3, "VMR", properties={"vmr_type": "any", "min_pages": 5}),    # Database
            Constraint("requires_vmr_access", 4, "VMR", properties={"vmr_type": "LIB", "min_pages": 5}),    # Admin panel
            # Service communication requirements
            Constraint("requires_communication", 1, "REQUEST", target_pd=2),  # Web -> API
            Constraint("requires_communication", 2, "REQUEST", target_pd=3),  # API -> DB
            Constraint("requires_communication", 4, "REQUEST", target_pd=1),  # Admin -> Web
            Constraint("requires_communication", 4, "REQUEST", target_pd=2),  # Admin -> API
        ],
        allowed_primitives=["remove_hold_edge"],  # Only edge removal for ASR reduction
        allowed_multistep=[],  # No multi-step allowed
        graph_builder=build_high_attack_surface_graph
    )
}


# Helper functions for common constraint patterns

def create_vmr_access_constraint(pd_id, vmr_type="any", min_pages=1, permissions="R"):
    """Create a specific VMR access requirement constraint"""
    return Constraint(
        "requires_vmr_access", 
        pd_id, 
        "VMR", 
        properties={
            "vmr_type": vmr_type, 
            "min_pages": min_pages,
            "permissions": permissions
        }
    )

def create_communication_constraint(source_pd, target_pd, communication_type="REQUEST"):
    """Create a communication requirement constraint"""
    return Constraint(
        "requires_communication",
        source_pd,
        communication_type,
        target_pd=target_pd
    )



def get_scenario(name):
    """Get a scenario by name"""
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Scenario '{name}' not found. Available scenarios: {available}")
    
    scenario = SCENARIOS[name]
    _validate_scenario_constraints(scenario)
    return scenario


def _validate_scenario_constraints(scenario):
    """Validate that all constraint types in a scenario are supported by the implementation"""
    supported_constraint_types = {"requires_vmr_access", "requires_communication"}
    
    for constraint in scenario.constraints:
        if constraint.constraint_type not in supported_constraint_types:
            raise ValueError(f"Unsupported constraint type '{constraint.constraint_type}' in scenario '{scenario.name}'. "
                           f"Supported types: {supported_constraint_types}")
    
    print(f"✓ Validated {len(scenario.constraints)} constraints in scenario '{scenario.name}'")


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