"""
Comprehensive constraint validation for IsoSearch
"""

from generic_model import EdgeType


def validate_all_constraints(graph, constraints):
    """
    Validate all constraints are satisfied in the current graph state
    Returns: (bool, list of violation messages)
    """
    violations = []
    
    for constraint in constraints:
        is_satisfied, message = validate_constraint(graph, constraint)
        if not is_satisfied:
            violations.append(message)
    
    return len(violations) == 0, violations


def validate_constraint(graph, constraint):
    """
    Validate a single constraint
    Returns: (bool satisfied, str message)
    """
    if constraint.constraint_type == "requires_file_access":
        return validate_requires_file_access(graph, constraint)
    elif constraint.constraint_type == "requires_communication":
        return validate_requires_communication(graph, constraint)
    elif constraint.constraint_type == "prohibit_direct_hold":
        return validate_prohibit_direct_hold(graph, constraint)
    elif constraint.constraint_type == "requires_indirect_access":
        return validate_requires_indirect_access(graph, constraint)
    else:
        return False, f"Unknown constraint type: {constraint.constraint_type}"


def validate_requires_file_access(graph, constraint):
    """PD must have access to files matching the constraint"""
    pd_string = f"PD_{constraint.pd_id}"
    required_type = constraint.properties.get('file_type', 'any')
    min_size_kb = constraint.properties.get('min_size_kb', 0)
    
    # Find all files this PD holds
    total_size = 0
    has_required_type = False
    
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if from_node == pd_string and edge_data.get('type') == 'HOLD':
            # Check if this is a FILE resource
            node_data = graph.g.nodes.get(to_node, {})
            if node_data.get('type') == 'RESOURCE' and node_data.get('data') == 'FILE':
                # Check file type
                if required_type == 'any':
                    has_required_type = True
                else:
                    import json
                    try:
                        extra = json.loads(node_data.get('extra', '{}'))
                        if extra.get('file_type', '').upper() == required_type.upper():
                            has_required_type = True
                    except:
                        pass
                
                # Add to total size
                try:
                    extra = json.loads(node_data.get('extra', '{}'))
                    size_bytes = int(extra.get('size_bytes', 0))
                    total_size += size_bytes / 1024  # Convert to KB
                except:
                    pass
    
    if not has_required_type:
        return False, f"{pd_string} lacks access to {required_type} files"
    
    if total_size < min_size_kb:
        return False, f"{pd_string} has only {total_size}KB of files (needs {min_size_kb}KB)"
    
    return True, f"{pd_string} has required file access"


def validate_requires_communication(graph, constraint):
    """PD must have communication path to target PD"""
    pd_string = f"PD_{constraint.pd_id}"
    target_pd_string = f"PD_{constraint.target_pd}"
    
    # Check for direct REQUEST edge
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if (from_node == pd_string and to_node == target_pd_string and 
            edge_data.get('type') == 'REQUEST'):
            return True, f"{pd_string} has direct communication to {target_pd_string}"
    
    # Could also check for indirect paths through shared resources
    # For now, we only check direct REQUEST edges
    
    return False, f"{pd_string} lacks communication path to {target_pd_string}"


def validate_prohibit_direct_hold(graph, constraint):
    """PD must NOT directly hold the specified resource"""
    pd_string = f"PD_{constraint.pd_id}"
    prohibited_resource = constraint.resource_info
    
    # Check if this HOLD edge exists
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if (from_node == pd_string and to_node == prohibited_resource and 
            edge_data.get('type') == 'HOLD'):
            return False, f"{pd_string} has prohibited direct hold on {prohibited_resource}"
    
    return True, f"{pd_string} does not directly hold {prohibited_resource}"


def validate_requires_indirect_access(graph, constraint):
    """
    PD must have indirect access to resource (through REQUEST edges)
    This is the key constraint for forcing mediation discovery
    """
    pd_string = f"PD_{constraint.pd_id}"
    target_resource = constraint.resource_info
    
    # First, ensure PD does NOT have direct access
    has_direct_access = False
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if (from_node == pd_string and to_node == target_resource and 
            edge_data.get('type') == 'HOLD'):
            has_direct_access = True
            break
    
    if has_direct_access:
        return False, f"{pd_string} has direct access to {target_resource} (should be indirect)"
    
    # Now check for indirect access paths
    # Path 1: PD -> REQUEST -> Mediator PD -> HOLD -> Resource
    has_indirect_access = False
    
    # Find all PDs that this PD has REQUEST edges to
    requested_pds = []
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if from_node == pd_string and edge_data.get('type') == 'REQUEST':
            requested_pds.append(to_node)
    
    # Check if any of those PDs hold the target resource
    for mediator_pd in requested_pds:
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if (from_node == mediator_pd and to_node == target_resource and 
                edge_data.get('type') == 'HOLD'):
                has_indirect_access = True
                break
        if has_indirect_access:
            break
    
    if not has_indirect_access:
        return False, f"{pd_string} lacks indirect access to {target_resource}"
    
    return True, f"{pd_string} has indirect access to {target_resource} through mediation"


def check_constraints_before_transformation(graph, constraints, transformation_type, params):
    """
    Check if a transformation would violate constraints
    Returns: (bool allowed, str reason)
    """
    # For now, we mainly check prohibit_direct_hold
    if transformation_type == "add_hold_edge":
        pd = params.get('pd', '')
        resource = params.get('resource', '')
        
        for constraint in constraints:
            if constraint.constraint_type == "prohibit_direct_hold":
                pd_string = f"PD_{constraint.pd_id}"
                prohibited_resource = constraint.resource_info
                if pd == pd_string and resource == prohibited_resource:
                    return False, f"Would violate prohibit_direct_hold constraint"
    
    # TODO: Add more pre-transformation checks
    
    return True, "Transformation allowed"


def suggest_constraint_fixing_operations(graph, constraints):
    """
    Suggest operations that would help satisfy violated constraints
    Returns: list of (operation, params, reason) tuples
    """
    suggestions = []
    
    is_valid, violations = validate_all_constraints(graph, constraints)
    
    for violation in violations:
        # Parse violation message to understand what's needed
        if "lacks indirect access" in violation:
            # Need to create mediation structure
            # Extract PD and resource from message
            parts = violation.split()
            pd = parts[0]
            resource = parts[-1]
            
            suggestions.append((
                "add_pd",
                {"pd_type": "mediator"},
                f"Create mediator for {resource} access"
            ))
            
            suggestions.append((
                "add_request_edge",
                {"from_pd": pd, "to_pd": "new_mediator"},
                f"Connect {pd} to mediator via REQUEST"
            ))
        
        elif "has prohibited direct hold" in violation:
            # Need to remove direct hold
            parts = violation.split()
            pd = parts[0]
            resource = parts[-1]
            
            suggestions.append((
                "remove_hold_edge",
                {"from_pd": pd, "to_resource": resource},
                f"Remove prohibited direct hold"
            ))
    
    return suggestions