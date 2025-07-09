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
    """Constraint structure for functional requirements"""
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
        # Node operations
        if self.name == "add_pd":
            return self._find_add_pd_candidates(graph, constraints)
        elif self.name == "remove_pd":
            return self._find_remove_pd_candidates(graph, constraints)
        elif self.name == "add_file_resource":
            return self._find_add_file_resource_candidates(graph, constraints)
        elif self.name == "remove_file_resource":
            return self._find_remove_file_resource_candidates(graph, constraints)
        elif self.name == "add_resource_space":
            return self._find_add_resource_space_candidates(graph, constraints)
        elif self.name == "remove_resource_space":
            return self._find_remove_resource_space_candidates(graph, constraints)
        # Edge operations
        elif self.name == "add_hold_edge":
            return self._find_add_hold_edge_candidates(graph, constraints)
        elif self.name == "remove_hold_edge":
            return self._find_remove_hold_edge_candidates(graph, constraints)
        elif self.name == "add_request_edge":
            return self._find_add_request_edge_candidates(graph, constraints)
        elif self.name == "remove_request_edge":
            return self._find_remove_request_edge_candidates(graph, constraints)
        elif self.name == "add_subset_edge":
            return self._find_add_subset_edge_candidates(graph, constraints)
        elif self.name == "remove_subset_edge":
            return self._find_remove_subset_edge_candidates(graph, constraints)
        
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
                # Smart constraint checking: allow removal if PD has alternatives
                can_remove = self._can_safely_remove_hold_edge(graph, from_node, to_node, constraints)
                
                if can_remove:
                    candidates.append({
                        'param_values': {'from_node': from_node, 'to_node': to_node},
                        'target_description': f"remove {from_node} -> {to_node} HOLD edge"
                    })
        return candidates
    
    def _can_safely_remove_hold_edge(self, graph, from_pd, to_resource, constraints):
        """Check if removing a HOLD edge would violate constraints"""
        import json
        
        # FIRST: Check if there's a prohibit_direct_hold constraint that REQUIRES this removal
        pd_id = int(from_pd.split('_')[1]) if from_pd.startswith('PD_') else None
        if pd_id is not None:
            for constraint in constraints:
                if (constraint.constraint_type == "prohibit_direct_hold" and 
                    constraint.pd_id == pd_id and 
                    constraint.resource_info == to_resource):
                    # This edge is explicitly prohibited - removal is strongly encouraged
                    return True
        
        # Get the resource type being removed
        if not to_resource.startswith('FILE_'):
            return True  # Not a file, safe to remove
        
        resource_data = graph.g.nodes.get(to_resource, {})
        extra_str = resource_data.get('extra', '{}')
        try:
            extra_data = json.loads(extra_str) if extra_str else {}
        except (json.JSONDecodeError, TypeError):
            extra_data = {}
        resource_type = extra_data.get('file_type', 'UNKNOWN')
        
        # Check if this PD has constraints requiring this resource type
        if pd_id is None:
            return True
        
        has_constraint_for_type = False
        for constraint in constraints:
            if (constraint.constraint_type == "requires_file_access" and 
                constraint.pd_id == pd_id):
                required_type = constraint.properties.get('file_type', 'any')
                if required_type == resource_type or required_type == 'any':
                    has_constraint_for_type = True
                    break
        
        if not has_constraint_for_type:
            return True  # No constraint requires this type, safe to remove
        
        # Check if PD has other resources of the same type
        alternative_count = 0
        for other_from, other_to, other_edge in graph.g.edges(data=True):
            if (other_from == from_pd and other_to != to_resource and 
                other_edge.get('type') == 'HOLD' and other_to.startswith('FILE_')):
                other_data = graph.g.nodes.get(other_to, {})
                other_extra_str = other_data.get('extra', '{}')
                try:
                    other_extra = json.loads(other_extra_str) if other_extra_str else {}
                except (json.JSONDecodeError, TypeError):
                    other_extra = {}
                if other_extra.get('file_type') == resource_type:
                    alternative_count += 1
        
        # Allow removal if PD has at least one alternative of the same type
        return alternative_count > 0
    
    def _find_add_pd_candidates(self, graph, constraints):
        """Simplified PD addition - let mediation emerge naturally"""
        candidates = []
        
        # SIMPLIFIED APPROACH: Check if we have constraint violations that might benefit from new PDs
        # Let the scoring system and constraints naturally guide toward mediation
        
        from constraint_validation import validate_constraint
        has_violations = False
        violation_count = 0
        
        for constraint in constraints:
            try:
                is_satisfied, _ = validate_constraint(graph, constraint)
                if not is_satisfied:
                    has_violations = True
                    violation_count += 1
            except:
                # If validation fails, assume there might be violations
                has_violations = True
                violation_count += 1
        
        # Always suggest adding a PD, but with different priorities based on violations
        if has_violations:
            # Higher priority when violations exist - system needs help
            constraint_relevance = 0.7
            description = f"add new protection domain to help resolve {violation_count} constraint violation(s)"
            addresses_violation = True
        else:
            # Lower priority when no violations - just system expansion
            constraint_relevance = 0.3
            description = "add new protection domain for system expansion"
            addresses_violation = False
        
        candidates.append({
            'param_values': {'pd_type': 'new_component'},
            'target_description': description,
            'constraint_relevance': constraint_relevance,
            'addresses_violation': addresses_violation
        })
        
        return candidates
    
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
    
    def _find_add_hold_edge_candidates(self, graph, constraints):
        """Simplified HOLD edge addition - minimal special logic"""
        candidates = []
        
        # Find PDs that could connect to existing resources
        pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']
        resources = [node for node, data in graph.g.nodes(data=True) 
                    if data.get('type') == 'RESOURCE' and data.get('data') == 'FILE']
        
        for pd in pds:
            current_resources = self._get_pd_held_resources(graph, pd)
            
            for resource in resources:
                if resource not in current_resources:
                    # Check prohibit_direct_hold constraints
                    prohibited = self._is_connection_prohibited(pd, resource, constraints)
                    
                    if not prohibited:
                        # Simplified scoring - no complex mediation logic
                        constraint_relevance = 0.4  # Standard score for all connections
                        addresses_violation = False
                        description = f"connect {pd} to {resource}"
                        
                        # Significant boost for orphaned resources needed for constraints
                        holders = self._get_resource_holders(graph, resource)
                        if len(holders) == 0:
                            # Check if this orphaned resource is needed by constraint violations
                            constraint_relevance = 0.8  # Higher priority for orphaned resources
                            description = f"connect {pd} to orphaned resource {resource}"
                        
                        candidates.append({
                            'param_values': {'pd': pd, 'resource': resource, 'permission': 'R'},
                            'target_description': description,
                            'constraint_relevance': constraint_relevance,
                            'addresses_violation': addresses_violation
                        })
        
        return candidates
    
    def _find_add_file_resource_candidates(self, graph, constraints):
        """Find opportunities to add new FILE resources"""
        candidates = []
        
        # Find FILE spaces where we could add resources
        file_spaces = [node for node, data in graph.g.nodes(data=True) 
                      if data.get('type') == 'RESOURCE_SPACE' and data.get('data') == 'FILE']
        
        if file_spaces:
            file_space = file_spaces[0]  # Use first available FILE space
            
            # Generate candidates for different file types that might help
            file_types = ['CONFIG', 'DATABASE', 'TEMP', 'LOG']
            for file_type in file_types:
                candidates.append({
                    'param_values': {
                        'file_space': file_space,
                        'file_type': file_type,
                        'file_path': f"/tmp/new_{file_type.lower()}.tmp",
                        'file_size': 1024
                    },
                    'target_description': f"create new {file_type} file in {file_space}"
                })
        
        return candidates
    
    def _find_remove_file_resource_candidates(self, graph, constraints):
        """Find FILE resources that can be safely removed"""
        candidates = []
        
        # Find FILE resources
        for node, data in graph.g.nodes(data=True):
            if data.get('type') == 'RESOURCE' and data.get('data') == 'FILE':
                # Check if any PD currently holds this resource
                holders = []
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if to_node == node and edge_data.get('type') == 'HOLD':
                        holders.append(from_node)
                
                # Only suggest removal if no PD depends on it, or if it's shared (might want to eliminate sharing)
                if len(holders) == 0 or len(holders) > 1:
                    candidates.append({
                        'param_values': {'resource': node},
                        'target_description': f"remove {node} (holders: {len(holders)})"
                    })
        
        return candidates
    
    def _find_remove_pd_candidates(self, graph, constraints):
        """Find PDs that can be safely removed"""
        candidates = []
        
        for node, data in graph.g.nodes(data=True):
            if data.get('type') == 'PD':
                # Check if this PD has any HOLD edges (resources it depends on)
                has_resources = False
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if from_node == node and edge_data.get('type') == 'HOLD':
                        has_resources = True
                        break
                
                # Only suggest removal if PD has no resource dependencies
                if not has_resources:
                    candidates.append({
                        'param_values': {'pd': node},
                        'target_description': f"remove empty {node}"
                    })
        
        return candidates
    
    def _find_add_resource_space_candidates(self, graph, constraints):
        """Find opportunities to add new resource spaces"""
        candidates = []
        
        # Simple implementation - suggest adding FILE space if none exists
        file_spaces = [node for node, data in graph.g.nodes(data=True) 
                      if data.get('type') == 'RESOURCE_SPACE' and data.get('data') == 'FILE']
        
        if len(file_spaces) == 0:
            candidates.append({
                'param_values': {'resource_type': 'FILE'},
                'target_description': "create new FILE resource space"
            })
        
        return candidates
    
    def _find_remove_resource_space_candidates(self, graph, constraints):
        """Find resource spaces that can be safely removed"""
        candidates = []
        
        for node, data in graph.g.nodes(data=True):
            if data.get('type') == 'RESOURCE_SPACE':
                # Check if any resources are connected to this space
                has_resources = False
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if to_node == node and edge_data.get('type') == 'SUBSET':
                        has_resources = True
                        break
                
                # Only suggest removal if no resources depend on this space
                if not has_resources:
                    candidates.append({
                        'param_values': {'resource_space': node},
                        'target_description': f"remove empty {node}"
                    })
        
        return candidates
    
    def _find_add_request_edge_candidates(self, graph, constraints):
        """Simplified REQUEST edge addition - let patterns emerge naturally"""
        candidates = []
        
        pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']
        
        for from_pd in pds:
            for to_pd in pds:
                if from_pd != to_pd:
                    # Check if REQUEST edge already exists
                    if self._request_edge_exists(graph, from_pd, to_pd):
                        continue
                    
                    # Simplified scoring - no complex mediation detection
                    constraint_relevance = 0.2  # Lower priority for authority relationships
                    description = f"add authority relationship: {from_pd} -> {to_pd}"
                    addresses_violation = False
                    
                    # Small boost if to_pd has resources that from_pd might need
                    to_pd_resources = self._get_pd_held_resources(graph, to_pd)
                    if to_pd_resources:
                        constraint_relevance = 0.3  # Slight preference for potential indirect access
                        description = f"enable indirect access: {from_pd} -> {to_pd}"
                    
                    candidates.append({
                        'param_values': {'from_pd': from_pd, 'to_pd': to_pd},
                        'target_description': description,
                        'constraint_relevance': constraint_relevance,
                        'addresses_violation': addresses_violation
                    })
        
        return candidates
    
    def _find_remove_request_edge_candidates(self, graph, constraints):
        """Find REQUEST edges that can be removed"""
        candidates = []
        
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'REQUEST':
                candidates.append({
                    'param_values': {'from_pd': from_node, 'to_pd': to_node},
                    'target_description': f"remove authority {from_node} -> {to_node}"
                })
        
        return candidates
    
    def _find_add_subset_edge_candidates(self, graph, constraints):
        """Find opportunities to add SUBSET edges (Resource -> ResourceSpace)"""
        candidates = []
        
        resources = [node for node, data in graph.g.nodes(data=True) 
                    if data.get('type') == 'RESOURCE']
        spaces = [node for node, data in graph.g.nodes(data=True) 
                 if data.get('type') == 'RESOURCE_SPACE']
        
        for resource in resources:
            resource_data = graph.g.nodes[resource]
            resource_type = resource_data.get('data', 'UNKNOWN')
            
            for space in spaces:
                space_data = graph.g.nodes[space]
                space_type = space_data.get('data', 'UNKNOWN')
                
                # Check if types match and edge doesn't exist
                if resource_type == space_type:
                    edge_exists = False
                    for from_node, to_node, edge_data in graph.g.edges(data=True):
                        if (from_node == resource and to_node == space and 
                            edge_data.get('type') == 'SUBSET'):
                            edge_exists = True
                            break
                    
                    if not edge_exists:
                        candidates.append({
                            'param_values': {'resource': resource, 'resource_space': space},
                            'target_description': f"connect {resource} to {space}"
                        })
        
        return candidates
    
    def _find_remove_subset_edge_candidates(self, graph, constraints):
        """Find SUBSET edges that can be removed"""
        candidates = []
        
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'SUBSET':
                candidates.append({
                    'param_values': {'resource': from_node, 'resource_space': to_node},
                    'target_description': f"disconnect {from_node} from {to_node}"
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
            elif self.name == "add_hold_edge":
                from graph_transformations import EdgeTransformations
                from generic_model import Permission, ResourceType
                
                # Extract PD ID and resource ID for EdgeTransformations
                pd_string = param_values['pd']
                resource_string = param_values['resource']
                
                # Extract numeric IDs
                pd_id = int(pd_string.split('_')[1]) if pd_string.startswith('PD_') else 1
                resource_id = int(resource_string.split('_')[-1]) if resource_string.startswith('FILE_') else 1
                
                # Extract resource space ID (default to 1 for FILE_SPACE_1)  
                resource_space_id = 1
                
                EdgeTransformations.add_hold_edge(
                    graph, 
                    Permission.R,  # Default permission
                    pd_id,
                    ResourceType.FILE,  # Use enum instead of string
                    resource_space_id,
                    resource_id
                )
                return True
            elif self.name == "add_file_resource":
                from graph_transformations import NodeTransformations
                from generic_model import FileType
                
                try:
                    file_type = getattr(FileType, param_values['file_type'])
                except AttributeError:
                    print(f"Error: Invalid file_type '{param_values['file_type']}'. Available: {[ft.name for ft in FileType]}")
                    return False
                
                # Extract file space ID from node name (e.g., 'FILE_SPACE_1' -> 1)
                file_space_name = param_values['file_space']
                if file_space_name.startswith('FILE_SPACE_'):
                    file_space_id = int(file_space_name.split('_')[-1])
                else:
                    file_space_id = 1  # Default
                
                result = NodeTransformations.add_file_resource(
                    graph,
                    file_space_id,
                    file_type,
                    param_values['file_path'],
                    param_values.get('file_size', 1024)
                )
                return result is not None
            elif self.name == "remove_file_resource":
                from graph_transformations import NodeTransformations
                import json
                # Remove the resource node and its edges
                resource = param_values['resource']
                
                # Check constraints before removal - find which PDs currently hold this resource
                current_holders = []
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if to_node == resource and edge_data.get('type') == 'HOLD':
                        current_holders.append(from_node)
                
                # Get the file type of the resource being removed
                resource_data = graph.g.nodes[resource]
                resource_extra = json.loads(resource_data.get('extra', '{}'))
                resource_file_type = resource_extra.get('file_type', 'UNKNOWN')
                
                # Check if any PD has a constraint requiring this file type
                for holder in current_holders:
                    pd_id = int(holder.split('_')[1]) if holder.startswith('PD_') else None
                    if pd_id is not None:
                        # Check if this PD has any other resources of the same type
                        other_resources_of_type = []
                        for from_node, to_node, edge_data in graph.g.edges(data=True):
                            if (from_node == holder and to_node != resource and 
                                edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_')):
                                other_data = graph.g.nodes[to_node]
                                other_extra = json.loads(other_data.get('extra', '{}'))
                                if other_extra.get('file_type') == resource_file_type:
                                    other_resources_of_type.append(to_node)
                        
                        # If this PD has no other resources of this type, allow removal but warn
                        if len(other_resources_of_type) == 0:
                            # Allow removal for exploration purposes, but note the impact
                            print(f"Warning: Removing {resource} will leave {holder} without {resource_file_type} files")
                            # Continue with removal - let constraint validation catch violations later
                
                # If we get here, removal is safe
                # Remove all edges connected to this resource
                edges_to_remove = []
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if from_node == resource or to_node == resource:
                        edges_to_remove.append((from_node, to_node))
                
                for from_node, to_node in edges_to_remove:
                    graph.g.remove_edge(from_node, to_node)
                
                # Remove the resource node
                graph.g.remove_node(resource)
                return True
            elif self.name == "remove_pd":
                # Remove PD node and all its edges
                pd = param_values['pd']
                
                # Remove all edges connected to this PD
                edges_to_remove = []
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if from_node == pd or to_node == pd:
                        edges_to_remove.append((from_node, to_node))
                
                for from_node, to_node in edges_to_remove:
                    graph.g.remove_edge(from_node, to_node)
                
                # Remove the PD node
                graph.g.remove_node(pd)
                return True
            elif self.name == "add_resource_space":
                from graph_transformations import NodeTransformations
                from generic_model import ResourceType
                resource_type = getattr(ResourceType, param_values['resource_type'])
                NodeTransformations.add_resource_space(graph, resource_type)
                return True
            elif self.name == "remove_resource_space":
                # Remove resource space node and all its edges
                space = param_values['resource_space']
                
                # Remove all edges connected to this space
                edges_to_remove = []
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if from_node == space or to_node == space:
                        edges_to_remove.append((from_node, to_node))
                
                for from_node, to_node in edges_to_remove:
                    graph.g.remove_edge(from_node, to_node)
                
                # Remove the space node
                graph.g.remove_node(space)
                return True
            elif self.name == "add_request_edge":
                from graph_transformations import EdgeTransformations
                from generic_model import ResourceType
                
                # Extract PD IDs from PD strings
                from_pd_string = param_values['from_pd']
                to_pd_string = param_values['to_pd']
                from_pd_id = int(from_pd_string.split('_')[1]) if from_pd_string.startswith('PD_') else 1
                to_pd_id = int(to_pd_string.split('_')[1]) if to_pd_string.startswith('PD_') else 1
                
                # Use FILE space 1 as default for REQUEST edges
                EdgeTransformations.add_request_edge(
                    graph, 
                    from_pd_id, 
                    to_pd_id, 
                    ResourceType.FILE, 
                    1  # space_id 
                )
                return True
            elif self.name == "remove_request_edge":
                from graph_transformations import EdgeTransformations
                from generic_model import EdgeType
                EdgeTransformations.remove_edge(
                    graph,
                    param_values['from_pd'],
                    param_values['to_pd'],
                    EdgeType.REQUEST
                )
                return True
            elif self.name == "add_subset_edge":
                from graph_transformations import EdgeTransformations
                from generic_model import EdgeType
                EdgeTransformations.add_edge(
                    graph,
                    param_values['resource'],
                    param_values['resource_space'],
                    EdgeType.SUBSET
                )
                return True
            elif self.name == "remove_subset_edge":
                from graph_transformations import EdgeTransformations
                from generic_model import EdgeType
                EdgeTransformations.remove_edge(
                    graph,
                    param_values['resource'],
                    param_values['resource_space'],
                    EdgeType.SUBSET
                )
                return True
            # Add other primitive implementations as needed
            else:
                print(f"Primitive {self.name} not yet implemented")
                return False
        except Exception as e:
            print(f"Error applying primitive {self.name}: {e}")
            import traceback
            traceback.print_exc()
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
    
    # ========== Mediation-Aware Helper Methods ==========
    
    def _find_orphaned_resources_needing_mediation(self, graph, constraints):
        """Find resources that have no holders but are required by constraints"""
        orphaned_resources = []
        
        # Find all resources that have no HOLD edges pointing to them
        resources = [node for node, data in graph.g.nodes(data=True) 
                    if data.get('type') == 'RESOURCE' and data.get('data') == 'FILE']
        
        for resource in resources:
            holders = self._get_resource_holders(graph, resource)
            
            # Check if any PD should have access to this resource based on constraints
            if len(holders) == 0:
                required_by_pds = self._get_pds_requiring_resource(resource, constraints)
                if required_by_pds:
                    orphaned_resources.append({
                        'resource': resource,
                        'required_by': required_by_pds,
                        'resource_type': self._get_resource_file_type(graph, resource)
                    })
        
        return orphaned_resources
    
    def _find_shared_resources_needing_mediation(self, graph, constraints):
        """Find shared resources that could benefit from mediation based on constraints"""
        shared_resources = []
        
        # Find resources with multiple holders that have prohibition constraints
        resource_holders = {}
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_'):
                if to_node not in resource_holders:
                    resource_holders[to_node] = []
                resource_holders[to_node].append(from_node)
        
        for resource, holders in resource_holders.items():
            if len(holders) > 1:  # Shared resource
                # Check if any PD is prohibited from directly holding this resource
                prohibited_pds = self._get_pds_prohibited_from_resource(resource, constraints)
                if prohibited_pds:
                    shared_resources.append({
                        'resource': resource,
                        'current_holders': holders,
                        'prohibited_holders': prohibited_pds,
                        'resource_type': self._get_resource_file_type(graph, resource)
                    })
        
        return shared_resources
    
    def _get_pd_held_resources(self, graph, pd):
        """Get all resources currently held by a PD"""
        resources = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd and edge_data.get('type') == 'HOLD':
                resources.append(to_node)
        return resources
    
    def _get_resource_holders(self, graph, resource):
        """Get all PDs that currently hold a resource"""
        holders = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if to_node == resource and edge_data.get('type') == 'HOLD':
                holders.append(from_node)
        return holders
    
    def _calculate_mediation_relevance(self, graph, pd, resource, constraints):
        """Calculate how relevant connecting this PD to this resource is for mediation"""
        score = 0.0
        
        # HIGHEST PRIORITY: Complete existing mediation patterns
        if self._is_orphaned_resource(graph, resource) and self._is_likely_mediator_pd(graph, pd):
            if self._is_resource_required_by_constraints(resource, constraints):
                score += 1.0  # Maximum priority for completing mediation
        
        # High score if this resource is orphaned and required by constraints
        elif self._is_orphaned_resource(graph, resource):
            if self._is_resource_required_by_constraints(resource, constraints):
                score += 0.8
        
        # Medium score if this would enable indirect access for constrained PDs
        if self._would_enable_indirect_access(graph, pd, resource, constraints):
            score += 0.6
        
        # Boost if this PD looks like it was recently created (likely for mediation)
        if self._is_likely_mediator_pd(graph, pd):
            score += 0.3
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _is_connection_prohibited(self, pd, resource, constraints):
        """Check if connecting this PD to this resource is prohibited by constraints"""
        for constraint in constraints:
            if constraint.constraint_type == "prohibit_direct_hold":
                pd_id = int(pd.split('_')[1]) if pd.startswith('PD_') else None
                if pd_id == constraint.pd_id and resource == constraint.resource_info:
                    return True
        return False
    
    def _is_orphaned_resource(self, graph, resource):
        """Check if a resource has no holders"""
        return len(self._get_resource_holders(graph, resource)) == 0
    
    def _would_enable_indirect_access(self, graph, mediator_pd, resource, constraints):
        """Check if connecting mediator_pd to resource would enable indirect access for constrained PDs"""
        # Look for constraints requiring indirect access to this resource
        for constraint in constraints:
            if constraint.constraint_type == "requires_resource_access":
                if constraint.resource_info == resource:
                    constrained_pd = f"PD_{constraint.pd_id}"
                    # Check if connecting mediator to resource + adding REQUEST edge would solve constraint
                    if not self._pd_has_access_to_resource(graph, constrained_pd, resource):
                        return True
        return False
    
    def _is_likely_mediator_pd(self, graph, pd):
        """Check if this PD looks like it was recently created for mediation purposes"""
        # Simple heuristic: PD with no current connections might be newly created
        outgoing_edges = 0
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd:
                outgoing_edges += 1
        return outgoing_edges == 0
    
    def _request_edge_exists(self, graph, from_pd, to_pd):
        """Check if a REQUEST edge already exists between two PDs"""
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if (from_node == from_pd and to_node == to_pd and 
                edge_data.get('type') == 'REQUEST'):
                return True
        return False
    
    def _analyze_request_edge_relevance(self, graph, from_pd, to_pd, constraints):
        """Analyze the relevance of adding a REQUEST edge for constraint solving"""
        constraint_relevance = 0.1  # Default low relevance
        addresses_violation = False
        description = f"add authority {from_pd} -> {to_pd}"
        
        # HIGHEST PRIORITY: Check if this would enable required indirect access
        for constraint in constraints:
            if constraint.constraint_type == "requires_resource_access":
                constrained_pd = f"PD_{constraint.pd_id}"
                required_resource = constraint.resource_info
                
                if from_pd == constrained_pd:
                    # Check if to_pd holds the required resource
                    if self._pd_has_access_to_resource(graph, to_pd, required_resource):
                        constraint_relevance = 0.9
                        addresses_violation = True
                        description = f"enable indirect access: {from_pd} -> {to_pd} for {required_resource}"
                        break
        
        # MEDIUM PRIORITY: Check if this completes a mediation pattern
        if constraint_relevance < 0.5:  # Only if not already high priority
            if self._would_complete_mediation_pattern(graph, from_pd, to_pd, constraints):
                constraint_relevance = 0.6
                addresses_violation = True
                description = f"complete mediation pattern: {from_pd} -> {to_pd}"
        
        return constraint_relevance, addresses_violation, description
    
    def _would_complete_mediation_pattern(self, graph, from_pd, to_pd, constraints):
        """Check if adding this REQUEST edge would complete a mediation pattern"""
        # Look for cases where from_pd is prohibited from direct access but to_pd has access
        for constraint in constraints:
            if constraint.constraint_type == "prohibit_direct_hold":
                constrained_pd = f"PD_{constraint.pd_id}"
                prohibited_resource = constraint.resource_info
                
                if from_pd == constrained_pd:
                    # Check if to_pd has access to the prohibited resource
                    if self._pd_has_access_to_resource(graph, to_pd, prohibited_resource):
                        return True
        return False
    
    def _get_pds_requiring_resource(self, resource, constraints):
        """Get list of PDs that require access to this resource based on constraints"""
        required_by = []
        
        # Check requires_resource_access constraints
        for constraint in constraints:
            if constraint.constraint_type == "requires_resource_access":
                if constraint.resource_info == resource:
                    required_by.append(f"PD_{constraint.pd_id}")
        
        # Check requires_file_access constraints that might apply to this resource
        resource_type = None  # Would need to get from graph
        for constraint in constraints:
            if constraint.constraint_type == "requires_file_access":
                file_type = constraint.properties.get('file_type', 'any')
                if file_type == 'any':  # This PD needs access to any file, including this one
                    required_by.append(f"PD_{constraint.pd_id}")
        
        return required_by
    
    def _get_pds_prohibited_from_resource(self, resource, constraints):
        """Get list of PDs that are prohibited from directly accessing this resource"""
        prohibited = []
        for constraint in constraints:
            if constraint.constraint_type == "prohibit_direct_hold":
                if constraint.resource_info == resource:
                    prohibited.append(f"PD_{constraint.pd_id}")
        return prohibited
    
    def _get_resource_file_type(self, graph, resource):
        """Get the file type of a resource"""
        import json
        try:
            node_data = graph.g.nodes.get(resource, {})
            extra_str = node_data.get('extra', '{}')
            extra_data = json.loads(extra_str) if extra_str else {}
            return extra_data.get('file_type', 'UNKNOWN')
        except:
            return 'UNKNOWN'
    
    def _is_resource_required_by_constraints(self, resource, constraints):
        """Check if any constraint requires access to this specific resource"""
        for constraint in constraints:
            if constraint.constraint_type == "requires_resource_access":
                if constraint.resource_info == resource:
                    return True
            elif constraint.constraint_type == "requires_resource_exists":
                if constraint.resource_info == resource:
                    return True
        return False
    
    def _pd_has_access_to_resource(self, graph, pd, resource):
        """Check if a PD has direct access to a resource"""
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd and to_node == resource and edge_data.get('type') == 'HOLD':
                return True
        return False
    
    def _find_unused_pds(self, graph):
        """Find PDs that have no outgoing edges (likely created for mediation but not connected yet)"""
        unused_pds = []
        pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']
        
        for pd in pds:
            outgoing_edges = 0
            for from_node, to_node, edge_data in graph.g.edges(data=True):
                if from_node == pd:
                    outgoing_edges += 1
            
            if outgoing_edges == 0:
                unused_pds.append(pd)
        
        return unused_pds
    
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
    "remove_resource_space": Transition(
        name="remove_resource_space",
        description="Remove resource space",
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
    "add_subset_edge": Transition(
        name="add_subset_edge",
        description="Create Resource → ResourceSpace relationship",
        transition_type="primitive"
    ),
    "remove_subset_edge": Transition(
        name="remove_subset_edge",
        description="Remove Resource → ResourceSpace relationship",
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
            Primitive("add_file_resource", file_space="$resource_space", file_type="$file_type", file_path="$path1", file_size="$size"),
            Primitive("add_file_resource", file_space="$resource_space", file_type="$file_type", file_path="$path2", file_size="$size"),
            Primitive("add_subset_edge", resource="$new_resource1", resource_space="$resource_space"),
            Primitive("add_subset_edge", resource="$new_resource2", resource_space="$resource_space"),
            Primitive("add_hold_edge", pd="$pd1", resource="$new_resource1"),
            Primitive("add_hold_edge", pd="$pd2", resource="$new_resource2"),
            Primitive("remove_hold_edge", from_node="$pd1", to_node="$resource"),
            Primitive("remove_hold_edge", from_node="$pd2", to_node="$resource"),
            Primitive("remove_file_resource", resource="$resource")
        ],
        parameters=["pd1", "pd2", "resource", "resource_space", "file_type", "path1", "path2", "size", "new_resource1", "new_resource2"]
    ),
    
    "add_mediator": Transition(
        name="add_mediator", 
        description="Insert mediator PD between sharers",
        transition_type="multistep",
        primitives=[
            Primitive("add_pd", pd_type="mediator"),
            Primitive("remove_hold_edge", from_node="$pd1", to_node="$resource"),
            Primitive("remove_hold_edge", from_node="$pd2", to_node="$resource"),
            Primitive("add_hold_edge", pd="$mediator_pd", resource="$resource"),
            Primitive("add_request_edge", from_pd="$pd1", to_pd="$mediator_pd"),
            Primitive("add_request_edge", from_pd="$pd2", to_pd="$mediator_pd")
        ],
        parameters=["pd1", "pd2", "resource", "mediator_pd"]
    )
}

# Graph builder functions for different scenarios

def build_basic_shared_resource_graph():
    """Build a basic graph with 2 PDs each having 1 private FILE resource + 1 shared FILE resource"""
    graph = ModelGraph()
    
    # Add two protection domains
    pd1 = NodeTransformations.add_pd_node(graph, "user_process")
    pd2 = NodeTransformations.add_pd_node(graph, "database_server")
    
    # Add a FILE space
    file_space = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    
    # Create 1 private resource for PD1
    pd1_config = NodeTransformations.add_file_resource(graph, file_space, FileType.CONFIG, "/etc/user.conf", 4096)
    
    # Create 1 private resource for PD2  
    pd2_db = NodeTransformations.add_file_resource(graph, file_space, FileType.DATABASE, "/var/db/main.db", 8192)
    
    # Create 1 shared resource that both PDs access
    shared_buffer = NodeTransformations.add_file_resource(graph, file_space, FileType.TEMP, "/tmp/shared_buffer.tmp", 2048)
    
    # PD1 holds its 1 private resource
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd1, ResourceType.FILE, file_space, pd1_config)
    
    # PD2 holds its 1 private resource
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




def build_reduce_isolation_graph():
    """Build a graph with mediated access: PD1 -> PD3 -> R0, PD2 -> PD4 -> R0"""
    graph = ModelGraph()
    
    # Add four protection domains
    pd1 = NodeTransformations.add_pd_node(graph, "client_1")
    pd2 = NodeTransformations.add_pd_node(graph, "client_2") 
    pd3 = NodeTransformations.add_pd_node(graph, "mediator_1")
    pd4 = NodeTransformations.add_pd_node(graph, "mediator_2")
    
    # Add a FILE space
    file_space = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    
    # Create the shared resource R0
    r0 = NodeTransformations.add_file_resource(graph, file_space, FileType.CONFIG, "/shared/config.dat", 4096)
    
    # Mediators hold the resource
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd3, ResourceType.FILE, file_space, r0)
    EdgeTransformations.add_hold_edge(graph, Permission.R, pd4, ResourceType.FILE, file_space, r0)
    
    # Clients request from mediators for the FILE resource space
    EdgeTransformations.add_request_edge(graph, pd1, pd3, ResourceType.FILE, file_space)
    EdgeTransformations.add_request_edge(graph, pd2, pd4, ResourceType.FILE, file_space)
    
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
# All atomic graph operations (node and edge operations)
PRIMITIVES = [
    # Node operations
    "add_pd", "remove_pd", 
    "add_file_resource", "remove_file_resource", 
    "add_resource_space", "remove_resource_space",
    # Edge operations  
    "add_hold_edge", "remove_hold_edge",
    "add_request_edge", "remove_request_edge",
    "add_subset_edge", "remove_subset_edge"
]

# Multi-step transitions composed of primitives
MULTISTEP = ["privatize_resource", "add_mediator"]


# Scenario definitions

SCENARIOS = {
    "basic_sharing": Scenario(
        name="Basic Resource Sharing",
        description="2 PDs each with 1 private FILE resource + 1 shared FILE resource",
        goals=[
            Goal("RSI", 0.3, "minimize", "PD_1,PD_2"),  # Target specific PD pair
            Goal("TCB", 0, "minimize", "PD_1"),         # Target specific PD
            Goal("ASR", 1.0, "minimize")                # System-wide goal
        ],
        constraints=[
            # Specific FILE access requirements
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "CONFIG", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "DATABASE", "min_size_kb": 1}),
        ],
        allowed_primitives=[],  # No primitives allowed
        allowed_multistep=["privatize_resource", "add_mediator"],  # Only multi-step transformations
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "basic_sharing_primitive": Scenario(
        name="Basic Resource Sharing (True Primitives Only)",
        description="Same simplified scenario as basic_sharing (1 private file + 1 shared file per PD) but using only true graph primitives",
        goals=[
            Goal("RSI", 0.3, "minimize", "PD_1,PD_2"),  # Target specific PD pair
            Goal("TCB", 0, "minimize", "PD_1"),         # Target specific PD
            Goal("ASR", 1.0, "minimize")                # System-wide goal
        ],
        constraints=[
            # Specific FILE access requirements (same as basic_sharing)
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "CONFIG", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "DATABASE", "min_size_kb": 1}),
            # Both PDs need access to TEMP files
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "TEMP", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "TEMP", "min_size_kb": 1}),
        ],
        allowed_primitives=PRIMITIVES,  # All atomic graph operations
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
        allowed_primitives=PRIMITIVES,  # All atomic graph operations
        allowed_multistep=[],  # No multi-step allowed
        graph_builder=build_high_sharing_graph
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
    
    "mediator_test_primitive": Scenario(
        name="Mediator Test Primitive",
        description="Test if primitives can achieve mediation pattern",
        goals=[
            Goal("RSI", 0.8, "minimize", "PD_1,PD_2")   # Same goal as mediator_test
        ],
        constraints=[
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
        ],
        allowed_primitives=PRIMITIVES,  # All primitives allowed
        allowed_multistep=[],  # No multi-step transitions
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "mediator_test_constrained": Scenario(
        name="Mediator Test Constrained",
        description="Test if no-direct-hold constraint leads to mediation discovery",
        goals=[
            Goal("RSI", 0.8, "minimize", "PD_1,PD_2")   # Same goal as mediator_test
        ],
        constraints=[
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            # New constraint: PD_1 and PD_2 should NOT directly hold FILE_1_3
            Constraint("prohibit_direct_hold", 1, "FILE_1_3", properties={"constraint_type": "negative"}),
            Constraint("prohibit_direct_hold", 2, "FILE_1_3", properties={"constraint_type": "negative"}),
        ],
        allowed_primitives=PRIMITIVES,  # All primitives allowed
        allowed_multistep=[],  # No multi-step transitions
        graph_builder=build_basic_shared_resource_graph
    ),
    
    "mediator_test_indirect": Scenario(
        name="Mediator Test Indirect Access",
        description="Test if requiring indirect access forces mediation discovery",
        goals=[
            Goal("RSI", 0.8, "minimize", "PD_1,PD_2")   # Same goal as mediator_test
        ],
        constraints=[
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            # Prohibit direct access to the shared resource
            Constraint("prohibit_direct_hold", 1, "FILE_1_3", properties={"constraint_type": "negative"}),
            Constraint("prohibit_direct_hold", 2, "FILE_1_3", properties={"constraint_type": "negative"}),
            # New constraint: Both PDs must have access to FILE_1_3 (direct or indirect)
            Constraint("requires_resource_access", 1, "FILE_1_3", properties={"access_type": "direct_or_indirect"}),
            Constraint("requires_resource_access", 2, "FILE_1_3", properties={"access_type": "direct_or_indirect"}),
            # Critical constraint: FILE_1_3 must exist in the graph (prevents removal)
            Constraint("requires_resource_exists", None, "FILE_1_3", properties={"mandatory": True}),
        ],
        allowed_primitives=PRIMITIVES,  # All primitives allowed
        allowed_multistep=[],  # No multi-step transitions
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
    ),
    
    "attack_surface_reduction_enhanced": Scenario(
        name="Attack Surface Reduction Enhanced",
        description="Same high attack surface system as attack_surface_reduction but with all primitives enabled for pattern-aware optimization",
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
        allowed_primitives=PRIMITIVES,  # All atomic graph operations enabled
        allowed_multistep=[],  # No multi-step allowed
        graph_builder=build_high_attack_surface_graph
    ),
    
    "reduce_isolation": Scenario(
        name="Reduce Isolation",
        description="Transform mediated access (PD1->PD3->R0, PD2->PD4->R0) to direct access (PD1->R0, PD2->R0) by maximizing RSI",
        goals=[
            Goal("RSI", 0.8, "maximize", "PD_1,PD_2")   # Maximize sharing to encourage direct access
        ],
        constraints=[
            # Both PDs require access to the shared resource R0 (FILE_1_1)
            Constraint("requires_resource_access", 1, "FILE_1_1", properties={"access_type": "direct_or_indirect"}),
            Constraint("requires_resource_access", 2, "FILE_1_1", properties={"access_type": "direct_or_indirect"}),
            # Resource must exist
            Constraint("requires_resource_exists", None, "FILE_1_1", properties={"mandatory": True}),
            # Basic file access requirements
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
        ],
        allowed_primitives=PRIMITIVES,  # All primitives allowed for flexible transformation
        allowed_multistep=[],  # No multi-step transitions
        graph_builder=build_reduce_isolation_graph
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
    supported_constraint_types = {"requires_file_access", "requires_communication", "prohibit_direct_hold", "requires_indirect_access", "requires_resource_access", "requires_resource_exists"}
    
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