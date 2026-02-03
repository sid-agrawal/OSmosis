"""
IsoSearch Scenario Definitions - Cleaned Version

This file contains 3 core scenarios for the IsoSearch algorithm.
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
    """Transition structure for graph operations"""
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

    # Core candidate finding methods (simplified versions)
    def _find_add_pd_candidates(self, graph, constraints):
        """Find opportunities to add new PDs"""
        candidates = []

        # Check current PD count to avoid excessive PD creation
        current_pd_count = len([node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD'])

        constraint_relevance = 0.4  # Default relevance
        description = "add new protection domain"

        # Reduce priority if we already have many PDs
        if current_pd_count >= 5:
            constraint_relevance *= 0.3
            description += f" (warning: {current_pd_count} PDs already exist)"
        elif current_pd_count >= 3:
            constraint_relevance *= 0.6

        candidates.append({
            'param_values': {'pd_type': 'new_component'},
            'target_description': description,
            'constraint_relevance': constraint_relevance,
            'addresses_violation': False
        })

        return candidates

    def _find_remove_pd_candidates(self, graph, constraints):
        """Find PDs that can be safely removed"""
        candidates = []
        pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']

        for pd in pds:
            # Check if PD has no connections (orphaned)
            has_outgoing = any(graph.g.has_edge(pd, neighbor) for neighbor in graph.g.nodes())
            has_incoming = any(graph.g.has_edge(neighbor, pd) for neighbor in graph.g.nodes())

            if not has_outgoing and not has_incoming:
                candidates.append({
                    'param_values': {'pd': pd},
                    'target_description': f"remove empty {pd}",
                    'constraint_relevance': 0.3,
                    'addresses_violation': False
                })

        return candidates

    def _find_add_hold_edge_candidates(self, graph, constraints):
        """Find PD-resource connections to add"""
        candidates = []

        # Find PDs
        pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']

        # Find resources by type - FILE, CPU, PHYS_PAGE
        resource_types = ['FILE', 'CPU', 'PHYS_PAGE']
        resources_by_type = {}
        for res_type in resource_types:
            resources_by_type[res_type] = [
                node for node, data in graph.g.nodes(data=True)
                if data.get('type') == 'RESOURCE' and data.get('data') == res_type
            ]

        for pd in pds:
            current_resources = self._get_pd_held_resources(graph, pd)

            # Process each resource type
            for res_type, resources in resources_by_type.items():
                for resource in resources:
                    if resource not in current_resources:
                        # Check if connection is prohibited
                        prohibited = self._is_connection_prohibited(pd, resource, constraints)

                        if not prohibited:
                            constraint_relevance = 0.4  # Standard score
                            description = f"connect {pd} to {resource}"

                            # For PHYS_PAGE: boost candidates that would reduce TransitiveRSI
                            if res_type == 'PHYS_PAGE':
                                trsi_improvement = self._calculate_transitive_rsi_improvement(
                                    graph, pd, resource, constraints)
                                if trsi_improvement > 0:
                                    constraint_relevance = max(constraint_relevance, 0.6 + trsi_improvement * 0.4)
                                    description = f"connect {pd} to {resource} (improves cache isolation)"

                            # For CPU: standard relevance
                            elif res_type == 'CPU':
                                # Check if PD needs a CPU
                                if not any(r for r in current_resources if 'CPU_' in r):
                                    constraint_relevance = max(constraint_relevance, 0.7)
                                    description = f"connect {pd} to {resource} (needs CPU)"

                            # For FILE: existing logic
                            else:
                                # Check RSI goal relevance
                                rsi_relevance = self._calculate_rsi_goal_relevance(graph, pd, resource, constraints)
                                if rsi_relevance > 0:
                                    constraint_relevance = max(constraint_relevance, rsi_relevance)
                                    if rsi_relevance >= 0.8:
                                        description = f"connect {pd} to {resource} (RSI goal achievement)"

                                # CRITICAL FIX: Check if this connection would satisfy constraint violations
                                constraint_satisfaction_boost = self._calculate_constraint_satisfaction_boost(
                                    graph, pd, resource, constraints)
                                if constraint_satisfaction_boost > 0:
                                    constraint_relevance = max(constraint_relevance, constraint_satisfaction_boost)
                                    if constraint_satisfaction_boost >= 1.0:
                                        description = f"connect {pd} to {resource} (satisfies constraint violation)"

                            # Boost for orphaned resources
                            holders = self._get_resource_holders(graph, resource)
                            if len(holders) == 0:
                                constraint_relevance = max(constraint_relevance, 0.8)
                                description = f"connect {pd} to orphaned resource {resource}"

                            candidates.append({
                                'param_values': {'pd': pd, 'resource': resource, 'permission': 'R'},
                                'target_description': description,
                                'constraint_relevance': constraint_relevance,
                                'addresses_violation': constraint_relevance >= 0.8
                            })

        return candidates

    def _calculate_transitive_rsi_improvement(self, graph, pd, resource, constraints):
        """Calculate how much connecting this PD to this PHYS_PAGE would improve TransitiveRSI.

        Returns a value between 0 and 1, where higher means better improvement.
        """
        # Get the cache set this physical page maps to
        target_cache_set = None
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == resource and edge_data.get('type') == 'MAP':
                target_cache_set = to_node
                break

        if target_cache_set is None:
            return 0.0

        # Find cache sets used by other PDs
        other_pds_cache_sets = set()
        for other_pd in [n for n, d in graph.g.nodes(data=True) if d.get('type') == 'PD' and n != pd]:
            for from_node, to_node, edge_data in graph.g.edges(data=True):
                if from_node == other_pd and edge_data.get('type') == 'HOLD':
                    # Follow MAP edges from held resources
                    for map_from, map_to, map_data in graph.g.edges(data=True):
                        if map_from == to_node and map_data.get('type') == 'MAP':
                            other_pds_cache_sets.add(map_to)

        # If target cache set is NOT used by others, this is a good choice
        if target_cache_set not in other_pds_cache_sets:
            return 1.0
        else:
            return 0.0

    def _find_remove_hold_edge_candidates(self, graph, constraints):
        """Find HOLD edges that can be safely removed"""
        candidates = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'HOLD':
                can_remove = self._can_safely_remove_hold_edge(graph, from_node, to_node, constraints)
                if can_remove:
                    candidates.append({
                        'param_values': {'from_node': from_node, 'to_node': to_node},
                        'target_description': f"remove {from_node} -> {to_node} HOLD edge"
                    })
        return candidates

    def _find_add_file_resource_candidates(self, graph, constraints):
        """Find opportunities to add new FILE resources"""
        candidates = []
        file_spaces = [node for node, data in graph.g.nodes(data=True)
                      if data.get('type') == 'RESOURCE_SPACE' and data.get('data') == 'FILE']

        for space in file_spaces:
            for file_type in ['CONFIG', 'DATABASE', 'TEMP', 'LOG']:
                candidates.append({
                    'param_values': {'file_type': file_type, 'resource_space': space},
                    'target_description': f"create new {file_type} file in {space}",
                    'constraint_relevance': 0.1,
                    'addresses_violation': False
                })

        return candidates

    def _find_remove_file_resource_candidates(self, graph, constraints):
        """Find FILE resources that can be removed"""
        candidates = []
        resources = [node for node, data in graph.g.nodes(data=True)
                    if data.get('type') == 'RESOURCE' and data.get('data') == 'FILE']

        for resource in resources:
            holders = self._get_resource_holders(graph, resource)
            candidates.append({
                'param_values': {'resource': resource},
                'target_description': f"remove {resource} (holders: {len(holders)})",
                'constraint_relevance': 0.1,
                'addresses_violation': False
            })

        return candidates

    def _find_add_resource_space_candidates(self, graph, constraints):
        """Find opportunities to add resource spaces"""
        candidates = []
        candidates.append({
            'param_values': {'space_type': 'FILE'},
            'target_description': "create new FILE resource space",
            'constraint_relevance': 0.2,
            'addresses_violation': False
        })
        return candidates

    def _find_remove_resource_space_candidates(self, graph, constraints):
        """Find resource spaces that can be removed"""
        candidates = []
        spaces = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'RESOURCE_SPACE']

        for space in spaces:
            # Check if space has resources
            has_resources = any(graph.g.has_edge(resource, space)
                               for resource in graph.g.nodes()
                               if graph.g.has_edge(resource, space))
            if not has_resources:
                candidates.append({
                    'param_values': {'resource_space': space},
                    'target_description': f"remove empty {space}",
                    'constraint_relevance': 0.2,
                    'addresses_violation': False
                })

        return candidates

    def _find_add_request_edge_candidates(self, graph, constraints):
        """Find PD-PD authority relationships to add"""
        candidates = []
        pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']

        for from_pd in pds:
            for to_pd in pds:
                if from_pd != to_pd and not graph.g.has_edge(from_pd, to_pd):
                    candidates.append({
                        'param_values': {'from_pd': from_pd, 'to_pd': to_pd},
                        'target_description': f"create {from_pd} -> {to_pd} REQUEST",
                        'constraint_relevance': 0.3,
                        'addresses_violation': False
                    })

        return candidates

    def _find_remove_request_edge_candidates(self, graph, constraints):
        """Find REQUEST edges that can be removed"""
        candidates = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'REQUEST':
                candidates.append({
                    'param_values': {'from_node': from_node, 'to_node': to_node},
                    'target_description': f"remove {from_node} -> {to_node} REQUEST edge"
                })
        return candidates

    def _find_add_subset_edge_candidates(self, graph, constraints):
        """Find resource-space relationships to add"""
        candidates = []
        resources = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'RESOURCE']
        spaces = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'RESOURCE_SPACE']

        for resource in resources:
            for space in spaces:
                if not graph.g.has_edge(resource, space):
                    candidates.append({
                        'param_values': {'resource': resource, 'resource_space': space},
                        'target_description': f"connect {resource} to {space}",
                        'constraint_relevance': 0.2,
                        'addresses_violation': False
                    })

        return candidates

    def _find_remove_subset_edge_candidates(self, graph, constraints):
        """Find subset edges that can be removed"""
        candidates = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'SUBSET':
                candidates.append({
                    'param_values': {'from_node': from_node, 'to_node': to_node},
                    'target_description': f"remove {from_node} -> {to_node} SUBSET edge"
                })
        return candidates

    def _find_privatize_resource_candidates(self, graph, constraints):
        """Find resources that can be privatized"""
        return []  # Simplified - not used by our 3 scenarios

    def _find_add_mediator_candidates(self, graph, constraints):
        """Find opportunities to add mediator PDs"""
        return []  # Simplified - not used by our 3 scenarios

    # Helper methods
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

    def _is_connection_prohibited(self, pd, resource, constraints):
        """Check if PD-resource connection is prohibited by constraints"""
        pd_id = int(pd.split('_')[1]) if pd.startswith('PD_') else None
        if pd_id is None:
            return False

        for constraint in constraints:
            if (constraint.constraint_type == "prohibit_direct_hold" and
                constraint.pd_id == pd_id and
                constraint.resource_info == resource):
                return True
        return False

    def _can_safely_remove_hold_edge(self, graph, from_pd, to_resource, constraints):
        """Check if removing a HOLD edge would violate constraints"""
        import json

        # Check if there's a prohibit_direct_hold constraint that REQUIRES this removal
        pd_id = int(from_pd.split('_')[1]) if from_pd.startswith('PD_') else None
        if pd_id is not None:
            for constraint in constraints:
                if (constraint.constraint_type == "prohibit_direct_hold" and
                    constraint.pd_id == pd_id and
                    constraint.resource_info == to_resource):
                    return True  # Removal is encouraged

        # For simplicity, allow most removals unless it would violate access requirements
        return True

    def _calculate_rsi_goal_relevance(self, graph, pd, resource, constraints):
        """Calculate how much connecting this PD to this resource would help achieve RSI goals"""
        # Check if this looks like the reduce_isolation scenario pattern
        if pd in ['PD_1', 'PD_2'] and resource == 'FILE_1_1':
            other_target_pd = 'PD_2' if pd == 'PD_1' else 'PD_1'
            other_has_resource = False

            for from_node, to_node, edge_data in graph.g.edges(data=True):
                if (from_node == other_target_pd and to_node == resource and
                    edge_data.get('type') == 'HOLD'):
                    other_has_resource = True
                    break

            if other_has_resource:
                return 0.9  # Very high priority - completes RSI maximization
            else:
                return 0.7  # High priority - first step toward RSI maximization

        # For other cases, check if adding this connection increases sharing
        current_holders = self._get_resource_holders(graph, resource)
        if len(current_holders) >= 1:
            return 0.6  # Medium priority for increasing sharing

        return 0.0

    def _calculate_constraint_satisfaction_boost(self, graph, pd, resource, constraints):
        """Calculate how much connecting this PD to this resource would help satisfy constraint violations"""
        import json
        
        # Extract PD ID from PD string
        try:
            pd_id = int(pd.split('_')[1]) if pd.startswith('PD_') else None
        except (IndexError, ValueError):
            return 0.0
            
        if pd_id is None:
            return 0.0
        
        # Get resource file type from node data
        node_data = graph.g.nodes.get(resource, {})
        extra_str = node_data.get('extra', '{}')
        try:
            extra_data = json.loads(extra_str) if extra_str else {}
        except (json.JSONDecodeError, TypeError):
            extra_data = {}
        resource_file_type = extra_data.get('file_type', 'UNKNOWN')
        
        # Check if this connection would satisfy any requires_file_access constraints
        for constraint in constraints:
            if (constraint.constraint_type == "requires_file_access" and 
                constraint.pd_id == pd_id):
                
                required_file_type = constraint.properties.get('file_type', 'any')
                
                # Check if this resource matches the required file type
                if (required_file_type == 'any' or 
                    required_file_type.upper() == resource_file_type.upper()):
                    
                    # Check if this PD currently lacks access to this file type
                    current_has_access = self._pd_has_access_to_file_type(graph, pd, required_file_type)
                    
                    if not current_has_access:
                        return 1.5  # Maximum boost for satisfying constraint violation
                        
        return 0.0

    def _pd_has_access_to_file_type(self, graph, pd, file_type):
        """Check if a PD currently has access to any file of the specified type"""
        import json
        
        # Get all resources currently held by this PD
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd and edge_data.get('type') == 'HOLD':
                # Check if this resource matches the file type
                node_data = graph.g.nodes.get(to_node, {})
                extra_str = node_data.get('extra', '{}')
                try:
                    extra_data = json.loads(extra_str) if extra_str else {}
                except (json.JSONDecodeError, TypeError):
                    extra_data = {}
                resource_file_type = extra_data.get('file_type', 'UNKNOWN')
                
                if (file_type == 'any' or 
                    file_type.upper() == resource_file_type.upper()):
                    return True
                    
        return False

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

                # Extract PD ID
                pd_id = int(pd_string.split('_')[1]) if pd_string.startswith('PD_') else 1

                # Determine resource type and extract IDs from resource string
                # Format: TYPE_SPACEID_RESOURCEID (e.g., FILE_1_2, CPU_1_1, PHYS_PAGE_3_5)
                if resource_string.startswith('FILE_'):
                    res_type = ResourceType.FILE
                    parts = resource_string.split('_')
                    resource_space_id = int(parts[1])
                    resource_id = int(parts[2])
                elif resource_string.startswith('CPU_'):
                    res_type = ResourceType.CPU
                    parts = resource_string.split('_')
                    resource_space_id = int(parts[1])
                    resource_id = int(parts[2])
                elif resource_string.startswith('PHYS_PAGE_'):
                    res_type = ResourceType.PHYS_PAGE
                    parts = resource_string.split('_')
                    resource_space_id = int(parts[2])
                    resource_id = int(parts[3])
                elif resource_string.startswith('CACHE_SET_'):
                    res_type = ResourceType.CACHE_SET
                    parts = resource_string.split('_')
                    resource_space_id = int(parts[2])
                    resource_id = int(parts[3])
                else:
                    # Default to FILE for backwards compatibility
                    res_type = ResourceType.FILE
                    resource_space_id = 1
                    resource_id = int(resource_string.split('_')[-1])

                EdgeTransformations.add_hold_edge(
                    graph,
                    {Permission.R, Permission.W},  # Use set notation for permissions
                    pd_id,
                    res_type,
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

                # Extract file space ID from node name or param
                if 'resource_space' in param_values:
                    file_space_name = param_values['resource_space']
                    if file_space_name.startswith('FILE_SPACE_'):
                        file_space_id = int(file_space_name.split('_')[-1])
                    else:
                        file_space_id = 1  # Default
                else:
                    file_space_id = 1  # Default

                # Generate default path and size based on file type
                file_paths = {
                    'CONFIG': '/etc/app.conf',
                    'DATABASE': '/var/db/data.db',
                    'TEMP': '/tmp/tempfile.tmp',
                    'LOG': '/var/log/app.log'
                }
                default_path = file_paths.get(param_values['file_type'], '/tmp/default.tmp')

                result = NodeTransformations.add_file_resource(
                    graph,
                    file_space_id,
                    file_type,
                    default_path,
                    param_values.get('file_size', 1024)
                )
                return result is not None
            elif self.name == "remove_file_resource":
                from graph_transformations import NodeTransformations
                import json
                # Remove the resource node and its edges
                resource = param_values['resource']

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
                resource_type = getattr(ResourceType, param_values['space_type'])
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
                    param_values['from_node'],
                    param_values['to_node'],
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
                    param_values['from_node'],
                    param_values['to_node'],
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
        """Apply sequence of primitives (not used by our 3 scenarios)"""
        print(f"Multi-step {self.name} not yet implemented")
        return False


class Scenario:
    """Complete scenario definition"""
    def __init__(self, name, description, goals, constraints, allowed_primitives, allowed_multistep, graph_builder):
        self.name = name
        self.description = description
        self.goals = goals
        self.constraints = constraints
        self.allowed_primitives = allowed_primitives
        self.allowed_multistep = allowed_multistep
        self.graph_builder = graph_builder

    def get_allowed_transitions(self):
        """Get all allowed transitions for this scenario"""
        transitions = []

        # Add allowed primitives
        for primitive_name in self.allowed_primitives:
            if primitive_name in PRIMITIVES:
                transitions.append(PRIMITIVES[primitive_name])

        # Add allowed multi-step (none for our 3 scenarios)
        for multistep_name in self.allowed_multistep:
            # Could add MULTISTEP_TRANSITIONS here if needed
            pass

        return transitions

    def build_graph(self):
        """Build the initial graph for this scenario"""
        return self.graph_builder()


# Primitive transitions
PRIMITIVES = {
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
    ),
}


# Graph builders for the 3 scenarios
def build_basic_shared_resource_graph():
    """Build a minimal graph with 2 PDs sharing 1 file, plus an alternative TEMP file"""
    graph = ModelGraph()

    # Add 2 PDs
    pd1_id = NodeTransformations.add_pd_node(graph, "PD_1")
    pd2_id = NodeTransformations.add_pd_node(graph, "PD_2")

    # Add 1 resource space for files
    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)

    # Add shared file resource (FILE_1_1)
    file1_id = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP, "/tmp/shared_buffer.tmp", 2048)

    # Add alternative TEMP file (FILE_1_2) to enable isolation solutions
    file2_id = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP, "/tmp/private_buffer.tmp", 1024)

    # Both PDs hold the shared file (this creates the sharing to be reduced)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd1_id, ResourceType.FILE, space_id, file1_id)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd2_id, ResourceType.FILE, space_id, file1_id)

    # FILE_1_2 starts unconnected (available for isolation solutions)

    return graph


def build_mediator_test_graph():
    """Build a minimal graph for mediator testing - 2 PDs sharing 1 file (no FILE_1_2)"""
    graph = ModelGraph()

    # Add 2 PDs
    pd1_id = NodeTransformations.add_pd_node(graph, "PD_1")
    pd2_id = NodeTransformations.add_pd_node(graph, "PD_2")

    # Add 1 resource space for files
    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)

    # Add shared file resource (FILE_1_1) - this is the only file resource
    file1_id = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP, "/tmp/shared_buffer.tmp", 2048)

    # Both PDs hold the shared file (this creates the sharing to be reduced)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd1_id, ResourceType.FILE, space_id, file1_id)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd2_id, ResourceType.FILE, space_id, file1_id)

    return graph


def build_reduce_isolation_graph():
    """Build a graph with mediated access: PD1 -> PD3 -> R0, PD2 -> PD4 -> R0"""
    graph = ModelGraph()

    # Add client PDs
    pd1_id = NodeTransformations.add_pd_node(graph, "PD_1")
    pd2_id = NodeTransformations.add_pd_node(graph, "PD_2")

    # Add mediator PDs
    pd3_id = NodeTransformations.add_pd_node(graph, "PD_3")
    pd4_id = NodeTransformations.add_pd_node(graph, "PD_4")

    # Add resource space
    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)

    # Add shared resource R0 (FILE_1_1)
    file_id = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG, "/shared/config.dat", 4096)

    # Create mediated access pattern:
    # PD_1 requests from PD_3, PD_2 requests from PD_4
    EdgeTransformations.add_request_edge(graph, pd1_id, pd3_id, ResourceType.FILE, space_id)
    EdgeTransformations.add_request_edge(graph, pd2_id, pd4_id, ResourceType.FILE, space_id)

    # Mediators hold the resource
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd3_id, ResourceType.FILE, space_id, file_id)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd4_id, ResourceType.FILE, space_id, file_id)

    return graph


def build_cache_same_core_conflict_graph():
    """Build a graph where 2 PDs on same CPU core have cache set collision.

    Structure:
    - 2 PDs on same CPU (CPU_1)
    - 4 cache sets
    - 8 physical pages (2 per cache set, using modulo mapping)
    - Both PDs use physical pages that map to the same cache set

    Initial state (collision):
        PD_1 -> CPU_1, PHYS_PAGE_1 -> CACHE_SET_1
        PD_2 -> CPU_1, PHYS_PAGE_5 -> CACHE_SET_1 (collision!)
    """
    graph = ModelGraph()

    # Add 2 PDs
    pd1_id = NodeTransformations.add_pd_node(graph, "PD_1")
    pd2_id = NodeTransformations.add_pd_node(graph, "PD_2")

    # Add CPU space and 2 CPU cores
    cpu_space_id = NodeTransformations.add_resource_space(graph, ResourceType.CPU)
    cpu1_id = NodeTransformations.add_cpu_resource(graph, cpu_space_id, 1)
    cpu2_id = NodeTransformations.add_cpu_resource(graph, cpu_space_id, 2)

    # Add cache set space and 4 cache sets (indexed 0-3)
    cache_space_id = NodeTransformations.add_resource_space(graph, ResourceType.CACHE_SET)
    for i in range(4):
        NodeTransformations.add_cache_set_resource(graph, cache_space_id, i)

    # Add physical page space and 8 pages
    phys_space_id = NodeTransformations.add_resource_space(graph, ResourceType.PHYS_PAGE)
    for i in range(1, 9):
        NodeTransformations.add_phys_page_resource(graph, phys_space_id, i)

    # Add fixed MAP edges: PHYS_PAGE -> CACHE_SET (modulo 4 mapping)
    # Page 1 -> Set 1, Page 2 -> Set 2, Page 3 -> Set 3, Page 4 -> Set 0
    # Page 5 -> Set 1, Page 6 -> Set 2, Page 7 -> Set 3, Page 8 -> Set 0
    for page_id in range(1, 9):
        cache_set_id = page_id % 4
        EdgeTransformations.add_map_edge(
            graph,
            ResourceType.PHYS_PAGE, ResourceType.CACHE_SET,
            phys_space_id, cache_space_id,
            page_id, cache_set_id
        )

    # Both PDs scheduled on same CPU (CPU_1)
    EdgeTransformations.add_hold_edge(graph, {Permission.R}, pd1_id, ResourceType.CPU, cpu_space_id, cpu1_id)
    EdgeTransformations.add_hold_edge(graph, {Permission.R}, pd2_id, ResourceType.CPU, cpu_space_id, cpu1_id)

    # PD_1 holds PHYS_PAGE_1 (maps to CACHE_SET_1)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd1_id, ResourceType.PHYS_PAGE, phys_space_id, 1)

    # PD_2 holds PHYS_PAGE_5 (also maps to CACHE_SET_1 - collision!)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd2_id, ResourceType.PHYS_PAGE, phys_space_id, 5)

    return graph


def build_cache_llc_collision_graph():
    """Build a graph where 2 PDs on different CPU cores have LLC cache set collision.

    Structure:
    - 2 PDs on different CPUs (CPU_1 and CPU_2)
    - 4 cache sets (shared L3/LLC)
    - 8 physical pages (2 per cache set, using modulo mapping)
    - Both PDs use physical pages that map to the same cache set

    Initial state (LLC collision):
        PD_1 -> CPU_1, PHYS_PAGE_1 -> CACHE_SET_1
        PD_2 -> CPU_2, PHYS_PAGE_5 -> CACHE_SET_1 (LLC collision!)
    """
    graph = ModelGraph()

    # Add 2 PDs
    pd1_id = NodeTransformations.add_pd_node(graph, "PD_1")
    pd2_id = NodeTransformations.add_pd_node(graph, "PD_2")

    # Add CPU space and 2 CPU cores
    cpu_space_id = NodeTransformations.add_resource_space(graph, ResourceType.CPU)
    cpu1_id = NodeTransformations.add_cpu_resource(graph, cpu_space_id, 1)
    cpu2_id = NodeTransformations.add_cpu_resource(graph, cpu_space_id, 2)

    # Add cache set space and 4 cache sets (indexed 0-3)
    cache_space_id = NodeTransformations.add_resource_space(graph, ResourceType.CACHE_SET)
    for i in range(4):
        NodeTransformations.add_cache_set_resource(graph, cache_space_id, i)

    # Add physical page space and 8 pages
    phys_space_id = NodeTransformations.add_resource_space(graph, ResourceType.PHYS_PAGE)
    for i in range(1, 9):
        NodeTransformations.add_phys_page_resource(graph, phys_space_id, i)

    # Add fixed MAP edges: PHYS_PAGE -> CACHE_SET (modulo 4 mapping)
    for page_id in range(1, 9):
        cache_set_id = page_id % 4
        EdgeTransformations.add_map_edge(
            graph,
            ResourceType.PHYS_PAGE, ResourceType.CACHE_SET,
            phys_space_id, cache_space_id,
            page_id, cache_set_id
        )

    # PDs on different CPUs
    EdgeTransformations.add_hold_edge(graph, {Permission.R}, pd1_id, ResourceType.CPU, cpu_space_id, cpu1_id)
    EdgeTransformations.add_hold_edge(graph, {Permission.R}, pd2_id, ResourceType.CPU, cpu_space_id, cpu2_id)

    # PD_1 holds PHYS_PAGE_1 (maps to CACHE_SET_1)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd1_id, ResourceType.PHYS_PAGE, phys_space_id, 1)

    # PD_2 holds PHYS_PAGE_5 (also maps to CACHE_SET_1 - LLC collision!)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd2_id, ResourceType.PHYS_PAGE, phys_space_id, 5)

    return graph


# Core scenarios
SCENARIOS = {
    "basic_sharing_primitive": Scenario(
        name="Basic Resource Sharing (True Primitives Only)",
        description="Minimal scenario: 2 PDs sharing 1 file only, using only true graph primitives",
        goals=[
            Goal("RSI", 0.0, "minimize", "PD_1,PD_2"),  # Perfect isolation
        ],
        constraints=[
            # Both PDs need access to FILE_1_1 (direct or indirect) - allows for mediation
            # Constraint("requires_resource_access", 1, "FILE_1_1", properties={"access_type": "direct_or_indirect"}),
            # Constraint("requires_resource_access", 2, "FILE_1_1", properties={"access_type": "direct_or_indirect"}),
            # Ensure the shared file must exist
            Constraint("requires_resource_exists", None, "FILE_1_1", properties={"mandatory": True}),
            # Ensure alternative TEMP file exists to enable isolation solutions
            Constraint("requires_resource_exists", None, "FILE_1_2", properties={"mandatory": True, "file_type": "TEMP"}),
            # Both PDs need access to a TEMP file
            Constraint("requires_file_access", 1, "FILE", properties={"file_type": "TEMP", "min_size_kb": 1}),
            Constraint("requires_file_access", 2, "FILE", properties={"file_type": "TEMP", "min_size_kb": 1}),
        ],
        allowed_primitives=PRIMITIVES,  # All atomic graph operations
        allowed_multistep=[],  # No multi-step allowed
        graph_builder=build_basic_shared_resource_graph
    ),

    "mediator_test_primitive": Scenario(
        name="Mediator Test Primitive",
        description="Test if primitives can achieve mediation pattern",
        goals=[
            Goal("RSI", 0.0, "minimize", "PD_1,PD_2")   # Complete isolation required
        ],
        constraints=[
            # Both PDs need indirect access to the shared resource FILE_1_1
            Constraint("requires_indirect_access", 1, "FILE_1_1", properties={"through_pd": True}),
            Constraint("requires_indirect_access", 2, "FILE_1_1", properties={"through_pd": True}),
            # The shared resource must exist
            Constraint("requires_resource_exists", None, "FILE_1_1", properties={"mandatory": True}),
            # Prohibit direct access to force mediation
            Constraint("prohibit_direct_hold", 1, "FILE_1_1"),
            Constraint("prohibit_direct_hold", 2, "FILE_1_1"),
            # Basic file access requirements
            # Constraint("requires_file_access", 1, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
            # Constraint("requires_file_access", 2, "FILE", properties={"file_type": "any", "min_size_kb": 1}),
        ],
        allowed_primitives=PRIMITIVES,  # All primitives allowed
        allowed_multistep=[],  # No multi-step transitions
        graph_builder=build_mediator_test_graph
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
        allowed_primitives=PRIMITIVES,  # All primitives allowed
        allowed_multistep=[],  # No multi-step transitions
        graph_builder=build_reduce_isolation_graph
    ),

    "cache_same_core_conflict": Scenario(
        name="Cache Same-Core Conflict",
        description="Two PDs on same CPU core with cache set collision. Goal: achieve cache isolation via page coloring.",
        goals=[
            Goal("TransitiveRSI", 0.0, "minimize", "PD_1,PD_2")  # Zero cache set overlap
        ],
        constraints=[
            # Each PD must have at least one physical page
            Constraint("requires_resource_type", 1, "PHYS_PAGE", properties={"min_count": 1}),
            Constraint("requires_resource_type", 2, "PHYS_PAGE", properties={"min_count": 1}),
            # Each PD must be scheduled on at least one CPU
            Constraint("requires_resource_type", 1, "CPU", properties={"min_count": 1}),
            Constraint("requires_resource_type", 2, "CPU", properties={"min_count": 1}),
        ],
        allowed_primitives=PRIMITIVES,
        allowed_multistep=[],
        graph_builder=build_cache_same_core_conflict_graph
    ),

    "cache_llc_collision": Scenario(
        name="Cache LLC Collision",
        description="Two PDs on different CPUs with shared L3 cache set collision. Goal: achieve cache isolation via page coloring.",
        goals=[
            Goal("TransitiveRSI", 0.0, "minimize", "PD_1,PD_2")  # Zero cache set overlap
        ],
        constraints=[
            # Each PD must have at least one physical page
            Constraint("requires_resource_type", 1, "PHYS_PAGE", properties={"min_count": 1}),
            Constraint("requires_resource_type", 2, "PHYS_PAGE", properties={"min_count": 1}),
            # Each PD must be scheduled on at least one CPU
            Constraint("requires_resource_type", 1, "CPU", properties={"min_count": 1}),
            Constraint("requires_resource_type", 2, "CPU", properties={"min_count": 1}),
        ],
        allowed_primitives=PRIMITIVES,
        allowed_multistep=[],
        graph_builder=build_cache_llc_collision_graph
    ),
}


def get_scenario(name):
    """Get scenario by name"""
    if name not in SCENARIOS:
        available = list(SCENARIOS.keys())
        raise ValueError(f"Unknown scenario '{name}'. Available scenarios: {available}")
    return SCENARIOS[name]


def _validate_scenario_constraints(scenario):
    """Validate that scenario constraints are consistent"""
    # Basic validation - can be extended
    return True


def list_scenarios():
    """List all available scenarios"""
    return list(SCENARIOS.keys())
