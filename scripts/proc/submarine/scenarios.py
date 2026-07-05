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

        # Block removal if resource has only 1 holder and requires_resource_held applies
        for constraint in constraints:
            if (constraint.constraint_type == "requires_resource_held" and
                    constraint.resource_info == to_resource):
                holders = self._get_resource_holders(graph, to_resource)
                if len(holders) <= 1:
                    return False  # Would leave resource unowned

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

        # Boost for requires_resource_held violations: connecting any PD to an unowned resource
        for constraint in constraints:
            if constraint.constraint_type == "requires_resource_held":
                if constraint.resource_info == resource:
                    # Check if this resource currently has no holders
                    has_holder = any(
                        v == resource and d.get('type') == 'HOLD'
                        for _, v, d in graph.g.edges(data=True)
                    )
                    if not has_holder:
                        return 1.5  # Maximum boost: resource needs a holder

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


def build_crypto_cache_isolation_graph():
    """Build a graph modeling a crypto key server sharing hardware with untrusted web service.

    Real-world scenario:
    - TLS/crypto service handles sensitive key material
    - Web service handles untrusted user input
    - Both share CPU and L3 cache (vulnerable to cache timing + Spectre)

    Threat model:
    - Attacker controls PD_web via malicious input
    - Can perform Prime+Probe cache timing attacks
    - Can exploit speculative execution (Spectre)

    Initial state (vulnerable):
        PD_crypto -> CPU_1, PHYS_PAGE_1 (key memory) -> CACHE_SET_1
        PD_web    -> CPU_1, PHYS_PAGE_5 (attack buffer) -> CACHE_SET_1

        RSI:CPU = 1.0 (same core - Spectre risk)
        TransitiveRSI:CACHE_SET = 1.0 (same cache set - timing attack possible)

    Expected solutions:
        1. Page coloring: Move crypto keys to different cache set
        2. CPU pinning: Move crypto to dedicated core
    """
    graph = ModelGraph()

    # Add 2 PDs: crypto service and web service
    pd_crypto_id = NodeTransformations.add_pd_node(graph, "PD_crypto")
    pd_web_id = NodeTransformations.add_pd_node(graph, "PD_web")

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

    # VULNERABLE STATE: Both PDs on same CPU
    EdgeTransformations.add_hold_edge(graph, {Permission.R}, pd_crypto_id, ResourceType.CPU, cpu_space_id, cpu1_id)
    EdgeTransformations.add_hold_edge(graph, {Permission.R}, pd_web_id, ResourceType.CPU, cpu_space_id, cpu1_id)

    # Crypto service holds PHYS_PAGE_1 (AES keys/T-tables) -> maps to CACHE_SET_1
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd_crypto_id, ResourceType.PHYS_PAGE, phys_space_id, 1)

    # Web service holds PHYS_PAGE_5 (attack buffer) -> also maps to CACHE_SET_1 (COLLISION!)
    EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, pd_web_id, ResourceType.PHYS_PAGE, phys_space_id, 5)

    return graph


def build_ssh_prune_graph():
    """Build a graph modeling OpenSSH-inspired privilege separation.

    Five-component decomposition (extends real OpenSSH's 2-3 process model):
      PD_1 (PD_monitor)  - privileged root monitor: holds audit log
      PD_2 (PD_net)      - network handler: internet-facing, unprivileged, holds TCP socket
      PD_3 (PD_session)  - session manager: holds session state post-authentication
      PD_4 (PD_auth)     - authentication handler: holds user credentials (PAM / pubkey)
      PD_5 (PD_keystore) - key manager: holds SSH host private key (like ssh-agent or HSM)

    Resources (all FILE type, one FILE_SPACE):
      FILE_1_1  CONFIG    /etc/ssh/ssh_host_rsa_key  SSH host private key
      FILE_1_2  DATABASE  /etc/shadow                User credentials
      FILE_1_3  TEMP      /tmp/sshd_session          Session state (IPC approximation)
      FILE_1_4  SOCKET    /var/run/sshd.sock         Network socket
      FILE_1_5  LOG       /var/log/auth.log           Audit log

    OpenSSH accuracy:
      FILE_1_1, FILE_1_4, FILE_1_5 map directly to real OpenSSH resources.
      FILE_1_2 simplifies /etc/shadow + authorized_keys into one credential store.
      FILE_1_3 approximates the monitor<->child socketpair as a TEMP file.
      The PD_auth / PD_keystore split generalizes the real monitor (which holds both)
      to model a modern design with dedicated auth and key management services.

    G_0 (monolithic baseline):
      All 5 PDs hold all 5 resources. 25 HOLD edges. RSI = 1.0 for all 10 pairs.

    Target state (privilege separated):
      PD_1 -> FILE_1_5 only (audit log)
      PD_2 -> FILE_1_4 only (network socket)
      PD_3 -> FILE_1_3 only (session state)
      PD_4 -> FILE_1_2 only (credentials)
      PD_5 -> FILE_1_1 only (host key)
      REQUEST edges establish mediated access between components.
    """
    graph = ModelGraph()

    # Add 5 PDs in order — node IDs will be PD_1 through PD_5
    # (name param is display-only; actual node key is f"PD_{counter}")
    pd_monitor_id  = NodeTransformations.add_pd_node(graph, "PD_monitor")   # PD_1
    pd_net_id      = NodeTransformations.add_pd_node(graph, "PD_net")        # PD_2
    pd_session_id  = NodeTransformations.add_pd_node(graph, "PD_session")    # PD_3
    pd_auth_id     = NodeTransformations.add_pd_node(graph, "PD_auth")       # PD_4
    pd_keystore_id = NodeTransformations.add_pd_node(graph, "PD_keystore")   # PD_5

    # Add one FILE resource space
    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)

    # Add 5 FILE resources — node IDs will be FILE_1_1 through FILE_1_5
    hostkey_id     = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG,   "/etc/ssh/ssh_host_rsa_key", 1679)  # FILE_1_1
    cred_id        = NodeTransformations.add_file_resource(graph, space_id, FileType.DATABASE, "/etc/shadow",               4096)  # FILE_1_2
    session_id_res = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,     "/tmp/sshd_session",          512)  # FILE_1_3
    socket_id      = NodeTransformations.add_file_resource(graph, space_id, FileType.SOCKET,   "/var/run/sshd.sock",           0)  # FILE_1_4
    log_id         = NodeTransformations.add_file_resource(graph, space_id, FileType.LOG,      "/var/log/auth.log",         8192)  # FILE_1_5

    # G_0: all PDs hold all resources (monolithic, fully-shared baseline)
    pd_ids  = [pd_monitor_id, pd_net_id, pd_session_id, pd_auth_id, pd_keystore_id]
    res_ids = [hostkey_id, cred_id, session_id_res, socket_id, log_id]
    for pd in pd_ids:
        for res in res_ids:
            EdgeTransformations.add_hold_edge(
                graph, {Permission.R, Permission.W}, pd, ResourceType.FILE, space_id, res
            )

    return graph


def build_ssh_assign_graph():
    """G0 for ssh_assign: 5 PDs exist, but only PD_1 holds all resources.
    PDs 2-5 are unassigned (no HOLD edges). IsoSearch must discover the correct
    resource assignment by adding hold edges to PDs 2-5 and removing PD_1's excess holds.

    Same PD names/IDs and resources as build_ssh_prune_graph(), so goals/constraints
    reference the same PD_2..PD_5 strings — but the starting topology is different:
      ssh_prune:  25 HOLD edges (all PDs × all resources)
      ssh_assign:  5 HOLD edges (PD_1 only)
    """
    graph = ModelGraph()

    pd_monitor_id  = NodeTransformations.add_pd_node(graph, "PD_monitor")   # PD_1
    pd_net_id      = NodeTransformations.add_pd_node(graph, "PD_net")        # PD_2
    pd_session_id  = NodeTransformations.add_pd_node(graph, "PD_session")    # PD_3
    pd_auth_id     = NodeTransformations.add_pd_node(graph, "PD_auth")       # PD_4
    pd_keystore_id = NodeTransformations.add_pd_node(graph, "PD_keystore")   # PD_5

    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    hostkey_id     = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG,   "/etc/ssh/ssh_host_rsa_key", 1679)
    cred_id        = NodeTransformations.add_file_resource(graph, space_id, FileType.DATABASE, "/etc/shadow",               4096)
    session_id_res = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,     "/tmp/sshd_session",          512)
    socket_id      = NodeTransformations.add_file_resource(graph, space_id, FileType.SOCKET,   "/var/run/sshd.sock",           0)
    log_id         = NodeTransformations.add_file_resource(graph, space_id, FileType.LOG,      "/var/log/auth.log",         8192)

    # G0: ONLY PD_1 (monitor) holds all 5 resources — PDs 2-5 are empty
    for res in [hostkey_id, cred_id, session_id_res, socket_id, log_id]:
        EdgeTransformations.add_hold_edge(
            graph, {Permission.R, Permission.W}, pd_monitor_id, ResourceType.FILE, space_id, res)

    return graph


def build_ssh_discover_graph():
    """G0 for ssh_discover: a single PD holds all 5 resources.

    No PD names, no resource-to-PD assignments are pre-specified.
    IsoSearch must discover both the PD count and resource assignment purely
    from prohibit_co_hold constraints (which resources cannot share a PD)
    and a GlobalRSI minimization goal.

    Starting topology:
      1 PD (PD_1 / PD_monitor), 5 HOLD edges
      10 co-hold constraint violations (all critical pairs violated by PD_1)
      GlobalRSI = 1.0 (single-PD worst case)
    """
    graph = ModelGraph()

    pd_monitor_id = NodeTransformations.add_pd_node(graph, "PD_monitor")  # PD_1 only

    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    hostkey_id     = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG,   "/etc/ssh/ssh_host_rsa_key", 1679)  # FILE_1_1
    cred_id        = NodeTransformations.add_file_resource(graph, space_id, FileType.DATABASE, "/etc/shadow",               4096)  # FILE_1_2
    session_id_res = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,     "/tmp/sshd_session",          512)  # FILE_1_3
    socket_id      = NodeTransformations.add_file_resource(graph, space_id, FileType.SOCKET,   "/var/run/sshd.sock",           0)  # FILE_1_4
    log_id         = NodeTransformations.add_file_resource(graph, space_id, FileType.LOG,      "/var/log/auth.log",         8192)  # FILE_1_5

    for res in [hostkey_id, cred_id, session_id_res, socket_id, log_id]:
        EdgeTransformations.add_hold_edge(
            graph, {Permission.R, Permission.W}, pd_monitor_id, ResourceType.FILE, space_id, res)

    return graph


def build_webapp_3tier_graph():
    """Build a graph modeling a 5-PD three-tier web application, fully shared at G0.

    Five-component decomposition of a typical web application deployment:
      PD_1 (PD_frontend) - public-facing web/reverse-proxy tier
      PD_2 (PD_api)       - application/API server; the only intended path to the DB
      PD_3 (PD_db)        - database holding customer records
      PD_4 (PD_auth)      - authentication service holding session/auth tokens
      PD_5 (PD_cache)     - cache tier holding cache access keys

    Resources (all FILE type, one FILE_SPACE):
      FILE_1_1  DATABASE  /var/db/customers      Customer database credentials/data
      FILE_1_2  CONFIG    /etc/app/auth_tokens    Auth/session signing tokens
      FILE_1_3  SOCKET    /var/run/cache.sock     Cache access key/socket
      FILE_1_4  TEMP      /tmp/app_session        Session state
      FILE_1_5  LOG       /var/log/app_request.log  Request log

    G_0 (fully-shared baseline):
      All 5 PDs hold all 5 resources. 25 HOLD edges. RSI = 1.0 for all 10 pairs.

    Target: IsoSearch should rediscover that the database is reachable only via
    the API server, i.e. PD_frontend/PD_auth/PD_cache lose direct access to
    FILE_1_1 (customer DB) while PD_api and PD_db retain it.
    """
    graph = ModelGraph()

    pd_frontend_id = NodeTransformations.add_pd_node(graph, "PD_frontend")  # PD_1
    pd_api_id      = NodeTransformations.add_pd_node(graph, "PD_api")        # PD_2
    pd_db_id       = NodeTransformations.add_pd_node(graph, "PD_db")         # PD_3
    pd_auth_id     = NodeTransformations.add_pd_node(graph, "PD_auth")       # PD_4
    pd_cache_id    = NodeTransformations.add_pd_node(graph, "PD_cache")      # PD_5

    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)

    db_id      = NodeTransformations.add_file_resource(graph, space_id, FileType.DATABASE, "/var/db/customers",         4096)  # FILE_1_1
    auth_id    = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG,   "/etc/app/auth_tokens",       512)  # FILE_1_2
    cache_id   = NodeTransformations.add_file_resource(graph, space_id, FileType.SOCKET,   "/var/run/cache.sock",          0)  # FILE_1_3
    session_id = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,     "/tmp/app_session",           512)  # FILE_1_4
    log_id     = NodeTransformations.add_file_resource(graph, space_id, FileType.LOG,      "/var/log/app_request.log", 8192)  # FILE_1_5

    # G_0: all PDs hold all resources (fully-shared baseline)
    pd_ids  = [pd_frontend_id, pd_api_id, pd_db_id, pd_auth_id, pd_cache_id]
    res_ids = [db_id, auth_id, cache_id, session_id, log_id]
    for pd in pd_ids:
        for res in res_ids:
            EdgeTransformations.add_hold_edge(
                graph, {Permission.R, Permission.W}, pd, ResourceType.FILE, space_id, res
            )

    return graph


def build_ml_tenant_graph():
    """G0 for ml_tenant: a single monolithic ML server PD holds the model and all KV-caches.

    Real-world grounding: multi-tenant ML inference (SageMaker multi-model endpoints /
    shared GPU cluster). Each PD carries 50MB process overhead (runtime, stack, CUDA).
    The 320MB memory budget allows exactly 3 tenant PDs (3×50MB + 160MB = 310MB ≤ 320MB).
    A 4th PD would cost 360MB — violating the budget.

    Starting topology:
      1 PD (PD_1 / PD_server), 4 HOLD edges
      3 co-hold constraint violations (all cache pairs held by PD_server)
      Memory at G0: 50MB (PD overhead) + 160MB (resources) = 210MB
    """
    import json
    graph = ModelGraph()

    server_id = NodeTransformations.add_pd_node(graph, "PD_server")   # PD_1
    # Set 50MB process overhead on the initial PD node
    graph.g.nodes[f"PD_{server_id}"]['extra'] = json.dumps({"pd_overhead_bytes": 50_000_000})

    space_id  = NodeTransformations.add_resource_space(graph, ResourceType.FILE)
    model_id  = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG, "ml_model.bin",    100_000_000)  # FILE_1_1 ~100MB
    cache1_id = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,   "kv_cache_t1.bin",  20_000_000)  # FILE_1_2 ~20MB
    cache2_id = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,   "kv_cache_t2.bin",  20_000_000)  # FILE_1_3 ~20MB
    cache3_id = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,   "kv_cache_t3.bin",  20_000_000)  # FILE_1_4 ~20MB

    for res in [model_id, cache1_id, cache2_id, cache3_id]:
        EdgeTransformations.add_hold_edge(
            graph, {Permission.R, Permission.W}, server_id, ResourceType.FILE, space_id, res)

    return graph


def build_db_trust_graph():
    """G0 for db_trust: an over-provisioned PostgreSQL-like deployment with 8 violations.

    Real-world grounding: a naive deployment over-provisions PD_frontend with direct
    access to tls_key and auth_hba (resources it should never hold directly), while
    PD_backend holds tls_key alongside datadir and wal. Eight constraint violations must
    be resolved. IsoSearch discovers the signing-oracle pattern (Pattern B): PD_frontend
    must reach tls_key only through a REQUEST edge to a dedicated PD_tls.

    Starting topology (3 PDs, 9 resources, 8 violations):
      PD_1 (PD_frontend): conn.sock, query_pipe, txn_temp, tls_key, auth_hba
        - co-hold(conn.sock,  tls_key)         VIOLATED [A]
        - co-hold(txn_temp,   tls_key)         VIOLATED [B]
        - co-hold(tls_key,    auth_hba)        VIOLATED [C]
        - prohibit_direct_hold(PD_1, tls_key)  VIOLATED [F]
        - requires_indirect_access(PD_1, auth_hba) VIOLATED [G] — held directly
        - requires_indirect_access(PD_1, tls_key)  VIOLATED [P] — held directly, no REQUEST chain
      PD_2 (PD_backend):  datadir, wal, tls_key (shared with PD_1)
        - co-hold(datadir, tls_key)            VIOLATED [H]
        - co-hold(wal, tls_key)                VIOLATED [I]
      PD_3 (PD_admin):    auth_hba (shared with PD_1), audit_log, admin_sock
      REQUEST: PD_1 -> PD_3  (pre-added; satisfies indirect_access(auth_hba) once direct hold removed)

    TCB(PD_1) = {PD_2 [tls_key shared], PD_3 [REQUEST]} = 2
    TCB(PD_2) = {PD_1 [tls_key shared]}                 = 1
    Memory at G0: 3x30MB + 350MB = 440MB (budget = 530MB; max 6 PDs)

    Path to solution (~6 steps):
      1. remove_hold(PD_1, tls_key):       +4 (fixes A, B, C, F)
      2. remove_hold(PD_1, auth_hba):      +1 (fixes G: not held directly, REQUEST chain exists)
      3. remove_hold(PD_2, tls_key):       net +1 (fixes H, I; creates resource_held violation)
      4. add_pd + add_hold(PD_4, tls_key): +1 (resource_held fixed)
      5. add_request_edge(PD_1 -> PD_4):   +1 (fixes P: indirect_access tls_key satisfied)
      → 0 violations remaining; TCB(PD_1)=2 {PD_3,PD_4}, TCB(PD_2)=0, solution found
    """
    import json
    graph = ModelGraph()

    PD_OVERHEAD = 30_000_000  # 30 MB per PD

    # Three PDs
    frontend_id = NodeTransformations.add_pd_node(graph, "PD_frontend")   # PD_1
    graph.g.nodes[f"PD_{frontend_id}"]['extra'] = json.dumps({"pd_overhead_bytes": PD_OVERHEAD})

    backend_id  = NodeTransformations.add_pd_node(graph, "PD_backend")    # PD_2
    graph.g.nodes[f"PD_{backend_id}"]['extra']  = json.dumps({"pd_overhead_bytes": PD_OVERHEAD})

    admin_id    = NodeTransformations.add_pd_node(graph, "PD_admin")      # PD_3
    graph.g.nodes[f"PD_{admin_id}"]['extra']    = json.dumps({"pd_overhead_bytes": PD_OVERHEAD})

    space_id = NodeTransformations.add_resource_space(graph, ResourceType.FILE)

    conn_sock_id  = NodeTransformations.add_file_resource(graph, space_id, FileType.SOCKET,   "conn.sock",        0)          # FILE_1_1
    query_pipe_id = NodeTransformations.add_file_resource(graph, space_id, FileType.SOCKET,   "query_pipe",       0)          # FILE_1_2
    txn_temp_id   = NodeTransformations.add_file_resource(graph, space_id, FileType.TEMP,     "txn_temp",  50_000_000)        # FILE_1_3 50MB
    datadir_id    = NodeTransformations.add_file_resource(graph, space_id, FileType.DATABASE, "datadir",  200_000_000)        # FILE_1_4 200MB
    wal_id        = NodeTransformations.add_file_resource(graph, space_id, FileType.DATABASE, "wal",      100_000_000)        # FILE_1_5 100MB
    tls_key_id    = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG,   "tls_key",        4_096)        # FILE_1_6
    auth_hba_id   = NodeTransformations.add_file_resource(graph, space_id, FileType.CONFIG,   "auth_hba",       4_096)        # FILE_1_7
    audit_log_id  = NodeTransformations.add_file_resource(graph, space_id, FileType.LOG,      "audit_log",      8_192)        # FILE_1_8
    admin_sock_id = NodeTransformations.add_file_resource(graph, space_id, FileType.SOCKET,   "admin_sock",         0)        # FILE_1_9

    # PD_frontend: over-provisioned — holds tls_key and auth_hba in addition to its own resources
    for res in [conn_sock_id, query_pipe_id, txn_temp_id, tls_key_id, auth_hba_id]:
        EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, frontend_id, ResourceType.FILE, space_id, res)

    # PD_backend: holds datadir + wal + tls_key (shared with PD_1)
    # txn_temp intentionally NOT in PD_2 — it is a PD_1-only resource at G0
    for res in [datadir_id, wal_id, tls_key_id]:
        EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, backend_id,  ResourceType.FILE, space_id, res)

    # PD_admin: holds auth_hba (shared with frontend) + audit_log + admin_sock
    for res in [auth_hba_id, audit_log_id, admin_sock_id]:
        EdgeTransformations.add_hold_edge(graph, {Permission.R, Permission.W}, admin_id,    ResourceType.FILE, space_id, res)

    # Pre-add REQUEST edge PD_frontend -> PD_admin so that once the direct hold on
    # auth_hba is removed from PD_frontend, requires_indirect_access is satisfied.
    graph.g.add_edge(f"PD_{frontend_id}", f"PD_{admin_id}",
                     type='REQUEST', extra='{}')

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
        description="Two PDs on same CPU core with cache set collision. Goal: achieve cache isolation via page coloring AND/OR CPU migration.",
        goals=[
            # Two goals: page coloring (cache set isolation) AND CPU migration (separate cores)
            Goal("TransitiveRSI:CACHE_SET", 0.0, "minimize", "PD_1,PD_2"),  # Zero cache set overlap via page coloring
            Goal("RSI:CPU", 0.0, "minimize", "PD_1,PD_2"),  # Zero CPU sharing via CPU migration
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
            Goal("TransitiveRSI:CACHE_SET", 0.0, "minimize", "PD_1,PD_2"),  # Zero cache set overlap via page coloring
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

    "crypto_cache_isolation": Scenario(
        name="Crypto Key Server Isolation",
        description="TLS/crypto service shares CPU and L3 cache with untrusted web service. "
                    "Goal: prevent cache timing attacks (Prime+Probe) and speculative execution attacks (Spectre) "
                    "by discovering page coloring and CPU pinning.",
        goals=[
            # Prevent cache timing attacks (Prime+Probe on AES T-tables)
            Goal("TransitiveRSI:CACHE_SET", 0.0, "minimize", "PD_1,PD_2"),
            # Prevent speculative execution attacks (Spectre)
            Goal("RSI:CPU", 0.0, "minimize", "PD_1,PD_2"),
        ],
        constraints=[
            # Crypto service must have memory for keys
            Constraint("requires_resource_type", 1, "PHYS_PAGE", properties={"min_count": 1}),
            # Web service must have memory for buffers
            Constraint("requires_resource_type", 2, "PHYS_PAGE", properties={"min_count": 1}),
            # Both services must be scheduled
            Constraint("requires_resource_type", 1, "CPU", properties={"min_count": 1}),
            Constraint("requires_resource_type", 2, "CPU", properties={"min_count": 1}),
        ],
        allowed_primitives=PRIMITIVES,
        allowed_multistep=[],
        graph_builder=build_crypto_cache_isolation_graph
    ),

    "ssh_prune": Scenario(
        name="SSH Privilege Separation — Pruning",
        description=(
            "Five-component SSH daemon starting from a fully-shared monolithic baseline. "
            "IsoSearch must discover privilege separation: each component ends up holding "
            "only its own resource, with sensitive material (host key, credentials) "
            "isolated from the internet-facing network handler. "
            "Inspired by OpenSSH privsep (Provos 2002), extended to 5 PDs for scalability."
        ),
        goals=[
            # Primary: internet-facing handler must not share resources with key material
            Goal("RSI", 0.0, "minimize", "PD_2,PD_5"),  # net (PD_2) ↔ keystore (PD_5)
            Goal("RSI", 0.0, "minimize", "PD_2,PD_4"),  # net (PD_2) ↔ auth (PD_4)
            # Secondary: active sessions and net handler stay isolated post-auth
            Goal("RSI", 0.0, "minimize", "PD_2,PD_3"),  # net (PD_2) ↔ session (PD_3)
            Goal("RSI", 0.0, "minimize", "PD_3,PD_5"),  # session (PD_3) ↔ keystore (PD_5)
        ],
        constraints=[
            # Functional: each PD must retain direct access to its own resource
            Constraint("requires_resource_access", 1, "FILE_1_5", properties={"access_type": "direct"}),  # monitor keeps audit log
            Constraint("requires_resource_access", 2, "FILE_1_4", properties={"access_type": "direct"}),  # net keeps network socket
            Constraint("requires_resource_access", 3, "FILE_1_3", properties={"access_type": "direct"}),  # session keeps session state
            Constraint("requires_resource_access", 4, "FILE_1_2", properties={"access_type": "direct"}),  # auth keeps credentials
            Constraint("requires_resource_access", 5, "FILE_1_1", properties={"access_type": "direct"}),  # keystore keeps host key
            # Security invariants: PD_2 (net handler) must never directly hold sensitive resources
            Constraint("prohibit_direct_hold", 2, "FILE_1_1"),  # net never holds host key
            Constraint("prohibit_direct_hold", 2, "FILE_1_2"),  # net never holds credentials
        ],
        allowed_primitives=PRIMITIVES,
        allowed_multistep=[],
        graph_builder=build_ssh_prune_graph
    ),

    "ssh_assign": Scenario(
        name="SSH Privilege Separation — Assignment",
        description=(
            "Five-component SSH daemon. PDs 2-5 exist but hold no resources at start; "
            "only PD_1 holds all 5 resources. IsoSearch must discover the correct resource "
            "assignment: add hold edges to PDs 2-5 and remove PD_1's excess holds. "
            "Answers MIS's question: can IsoSearch discover the privilege-separated "
            "assignment from an unassigned starting point?"
        ),
        goals=[
            Goal("RSI", 0.0, "minimize", "PD_2,PD_5"),  # net ↔ keystore
            Goal("RSI", 0.0, "minimize", "PD_2,PD_4"),  # net ↔ auth
            Goal("RSI", 0.0, "minimize", "PD_2,PD_3"),  # net ↔ session
            Goal("RSI", 0.0, "minimize", "PD_3,PD_5"),  # session ↔ keystore
        ],
        constraints=[
            # Each PD must retain direct access to its designated resource
            Constraint("requires_resource_access", 1, "FILE_1_5", properties={"access_type": "direct"}),  # monitor keeps audit log
            Constraint("requires_resource_access", 2, "FILE_1_4", properties={"access_type": "direct"}),  # net keeps network socket
            Constraint("requires_resource_access", 3, "FILE_1_3", properties={"access_type": "direct"}),  # session keeps session state
            Constraint("requires_resource_access", 4, "FILE_1_2", properties={"access_type": "direct"}),  # auth keeps credentials
            Constraint("requires_resource_access", 5, "FILE_1_1", properties={"access_type": "direct"}),  # keystore keeps host key
            # Security invariants: PD_2 (net handler) must never directly hold sensitive resources
            Constraint("prohibit_direct_hold", 2, "FILE_1_1"),  # net never holds host key
            Constraint("prohibit_direct_hold", 2, "FILE_1_2"),  # net never holds credentials
        ],
        allowed_primitives=PRIMITIVES,
        allowed_multistep=[],
        graph_builder=build_ssh_assign_graph
    ),

    "ssh_discover": Scenario(
        name="SSH Privilege Separation — Full Discovery",
        description=(
            "Single-PD SSH daemon start. IsoSearch must discover both the PD count and "
            "resource assignment using only co-hold prohibitions and a global RSI goal — "
            "no PD names, no resource-to-PD assignments pre-specified. "
            "Directly answers MIS's question: can IsoSearch discover the 5-PD structure from scratch?"
        ),
        goals=[
            Goal("GlobalRSI", 0.0, "minimize"),  # minimize mean RSI across all PD pairs
        ],
        constraints=[
            # 4 critical co-hold prohibitions (same security invariants as ssh_prune/ssh_assign):
            Constraint("prohibit_co_hold", None, "FILE_1_4,FILE_1_1"),  # socket ↔ hostkey  (net↔key)
            Constraint("prohibit_co_hold", None, "FILE_1_4,FILE_1_2"),  # socket ↔ creds    (net↔auth)
            Constraint("prohibit_co_hold", None, "FILE_1_4,FILE_1_3"),  # socket ↔ session  (net↔sess)
            Constraint("prohibit_co_hold", None, "FILE_1_3,FILE_1_1"),  # session ↔ hostkey (sess↔key)
            # Each resource must remain held by at least one PD (prevents orphaning)
            Constraint("requires_resource_held", None, "FILE_1_1"),
            Constraint("requires_resource_held", None, "FILE_1_2"),
            Constraint("requires_resource_held", None, "FILE_1_3"),
            Constraint("requires_resource_held", None, "FILE_1_4"),
            Constraint("requires_resource_held", None, "FILE_1_5"),
        ],
        # Restrict to additive primitives only — resource/PD deletion would trivially
        # satisfy co-hold constraints by removing resources rather than redistributing them.
        allowed_primitives=[
            "add_pd", "add_hold_edge", "remove_hold_edge",
            "add_request_edge", "remove_request_edge",
        ],
        allowed_multistep=[],
        graph_builder=build_ssh_discover_graph
    ),

    "webapp_3tier": Scenario(
        name="Three-Tier Web Application",
        description=(
            "Five-PD three-tier web application (frontend, api, db, auth, cache) starting "
            "from a fully-shared monolithic baseline. IsoSearch must discover that the "
            "database is reachable only via the API server: frontend, auth, and cache lose "
            "direct access to the customer database, mirroring a real deployment where only "
            "the application tier talks to the DB directly."
        ),
        goals=[
            # Primary: DB must not be directly shared with frontend, auth, or cache
            Goal("RSI", 0.0, "minimize", "PD_1,PD_3"),  # frontend (PD_1) <-> db (PD_3)
            Goal("RSI", 0.0, "minimize", "PD_3,PD_4"),  # db (PD_3) <-> auth (PD_4)
            Goal("RSI", 0.0, "minimize", "PD_3,PD_5"),  # db (PD_3) <-> cache (PD_5)
            # Secondary: reduce overall sharing across the deployment
            Goal("GlobalRSI", 0.3, "minimize"),
        ],
        constraints=[
            # Functional: each PD must retain direct access to its own resource
            Constraint("requires_resource_access", 1, "FILE_1_5", properties={"access_type": "direct"}),  # frontend keeps request log
            Constraint("requires_resource_access", 2, "FILE_1_1", properties={"access_type": "direct"}),  # api keeps DB access
            Constraint("requires_resource_access", 3, "FILE_1_1", properties={"access_type": "direct"}),  # db keeps DB access
            Constraint("requires_resource_access", 4, "FILE_1_2", properties={"access_type": "direct"}),  # auth keeps auth tokens
            Constraint("requires_resource_access", 5, "FILE_1_3", properties={"access_type": "direct"}),  # cache keeps cache socket
            # Security invariants: only PD_api and PD_db may directly hold the customer DB
            Constraint("prohibit_direct_hold", 1, "FILE_1_1"),  # frontend never holds DB directly
            Constraint("prohibit_direct_hold", 4, "FILE_1_1"),  # auth never holds DB directly
            Constraint("prohibit_direct_hold", 5, "FILE_1_1"),  # cache never holds DB directly
        ],
        allowed_primitives=PRIMITIVES,
        allowed_multistep=[],
        graph_builder=build_webapp_3tier_graph
    ),

    "ml_tenant": Scenario(
        name="Multi-Tenant ML Inference",
        description=(
            "Monolithic ML server → 3 tenant PDs with private KV-caches. "
            "Each PD carries 50MB process overhead; the 320MB memory budget permits exactly "
            "3 PDs (310MB), preventing a fully-isolated 4-PD design (360MB). "
            "IsoSearch discovers the budget-constrained optimum: GlobalRSI = 1/3."
        ),
        goals=[
            Goal("GlobalRSI", 0.5, "minimize"),  # target 0.5; achievable at 1/3 with 3 PDs
        ],
        constraints=[
            # Tenant KV-caches must be in separate PDs (cross-tenant cache access = data leak)
            Constraint("prohibit_co_hold", None, "FILE_1_2,FILE_1_3"),  # cache_t1 ↔ cache_t2
            Constraint("prohibit_co_hold", None, "FILE_1_2,FILE_1_4"),  # cache_t1 ↔ cache_t3
            Constraint("prohibit_co_hold", None, "FILE_1_3,FILE_1_4"),  # cache_t2 ↔ cache_t3
            # All resources must remain held by at least one PD
            Constraint("requires_resource_held", None, "FILE_1_1"),  # model
            Constraint("requires_resource_held", None, "FILE_1_2"),  # cache_t1
            Constraint("requires_resource_held", None, "FILE_1_3"),  # cache_t2
            Constraint("requires_resource_held", None, "FILE_1_4"),  # cache_t3
            # Memory budget: 320MB total; 50MB per-PD process overhead
            # 3 PDs: 3×50 + 160 = 310MB ✓   4 PDs: 4×50 + 160 = 360MB ✗
            Constraint("max_memory_bytes", None, None, properties={
                "limit_bytes":       320_000_000,
                "pd_overhead_bytes":  50_000_000,
            }),
        ],
        # Restrict to hold-edge primitives only.
        # Deletion primitives removed: remove_file_resource would trivially satisfy
        # co-hold constraints by deleting caches; remove_pd allows thrashing.
        # Request-edge primitives removed: irrelevant for cache isolation (no request
        # edges in the optimal solution), and they generate many score-90 lateral states
        # that crowd out useful score-89 intermediates in the beam.
        allowed_primitives=["add_pd", "add_hold_edge", "remove_hold_edge"],
        allowed_multistep=[],
        graph_builder=build_ml_tenant_graph
    ),

    "db_trust": Scenario(
        name="DB Trust Tiers (PostgreSQL-like)",
        description=(
            "Over-provisioned 3-PD PostgreSQL-like deployment → trust-tiered design with "
            "signing-oracle pattern (Pattern B). PD_frontend must reach tls_key only via "
            "a REQUEST edge to PD_tls (signing oracle), and auth_hba only via REQUEST to "
            "PD_admin. A 530 MB budget caps PD count at 6. IsoSearch minimizes "
            "TCB(PD_frontend)≤2, TCB(PD_backend)=0, and GlobalRSI simultaneously using "
            "all five constraint types."
        ),
        goals=[
            Goal("TCB",       2,   "minimize", "PD_1"),   # TCB(frontend) = 2: PD_admin (auth) + PD_tls (key)
            Goal("TCB",       0,   "minimize", "PD_2"),   # TCB(backend) = 0: fully isolated storage
            Goal("GlobalRSI", 0.3, "minimize"),            # reduce global resource sharing index
        ],
        constraints=[
            # Co-hold prohibitions — no single PD may hold both resources simultaneously.
            # tls_key (FILE_1_6) must be isolated from all other sensitive resources.
            # Five co-holds involving tls_key ensure each removal of tls_key from a PD
            # fixes multiple violations at once, giving the scoring strong positive signal.
            Constraint("prohibit_co_hold", None, "FILE_1_4,FILE_1_6"),  # datadir <-> tls_key [VIOLATED: PD_2]
            Constraint("prohibit_co_hold", None, "FILE_1_5,FILE_1_6"),  # wal <-> tls_key [VIOLATED: PD_2]
            Constraint("prohibit_co_hold", None, "FILE_1_3,FILE_1_6"),  # txn_temp <-> tls_key [VIOLATED: PD_1]
            Constraint("prohibit_co_hold", None, "FILE_1_1,FILE_1_6"),  # conn.sock <-> tls_key [VIOLATED: PD_1]
            Constraint("prohibit_co_hold", None, "FILE_1_6,FILE_1_7"),  # tls_key <-> auth_hba [VIOLATED: PD_1]
            # Direct-hold prohibition: PD_frontend must never directly hold tls_key [VIOLATED at G0]
            Constraint("prohibit_direct_hold", 1, "FILE_1_6"),
            # Indirect access (auth): PD_frontend must reach auth_hba through a mediator.
            # The PD_1->PD_3 REQUEST edge is pre-wired in G0; once the direct hold on
            # auth_hba is removed from PD_1, this constraint becomes satisfied. [VIOLATED at G0]
            Constraint("requires_indirect_access", 1, "FILE_1_7"),
            # Indirect access (TLS key / Pattern B): PD_frontend must reach tls_key through
            # a mediator — the signing-oracle pattern. PD_frontend sends raw TLS bytes to
            # PD_tls via REQUEST; PD_tls performs crypto and returns the result.
            # Requires: PD_1 not hold FILE_1_6 directly AND PD_1→REQUEST→PD_tls→HOLD→FILE_1_6.
            # [VIOLATED at G0: PD_1 holds FILE_1_6 directly; no REQUEST chain exists]
            Constraint("requires_indirect_access", 1, "FILE_1_6"),
            # All 9 resources must remain held by at least one PD
            Constraint("requires_resource_held", None, "FILE_1_1"),
            Constraint("requires_resource_held", None, "FILE_1_2"),
            Constraint("requires_resource_held", None, "FILE_1_3"),
            Constraint("requires_resource_held", None, "FILE_1_4"),
            Constraint("requires_resource_held", None, "FILE_1_5"),
            Constraint("requires_resource_held", None, "FILE_1_6"),
            Constraint("requires_resource_held", None, "FILE_1_7"),
            Constraint("requires_resource_held", None, "FILE_1_8"),
            Constraint("requires_resource_held", None, "FILE_1_9"),
            # Memory budget: 530 MB -> max 6 PDs (6x30 + 350 = 530MB; 7th PD would need 560MB)
            Constraint("max_memory_bytes", None, None, properties={
                "limit_bytes":       530_000_000,
                "pd_overhead_bytes":  30_000_000,
            }),
        ],
        # Hold-edge and add_request_edge primitives. add_request_edge is needed so the
        # algorithm can wire PD_1→REQUEST→PD_tls (Pattern B / signing oracle).
        # remove_request_edge is excluded: the pre-wired PD_1→PD_3 REQUEST edge is load-bearing
        # for requires_indirect_access(PD_1, auth_hba) and must not be removable.
        # Flood control: spurious REQUEST edges increase TCB(PD_1), directly penalising the
        # minimize-TCB goal; only the two mandated edges (PD_admin, PD_tls) hit TCB=2.
        allowed_primitives=["add_pd", "add_hold_edge", "remove_hold_edge", "add_request_edge"],
        allowed_multistep=[],
        graph_builder=build_db_trust_graph
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
