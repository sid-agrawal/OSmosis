"""
IsoSearch Scenario Definitions

This file contains different starting scenarios for the IsoSearch algorithm.
Each scenario defines a starting graph, goals, constraints, and allowed transitions.
"""

from graph_transformations import NodeTransformations, EdgeTransformations
from generic_model import ModelGraph, ResourceType, VmrType, FileType, Permission


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
    
    def to_dict(self):
        """Convert constraint to dictionary for JSON serialization"""
        return {
            'constraint_type': self.constraint_type,
            'pd_id': self.pd_id,
            'resource_info': self.resource_info,
            'target_pd': self.target_pd,
            'properties': self.properties
        }


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
        elif self.name == "clone_vmr_resource":
            return self._find_clone_vmr_resource_candidates(graph, constraints)
        elif self.name == "replace_hold_edge":
            return self._find_replace_hold_edge_candidates(graph, constraints)
        elif self.name == "create_private_copy":
            return self._find_create_private_copy_candidates(graph, constraints)
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
                    if constraint.constraint_type == "requires_file_access":
                        pd_string = f"PD_{constraint.pd_id}"
                        if pd_string == from_node and to_node.startswith('FILE_'):
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
            if edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_'):
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
                        'resource_space': 'FILE_SPACE_1'  # Simplified
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
            if edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_'):
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
    
    def _find_clone_file_resource_candidates(self, graph, constraints):
        """Find shared FILE resources that can be cloned for privatization (Strategy 3: Constraint-Guided)"""
        candidates = []
        
        # Analyze constraint violations to guide candidate discovery
        violations = self._analyze_sharing_violations(graph, constraints)
        
        for violation in violations:
            resource = violation['resource']
            sharers = violation['sharers']
            constraint = violation['constraint']
            
            # Suggest cloning for each sharer
            for i, sharer in enumerate(sharers):
                new_va = hex(0x8000 + i * 0x1000)  # Generate unique VAs
                candidates.append({
                    'param_values': {
                        'source_resource': resource,
                        'new_va': new_va,
                        'target_pd': sharer
                    },
                    'target_description': f"clone {resource} as private copy for {sharer}",
                    'constraint_relevance': 0.9,  # High relevance for constraint violations
                    'addresses_violation': True
                })
        
        return candidates
    
    def _find_replace_hold_edge_candidates(self, graph, constraints):
        """Find HOLD edges that can be replaced to resolve sharing violations"""
        candidates = []
        
        # Find sharing violations
        violations = self._analyze_sharing_violations(graph, constraints)
        
        for violation in violations:
            resource = violation['resource']
            sharers = violation['sharers']
            
            for sharer in sharers:
                # Look for potential private replacement resources
                potential_replacements = self._find_potential_private_resources(graph, resource, sharer)
                
                for replacement in potential_replacements:
                    candidates.append({
                        'param_values': {
                            'pd': sharer,
                            'old_resource': resource,
                            'new_resource': replacement
                        },
                        'target_description': f"redirect {sharer} from {resource} to private {replacement}",
                        'constraint_relevance': 0.8,
                        'addresses_violation': True
                    })
        
        return candidates
    
    def _find_create_private_copy_candidates(self, graph, constraints):
        """Find opportunities to create private copies (combines clone + replace)"""
        candidates = []
        
        violations = self._analyze_sharing_violations(graph, constraints)
        
        for violation in violations:
            resource = violation['resource']
            sharers = violation['sharers']
            
            for sharer in sharers:
                candidates.append({
                    'param_values': {
                        'source_resource': resource,
                        'target_pd': sharer
                    },
                    'target_description': f"create private copy of {resource} for {sharer}",
                    'constraint_relevance': 1.0,  # Highest relevance - directly solves sharing
                    'addresses_violation': True
                })
        
        return candidates
    
    def _analyze_sharing_violations(self, graph, constraints):
        """Strategy 3: Analyze constraints to identify sharing violations"""
        violations = []
        
        for constraint in constraints:
            if constraint.constraint_type == "requires_file_access":
                pd_id = constraint.pd_id
                file_type = constraint.properties.get('file_type', 'any')
                pd_string = f"PD_{pd_id}"
                
                # Find resources this PD accesses
                pd_resources = []
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if from_node == pd_string and edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_'):
                        if self._matches_file_type(graph, to_node, file_type):
                            pd_resources.append(to_node)
                
                # Check for sharing violations
                for resource in pd_resources:
                    sharers = []
                    for from_node, to_node, edge_data in graph.g.edges(data=True):
                        if to_node == resource and edge_data.get('type') == 'HOLD':
                            sharers.append(from_node)
                    
                    if len(sharers) > 1:  # Shared resource found
                        violations.append({
                            'type': 'unwanted_sharing',
                            'constraint': constraint,
                            'resource': resource,
                            'sharers': sharers,
                            'severity': len(sharers) - 1,
                            'file_type': file_type
                        })
        
        # Sort by severity (most shared resources first)
        return sorted(violations, key=lambda x: x['severity'], reverse=True)
    
    def _matches_file_type(self, graph, resource, required_type):
        """Check if resource matches required FILE type"""
        if required_type == 'any':
            return True
        
        try:
            resource_data = graph.g.nodes[resource]
            if resource_data.get('type') == 'RESOURCE' and resource_data.get('data') == 'FILE':
                import json
                extra = json.loads(resource_data.get('extra', '{}'))
                actual_type = extra.get('vmr_type', '').upper()
                return actual_type == required_type.upper()
        except:
            pass
        
        return False
    
    def _find_potential_private_resources(self, graph, shared_resource, pd):
        """Find existing private resources that could replace shared access"""
        potential = []
        
        # Look for private FILE resources of same type that this PD could use
        try:
            shared_data = graph.g.nodes[shared_resource]
            import json
            shared_extra = json.loads(shared_data.get('extra', '{}'))
            shared_type = shared_extra.get('vmr_type')
            
            for node, data in graph.g.nodes(data=True):
                if (node.startswith('FILE_') and node != shared_resource and 
                    data.get('type') == 'RESOURCE' and data.get('data') == 'FILE'):
                    
                    node_extra = json.loads(data.get('extra', '{}'))
                    if node_extra.get('file_type') == shared_type:
                        # Check if this resource is private or could be made available
                        current_holders = []
                        for from_node, to_node, edge_data in graph.g.edges(data=True):
                            if to_node == node and edge_data.get('type') == 'HOLD':
                                current_holders.append(from_node)
                        
                        # If no holders or could be shared, it's a potential replacement
                        if len(current_holders) == 0:
                            potential.append(node)
        except:
            pass
        
        return potential
    
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
            elif self.name == "clone_vmr_resource":
                return self._apply_clone_vmr_resource(graph, param_values)
            elif self.name == "replace_hold_edge":
                return self._apply_replace_hold_edge(graph, param_values)
            elif self.name == "create_private_copy":
                return self._apply_create_private_copy(graph, param_values)
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
            
            # Find existing FILE space or create one
            vmr_spaces = [node for node, data in graph.g.nodes(data=True) 
                         if data.get('type') == 'RESOURCE_SPACE' and data.get('data') == 'FILE']
            
            if vmr_spaces:
                # Extract space ID from node name (e.g., "FILE_SPACE_1" -> 1)
                space_id = int(vmr_spaces[0].split('_')[-1])
            else:
                # Create new FILE space if none exists
                space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
            
            # Create new private resources
            new_resource1 = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP, "/tmp/private1.tmp", 10240)
            new_resource2 = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP, "/tmp/private2.tmp", 10240)
            
            # Add new HOLD edges
            pd1_id = int(pd1.split('_')[1])
            pd2_id = int(pd2.split('_')[1])
            EdgeTransformations.add_hold_edge(graph, Permission.R, pd1_id, ResourceType.FILE, space_id, new_resource1)
            EdgeTransformations.add_hold_edge(graph, Permission.R, pd2_id, ResourceType.FILE, space_id, new_resource2)
            
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
            
            # Find existing FILE space
            vmr_spaces = [node for node, data in graph.g.nodes(data=True) 
                         if data.get('type') == 'RESOURCE_SPACE' and data.get('data') == 'FILE']
            
            if vmr_spaces:
                space_id = int(vmr_spaces[0].split('_')[-1])
            else:
                space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
            
            # Add mediator access to resource
            resource_num = int(resource.split('_')[-1])
            EdgeTransformations.add_hold_edge(graph, Permission.R, mediator_pd, ResourceType.FILE, space_id, resource_num)
            
            # Add REQUEST edges
            pd1_id = int(pd1.split('_')[1])
            pd2_id = int(pd2.split('_')[1])
            EdgeTransformations.add_request_edge(graph, pd1_id, mediator_pd, ResourceType.FILE, space_id)
            EdgeTransformations.add_request_edge(graph, pd2_id, mediator_pd, ResourceType.FILE, space_id)
            
            return True
        except Exception as e:
            print(f"Error in add_mediator: {e}")
            return False
    
    def _apply_clone_file_resource(self, graph, param_values):
        """Apply clone_file_resource primitive - create private copy of FILE resource"""
        from graph_transformations import NodeTransformations
        from generic_model import FileType
        import json
        
        try:
            source_resource = param_values['source_resource']
            new_path = param_values['new_path'] 
            target_pd = param_values['target_pd']
            
            # Get source resource properties
            source_data = graph.g.nodes[source_resource]
            source_extra = json.loads(source_data.get('extra', '{}'))
            
            # Find FILE space
            file_space_id = self._find_file_space_for_resource(graph, source_resource)
            
            # Create new private resource with same properties but different path
            file_type = FileType[source_extra['file_type']]
            file_size = int(source_extra['size_bytes'])
            
            new_resource_id = NodeTransformations.add_file_resource(
                graph, file_space_id, file_type, new_path, file_size
            )
            
            print(f"  🔧 Cloned {source_resource} → FILE_{file_space_id}_{new_resource_id} for {target_pd}")
            return True
            
        except Exception as e:
            print(f"Error in clone_file_resource: {e}")
            return False
    
    def _apply_replace_hold_edge(self, graph, param_values):
        """Apply replace_hold_edge primitive - atomically replace HOLD edge target"""
        from graph_transformations import EdgeTransformations
        from generic_model import EdgeType, ResourceType, Permission
        
        try:
            pd = param_values['pd']
            old_resource = param_values['old_resource']
            new_resource = param_values['new_resource']
            
            # Find existing edge properties
            edge_data = None
            for from_node, to_node, data in graph.g.edges(data=True):
                if from_node == pd and to_node == old_resource and data.get('type') == 'HOLD':
                    edge_data = data
                    break
            
            if not edge_data:
                print(f"No HOLD edge found from {pd} to {old_resource}")
                return False
            
            permission = edge_data.get('permission', Permission.R)
            
            # Atomic replacement: remove old, add new
            EdgeTransformations.remove_edge(graph, pd, old_resource, EdgeType.HOLD)
            
            # Extract IDs for new edge
            pd_id = int(pd.split('_')[1])
            resource_id = int(new_resource.split('_')[-1])
            file_space_id = self._find_file_space_for_resource(graph, new_resource)
            
            EdgeTransformations.add_hold_edge(
                graph, permission, pd_id, ResourceType.FILE, file_space_id, resource_id
            )
            
            print(f"  🔧 Redirected {pd}: {old_resource} → {new_resource}")
            return True
            
        except Exception as e:
            print(f"Error in replace_hold_edge: {e}")
            return False
    
    def _apply_create_private_copy(self, graph, param_values):
        """Apply create_private_copy primitive - combines clone + replace"""
        try:
            source_resource = param_values['source_resource']
            target_pd = param_values['target_pd']
            
            # Generate unique VA for private copy
            import random
            new_va = hex(0x8000 + random.randint(0, 0x1000))
            
            # Step 1: Clone the resource
            clone_params = {
                'source_resource': source_resource,
                'new_va': new_va,
                'target_pd': target_pd
            }
            
            if not self._apply_clone_vmr_resource(graph, clone_params):
                return False
            
            # Find the newly created resource
            new_resource = self._find_latest_resource(graph, source_resource)
            
            # Step 2: Replace the HOLD edge
            replace_params = {
                'pd': target_pd,
                'old_resource': source_resource,
                'new_resource': new_resource
            }
            
            if not self._apply_replace_hold_edge(graph, replace_params):
                return False
            
            print(f"  🎯 Created private copy: {source_resource} → {new_resource} for {target_pd}")
            return True
            
        except Exception as e:
            print(f"Error in create_private_copy: {e}")
            return False
    
    def _find_file_space_for_resource(self, graph, resource):
        """Find the FILE space ID for a given resource"""
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == resource and edge_data.get('type') == 'SUBSET':
                # Extract space ID from node name
                return int(to_node.split('_')[-1])
        return 1  # Default to space 1
    
    def _find_latest_resource(self, graph, base_resource):
        """Find the most recently created resource similar to base_resource"""
        max_id = 0
        latest_resource = None
        
        for node in graph.g.nodes():
            if node.startswith('FILE_') and node != base_resource:
                try:
                    resource_id = int(node.split('_')[-1])
                    if resource_id > max_id:
                        max_id = resource_id
                        latest_resource = node
                except:
                    continue
        
        return latest_resource or base_resource
    
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
    "add_file_resource": Transition(
        name="add_file_resource",
        description="Create new FILE resource", 
        transition_type="primitive"
    ),
    "remove_file_resource": Transition(
        name="remove_file_resource",
        description="Remove FILE resource",
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
    ),
    
    # Enhanced Resource Management Primitives (Strategy 1)
    "clone_file_resource": Transition(
        name="clone_file_resource",
        description="Create private copy of existing FILE resource",
        transition_type="primitive"
    ),
    "replace_hold_edge": Transition(
        name="replace_hold_edge", 
        description="Atomically replace HOLD edge target resource",
        transition_type="primitive"
    ),
    "create_private_copy": Transition(
        name="create_private_copy",
        description="Create private FILE copy for specific PD",
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
    """Build a basic graph with 2 PDs each having 3 private FILE resources + 1 shared FILE resource"""
    graph = ModelGraph()
    
    # Add two protection domains
    pd1 = NodeTransformations.add_pd_node(graph, "user_process")
    pd2 = NodeTransformations.add_pd_node(graph, "database_server")
    
    # Add a FILE space
    file_space = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    
    # Create 3 private resources for PD1
    pd1_config = NodeTransformations.add_file_resource(graph, file_space, FileType.CONFIG, "/etc/user.conf", 1024)
    pd1_log = NodeTransformations.add_file_resource(graph, file_space, FileType.LOG, "/var/log/user.log", 2048)
    pd1_lib = NodeTransformations.add_file_resource(graph, file_space, FileType.LIBRARY, "/usr/lib/user.so", 8192)
    
    # Create 3 private resources for PD2  
    pd2_config = NodeTransformations.add_file_resource(graph, file_space, FileType.CONFIG, "/etc/database.conf", 4096)
    pd2_log = NodeTransformations.add_file_resource(graph, file_space, FileType.LOG, "/var/log/database.log", 6144)
    pd2_db = NodeTransformations.add_file_resource(graph, file_space, FileType.DATABASE, "/var/db/main.db", 12288)
    
    # Create 1 shared resource that both PDs access
    shared_buffer = NodeTransformations.add_file_resource(graph, file_space, FileType.TEMP, "/tmp/shared_buffer.tmp", 20480)
    
    # PD1 holds its 3 private resources
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.FILE, file_space, pd1_config)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.FILE, file_space, pd1_log)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.FILE, file_space, pd1_lib)
    
    # PD2 holds its 3 private resources
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.FILE, file_space, pd2_config)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.FILE, file_space, pd2_log)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.FILE, file_space, pd2_db)
    
    # Both PD1 and PD2 hold the shared resource (the security problem to solve)
    EdgeTransformations.add_hold_edge(graph, Permission.W, pd1, ResourceType.FILE, file_space, shared_buffer)
    EdgeTransformations.add_hold_edge(graph, Permission.W, pd2, ResourceType.FILE, file_space, shared_buffer)
    
    return graph


def build_high_sharing_graph():
    """Build a graph with 3 PDs sharing multiple FILE resources"""
    graph = ModelGraph()
    
    # Add three protection domains
    pd1 = NodeTransformations.add_pd_node(graph, "web_server")
    pd2 = NodeTransformations.add_pd_node(graph, "database")
    pd3 = NodeTransformations.add_pd_node(graph, "cache_service")
    
    # Add FILE space and multiple shared resources
    file_space = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    shared_config = NodeTransformations.add_file_resource(graph, file_space, FileType.CONFIG, "/etc/shared.conf", 2048)
    shared_log = NodeTransformations.add_file_resource(graph, file_space, FileType.LOG, "/var/log/shared.log", 1024)
    shared_lib = NodeTransformations.add_file_resource(graph, file_space, FileType.LIBRARY, "/usr/lib/shared.so", 15360)
    
    # All PDs share the config file
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.FILE, file_space, shared_config)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.FILE, file_space, shared_config)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd3, ResourceType.FILE, file_space, shared_config)
    
    # PD1 and PD2 share the log file
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.FILE, file_space, shared_log)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.FILE, file_space, shared_log)
    
    # PD2 and PD3 share the library
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd2, ResourceType.FILE, file_space, shared_lib)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd3, ResourceType.FILE, file_space, shared_lib)
    
    return graph


def build_authority_chain_graph():
    """Build a graph with a chain of authority relationships"""
    graph = ModelGraph()
    
    # Add four protection domains in authority hierarchy
    user_pd = NodeTransformations.add_pd_node(graph, "user_app")
    service_pd = NodeTransformations.add_pd_node(graph, "service_manager")
    kernel_pd = NodeTransformations.add_pd_node(graph, "kernel_module")
    root_pd = NodeTransformations.add_pd_node(graph, "root_authority")
    
    # Add FILE space and resources
    file_space = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    user_resource = NodeTransformations.add_file_resource(graph, file_space, FileType.CONFIG, "/etc/user.conf", 512)
    service_resource = NodeTransformations.add_file_resource(graph, file_space, FileType.EXECUTABLE, "/bin/service", 1024)
    kernel_resource = NodeTransformations.add_file_resource(graph, file_space, FileType.LOG, "/var/log/kernel.log", 1536)
    
    # Each PD holds its own resource
    EdgeTransformations.add_hold_edge(graph, Permission.R, user_pd, ResourceType.FILE, file_space, user_resource)
    EdgeTransformations.add_hold_edge(graph, Permission.R, service_pd, ResourceType.FILE, file_space, service_resource)
    EdgeTransformations.add_hold_edge(graph, Permission.R, kernel_pd, ResourceType.FILE, file_space, kernel_resource)
    
    # Create authority chain: user -> service -> kernel -> root
    EdgeTransformations.add_request_edge(graph, user_pd, service_pd, ResourceType.FILE, file_space)
    EdgeTransformations.add_request_edge(graph, service_pd, kernel_pd, ResourceType.FILE, file_space)
    EdgeTransformations.add_request_edge(graph, kernel_pd, root_pd, ResourceType.FILE, file_space)
    
    return graph


def build_high_attack_surface_graph():
    """Build a graph with many attack paths (high ASR) that can be systematically reduced"""
    graph = ModelGraph()
    
    # Add 4 protection domains representing different system components
    web_pd = NodeTransformations.add_pd_node(graph, "web_frontend")
    api_pd = NodeTransformations.add_pd_node(graph, "api_server") 
    db_pd = NodeTransformations.add_pd_node(graph, "database")
    admin_pd = NodeTransformations.add_pd_node(graph, "admin_panel")
    
    # Add FILE space and multiple shared resources (creates many HOLD edges = attack paths)
    file_space = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    
    # Shared memory for inter-service communication (high attack surface)
    shared_memory = NodeTransformations.add_file_resource(graph, file_space, FileType.TEMP, "/tmp/shared_mem.tmp", 30720)
    
    # Shared configuration space
    config_space = NodeTransformations.add_file_resource(graph, file_space, FileType.CONFIG, "/etc/shared_config.conf", 20480)
    
    # Shared log buffer
    log_buffer = NodeTransformations.add_file_resource(graph, file_space, FileType.LOG, "/var/log/shared.log", 15360)
    
    # Database connection pool (shared by multiple services)
    db_pool = NodeTransformations.add_file_resource(graph, file_space, FileType.DATABASE, "/var/db/conn_pool.db", 25600)
    
    # Session store (shared by web and admin)
    session_store = NodeTransformations.add_file_resource(graph, file_space, FileType.CACHE, "/var/cache/sessions.cache", 10240)
    
    # Create many HOLD edges (attack paths) - all services access shared resources
    # Web frontend accesses: shared memory, config, log buffer, session store
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.FILE, file_space, shared_memory)
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.FILE, file_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.FILE, file_space, log_buffer)
    EdgeTransformations.add_hold_edge(graph, Permission.R, web_pd, ResourceType.FILE, file_space, session_store)
    
    # API server accesses: shared memory, config, log buffer, db pool
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.FILE, file_space, shared_memory)
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.FILE, file_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.FILE, file_space, log_buffer)
    EdgeTransformations.add_hold_edge(graph, Permission.R, api_pd, ResourceType.FILE, file_space, db_pool)
    
    # Database accesses: config, log buffer, db pool
    EdgeTransformations.add_hold_edge(graph, Permission.R, db_pd, ResourceType.FILE, file_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, db_pd, ResourceType.FILE, file_space, log_buffer)
    EdgeTransformations.add_hold_edge(graph, Permission.R, db_pd, ResourceType.FILE, file_space, db_pool)
    
    # Admin panel accesses: config, session store, shared memory
    EdgeTransformations.add_hold_edge(graph, Permission.R, admin_pd, ResourceType.FILE, file_space, config_space)
    EdgeTransformations.add_hold_edge(graph, Permission.R, admin_pd, ResourceType.FILE, file_space, session_store)
    EdgeTransformations.add_hold_edge(graph, Permission.R, admin_pd, ResourceType.FILE, file_space, shared_memory)
    
    # Add some REQUEST edges (authority relationships) for additional attack paths
    # Web requests from API, API requests from DB, Admin has authority over all
    EdgeTransformations.add_request_edge(graph, web_pd, api_pd, ResourceType.FILE, file_space)
    EdgeTransformations.add_request_edge(graph, api_pd, db_pd, ResourceType.FILE, file_space)
    EdgeTransformations.add_request_edge(graph, admin_pd, web_pd, ResourceType.FILE, file_space)
    EdgeTransformations.add_request_edge(graph, admin_pd, api_pd, ResourceType.FILE, file_space)
    
    return graph


# Standard transition sets for easy reuse
BASIC_PRIMITIVES = ["add_pd", "remove_pd", "add_hold_edge", "remove_hold_edge", "add_request_edge", "remove_request_edge"]
BASIC_MULTISTEP = ["privatize_resource", "add_mediator"]
EXTENDED_PRIMITIVES = BASIC_PRIMITIVES + ["add_file_resource", "remove_file_resource", "add_resource_space"]
ENHANCED_PRIMITIVES = BASIC_PRIMITIVES + ["clone_file_resource", "replace_hold_edge", "create_private_copy"]
EXTENDED_MULTISTEP = BASIC_MULTISTEP


# Scenario definitions

SCENARIOS = {
    "basic_sharing": Scenario(
        name="Basic Resource Sharing",
        description="2 PDs each with 3 private FILE resources + 1 shared FILE resource",
        goals=[
            Goal("RSI", 0.3, "minimize", "PD_1,PD_2"),  # Target specific PD pair
            Goal("TCB", 0, "minimize", "PD_1"),         # Target specific PD
            Goal("ASR", 1.0, "minimize")                # System-wide goal
        ],
        constraints=[
            # Specific FILE access requirements
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "CONFIG", "min_size_kb": 3}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "DATABASE", "min_size_kb": 3}),
        ],
        allowed_primitives=[],  # No primitives allowed
        allowed_multistep=["privatize_resource", "add_mediator"],  # Only multi-step transformations
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "basic_sharing_primitive": Scenario(
        name="Basic Resource Sharing (Primitive Only)",
        description="Same as basic_sharing but using only primitive transitions to see if same outcome can be achieved",
        goals=[
            Goal("RSI", 0.3, "minimize", "PD_1,PD_2"),  # Target specific PD pair
            Goal("TCB", 0, "minimize", "PD_1"),         # Target specific PD
            Goal("ASR", 1.0, "minimize")                # System-wide goal
        ],
        constraints=[
            # Specific FILE access requirements (same as basic_sharing)
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "CONFIG", "min_size_kb": 3}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "DATABASE", "min_size_kb": 3}),
        ],
        allowed_primitives=ENHANCED_PRIMITIVES,  # Enhanced primitive operations
        allowed_multistep=[],  # No multi-step allowed
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "high_sharing": Scenario(
        name="High Resource Sharing",
        description="3 PDs sharing multiple FILE resources with complex sharing patterns",
        goals=[
            Goal("RSI", 0.2, "minimize", "PD_1,PD_2"),  # Target specific high-sharing pair
            Goal("ASR", 2.0, "minimize"),               # System-wide goal
            Goal("TCB", 1, "minimize", "PD_1")          # Target specific PD
        ],
        constraints=[
            # Specific resource access requirements
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "CONFIG", "min_size_kb": 5}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 3}),
            Constraint("requires_file_access", 3, "FILE", properties={"file_type": "LIBRARY", "min_size_kb": 1}),
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
            # FILE access requirements
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "CONFIG", "min_size_kb": 1}),
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
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
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
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
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
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "LOG", "min_size_kb": 2}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
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
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "TEMP", "min_size_kb": 10}),  # Web frontend
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 15}),   # API server
            Constraint("requires_file_access", 3, "FILE", properties={"file_type": "any", "min_size_kb": 5}),    # Database
            Constraint("requires_file_access", 4, "FILE", properties={"file_type": "CACHE", "min_size_kb": 5}),    # Admin panel
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

def create_file_access_constraint(pd_id, file_type="any", min_size_kb=1, permissions="R"):
    """Create a specific FILE access requirement constraint"""
    return Constraint(
        "requires_file_access", 
        pd_id, 
        "FILE", 
        properties={
            "file_type": file_type, 
            "min_size_kb": min_size_kb,
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
    supported_constraint_types = {"requires_file_access", "requires_communication"}
    
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