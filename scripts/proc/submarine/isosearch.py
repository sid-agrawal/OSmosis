"""
IsoSearch Algorithm Implementation - Baby Steps
"""

# Import our graph transformation capabilities
from graph_transformations import NodeTransformations, EdgeTransformations
from generic_model import ModelGraph, ResourceType, VmrType, Permission, EdgeType

class Goal:
    """
    Simple goal structure for design space exploration
    """
    def __init__(self, metric_name, target_value, direction="minimize"):
        self.metric_name = metric_name  # e.g., "RSI", "TCB", "FR", "IB"
        self.target_value = target_value  # e.g., 0.5, 10, etc.
        self.direction = direction  # "minimize" or "maximize"
    
    def __str__(self):
        return f"Goal({self.direction} {self.metric_name} to {self.target_value})"


class Constraint:
    """
    Simple constraint structure for functional requirements
    """
    def __init__(self, constraint_type, pd_id, resource_info=None):
        self.constraint_type = constraint_type  # e.g., "requires_resource", "must_communicate"
        self.pd_id = pd_id  # The PD this constraint applies to
        self.resource_info = resource_info  # Additional info (resource type, target PD, etc.)
    
    def __str__(self):
        return f"Constraint({self.constraint_type} for PD{self.pd_id}: {self.resource_info})"


class Transition:
    """
    Simple transition structure for allowed graph modifications
    """
    def __init__(self, transition_type, description=""):
        self.transition_type = transition_type  # e.g., "privatize_resource", "add_mediator_pd"
        self.description = description  # Human-readable description
    
    def __str__(self):
        return f"Transition({self.transition_type}: {self.description})"


def ComputeMetrics(candidate):
    """
    Compute metrics for a candidate graph (RSI, FR, TCB, IB)
    Returns: dictionary of metric values
    """
    print("  Computing metrics...")
    
    # Find all PDs in the graph
    pd_nodes = [node for node, data in candidate.g.nodes(data=True) 
                if data.get('type') == 'PD']
    
    metrics = {}
    
    # Calculate RSI (Resource Sharing Index) by resource type
    metrics['RSI'] = _calculate_rsi_by_type(candidate, pd_nodes)
    
    # Calculate ASR (Attack Surface Ratio) - attack paths per PD
    metrics['ASR'] = _calculate_asr(candidate, pd_nodes)
    
    # Calculate TCB (Trusted Computing Base) size
    metrics['TCB'] = _calculate_tcb(candidate, pd_nodes)
    
    print(f"    RSI: {metrics['RSI']}, ASR: {metrics['ASR']}, TCB: {metrics['TCB']}")
    return metrics


def _calculate_rsi_by_type(graph, pd_nodes):
    """Calculate RSI (Resource Sharing Index) by resource type"""
    
    # Group resources by type and track which PDs access them
    resource_type_access = {}
    
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            # Determine resource type from the target node
            resource_type = _get_resource_type(graph, to_node)
            
            if resource_type not in resource_type_access:
                resource_type_access[resource_type] = {}
            
            if to_node not in resource_type_access[resource_type]:
                resource_type_access[resource_type][to_node] = set()
            
            resource_type_access[resource_type][to_node].add(from_node)
    
    # Calculate RSI for each resource type
    rsi_by_type = {}
    
    for resource_type, resources in resource_type_access.items():
        shared_count = 0
        total_count = len(resources)
        
        # Count how many resources of this type are shared
        for resource_id, accessing_pds in resources.items():
            if len(accessing_pds) > 1:
                shared_count += 1
        
        # RSI = shared_resources / total_resources for this type
        rsi_by_type[resource_type] = shared_count / total_count if total_count > 0 else 0.0
    
    return rsi_by_type


def _get_resource_type(graph, resource_node):
    """Get the resource type from a resource node"""
    # Check if it's a resource space
    node_data = graph.g.nodes.get(resource_node, {})
    node_type = node_data.get('type', '')
    
    if node_type == 'RESOURCE_SPACE':
        return node_data.get('data', 'UNKNOWN')
    elif node_type == 'RESOURCE':
        return node_data.get('data', 'UNKNOWN')
    else:
        # Try to infer from node name
        if 'VMR' in resource_node:
            return 'VMR'
        elif 'MO' in resource_node:
            return 'MO'
        elif 'FILE' in resource_node:
            return 'FILE'
        elif 'VCPU' in resource_node:
            return 'VCPU'
        elif 'PCPU' in resource_node:
            return 'PCPU'
        else:
            return 'UNKNOWN'


def _calculate_asr(graph, pd_nodes):
    """Calculate ASR (Attack Surface Ratio) - potential attack paths per PD"""
    # Count edges that could be attack paths (HOLD, REQUEST, MAP edges)
    attack_edges = 0
    
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        edge_type = edge_data.get('type')
        if edge_type in ['HOLD', 'REQUEST', 'MAP']:
            attack_edges += 1
    
    # Normalize by number of PDs
    return attack_edges / len(pd_nodes) if pd_nodes else 0


def _calculate_tcb(graph, pd_nodes):
    """Calculate TCB (Trusted Computing Base) - for each PD, list of PDs that have authority over it OR share resources with it"""
    # For each PD, find which PDs have authority over it OR share resources with it
    tcb_by_pd = {}
    
    # Initialize empty TCB lists for all PDs
    for pd_node in pd_nodes:
        tcb_by_pd[pd_node] = []
    
    # 1. Find authority relationships
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        edge_type = edge_data.get('type', '')
        
        # Direct authority: REQUEST edges show authority relationship
        if edge_type == 'REQUEST' and from_node.startswith('PD_') and to_node.startswith('PD_'):
            # from_node requests from to_node, so to_node has authority over from_node
            if from_node in tcb_by_pd and to_node not in tcb_by_pd[from_node]:
                tcb_by_pd[from_node].append(to_node)
        
        # Other direct authority relationships
        elif edge_type in ['AUTHORITY', 'CONTROL'] and from_node.startswith('PD_') and to_node.startswith('PD_'):
            # from_node has authority over to_node
            if to_node in tcb_by_pd and from_node not in tcb_by_pd[to_node]:
                tcb_by_pd[to_node].append(from_node)
    
    # Check for authority through resource control (pd_incharge fields)
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        extra = edge_data.get('extra', '{}')
        try:
            import json
            extra_dict = json.loads(extra) if extra else {}
            pd_incharge = extra_dict.get('pd_incharge', '')
            
            # Find which PD is in charge
            controller_pd = None
            for pd_node in pd_nodes:
                if (pd_incharge == pd_node.replace('PD_', '').lower() or 
                    pd_incharge == pd_node):
                    controller_pd = pd_node
                    break
            
            # If a PD controls this edge and it affects another PD, that's authority
            if controller_pd and edge_data.get('type') == 'HOLD':
                affected_pd = from_node if from_node.startswith('PD_') else None
                if (affected_pd and affected_pd != controller_pd and 
                    affected_pd in tcb_by_pd and 
                    controller_pd not in tcb_by_pd[affected_pd]):
                    tcb_by_pd[affected_pd].append(controller_pd)
        except:
            pass
    
    # 2. Find resource sharing relationships
    resource_holders = {}
    
    # Build map of which PDs hold which resources
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_holders:
                resource_holders[to_node] = []
            resource_holders[to_node].append(from_node)
    
    # For each shared resource, add sharing PDs to each other's TCB
    for resource, holders in resource_holders.items():
        if len(holders) > 1:  # Shared resource
            for pd in holders:
                for other_pd in holders:
                    if (pd != other_pd and 
                        pd in tcb_by_pd and 
                        other_pd not in tcb_by_pd[pd]):
                        tcb_by_pd[pd].append(other_pd)
    
    return tcb_by_pd




def GoalsMet(metrics, goals):
    """
    Check if the computed metrics meet the specified goals
    Returns: boolean indicating if all goals are satisfied
    """
    for goal in goals:
        metric_value = metrics.get(goal.metric_name)
        if metric_value is None:
            print(f"    Warning: Metric {goal.metric_name} not found in results")
            return False
        
        # Handle RSI map format
        if goal.metric_name == "RSI" and isinstance(metric_value, dict):
            # For RSI map, check if any resource type violates the goal
            goal_violated = False
            for resource_type, rsi_value in metric_value.items():
                if goal.direction == "minimize":
                    if rsi_value > goal.target_value:
                        print(f"    Goal not met: RSI[{resource_type}]={rsi_value:.3f} > {goal.target_value}")
                        goal_violated = True
                elif goal.direction == "maximize":
                    if rsi_value < goal.target_value:
                        print(f"    Goal not met: RSI[{resource_type}]={rsi_value:.3f} < {goal.target_value}")
                        goal_violated = True
            
            if goal_violated:
                return False
        
        # Handle TCB map format (per-PD authority and sharing lists)
        elif goal.metric_name == "TCB" and isinstance(metric_value, dict):
            goal_violated = False
            for pd, tcb_list in metric_value.items():
                tcb_count = len(tcb_list)
                if goal.direction == "minimize":
                    if tcb_count > goal.target_value:
                        dependencies = ", ".join(tcb_list) if tcb_list else "none"
                        print(f"    Goal not met: TCB[{pd}]={tcb_count} > {goal.target_value} (dependencies: {dependencies})")
                        goal_violated = True
                elif goal.direction == "maximize":
                    if tcb_count < goal.target_value:
                        dependencies = ", ".join(tcb_list) if tcb_list else "none"
                        print(f"    Goal not met: TCB[{pd}]={tcb_count} < {goal.target_value} (dependencies: {dependencies})")
                        goal_violated = True
            
            if goal_violated:
                return False
        else:
            # Handle scalar metrics (ASR)
            if goal.direction == "minimize":
                if metric_value > goal.target_value:
                    print(f"    Goal not met: {goal.metric_name}={metric_value} > {goal.target_value}")
                    return False
            elif goal.direction == "maximize":
                if metric_value < goal.target_value:
                    print(f"    Goal not met: {goal.metric_name}={metric_value} < {goal.target_value}")
                    return False
                
    print(f"    All {len(goals)} goals met!")
    return True


def GenerateCandidate(graph, constraints, transitions, goals):
    """
    Generate a new candidate graph by applying a transition
    Uses smart selection to choose the best node/edge for transformation
    Returns: new graph or None if no valid transition found
    """
    import copy
    
    # Get all possible transformations with their predicted impact
    transformation_candidates = []
    
    for transition in transitions:
        candidates = _find_transformation_candidates(graph, transition, constraints, goals)
        transformation_candidates.extend(candidates)
    
    if not transformation_candidates:
        print("  No valid transitions found")
        return None
    
    # Sort by predicted metric improvement (best first)
    transformation_candidates.sort(key=lambda x: x['predicted_improvement'], reverse=True)
    
    # Try the best transformation candidate
    best_candidate = transformation_candidates[0]
    candidate_graph = copy.deepcopy(graph)
    
    print(f"  Trying best transition: {best_candidate['transition_type']}")
    print(f"    Target: {best_candidate['target_description']}")
    print(f"    Predicted improvement: {best_candidate['predicted_improvement']:.3f}")
    
    success = _apply_specific_transformation(candidate_graph, best_candidate)
    
    if success:
        print(f"    ✅ Applied {best_candidate['transition_type']}")
        return candidate_graph
    else:
        print(f"    ❌ Failed to apply {best_candidate['transition_type']}")
        return None


def _find_transformation_candidates(graph, transition, constraints, goals):
    """
    Find all possible applications of a transformation and estimate their impact
    Returns: list of transformation candidates with predicted improvements
    """
    candidates = []
    
    if transition.transition_type == "privatize_resource":
        candidates.extend(_find_privatization_candidates(graph, constraints, goals))
    elif transition.transition_type == "add_mediator_pd":
        candidates.extend(_find_mediation_candidates(graph, constraints, goals))
    elif transition.transition_type == "remove_hold_edge":
        candidates.extend(_find_edge_removal_candidates(graph, constraints, goals))
    
    return candidates


def _find_privatization_candidates(graph, constraints, goals):
    """Find all shared resources that could be privatized and estimate RSI improvement"""
    candidates = []
    resource_holders = {}
    
    # Find all shared resources
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and to_node.startswith('VMR_'):
            if to_node not in resource_holders:
                resource_holders[to_node] = []
            resource_holders[to_node].append(from_node)
    
    # Evaluate each shared resource
    for resource, holders in resource_holders.items():
        if len(holders) > 1:
            if _check_privatization_constraints(resource, holders, constraints):
                # Predict RSI improvement: privatization reduces sharing significantly
                current_rsi = len(holders) / len(holders)  # Full sharing
                predicted_rsi = 0.0  # No sharing after privatization
                improvement = current_rsi - predicted_rsi
                
                candidates.append({
                    'transition_type': 'privatize_resource',
                    'target_resource': resource,
                    'target_holders': holders,
                    'target_description': f"resource {resource} (shared by {len(holders)} PDs)",
                    'predicted_improvement': improvement,
                    'constraint_violations': 0
                })
    
    return candidates


def _find_mediation_candidates(graph, constraints, goals):
    """Find PD pairs that could benefit from mediation"""
    candidates = []
    resource_sharers = {}
    
    # Find resources shared by exactly 2 PDs
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_sharers:
                resource_sharers[to_node] = []
            resource_sharers[to_node].append(from_node)
    
    for resource, sharers in resource_sharers.items():
        if len(sharers) == 2:
            if _check_mediation_constraints(resource, sharers, constraints):
                # Predict metric improvement: mediation can reduce TCB size
                improvement = 0.5  # Moderate improvement for access control
                
                candidates.append({
                    'transition_type': 'add_mediator_pd',
                    'target_resource': resource,
                    'target_sharers': sharers,
                    'target_description': f"mediate access to {resource} between {sharers}",
                    'predicted_improvement': improvement,
                    'constraint_violations': 0
                })
    
    return candidates


def _find_edge_removal_candidates(graph, constraints, goals):
    """Find HOLD edges that could be safely removed"""
    candidates = []
    
    hold_edges = [(f, t, d) for f, t, d in graph.g.edges(data=True) 
                  if d.get('type') == 'HOLD']
    
    for from_node, to_node, edge_data in hold_edges:
        if _can_remove_hold_edge(from_node, to_node, constraints):
            # Predict improvement: removing edges reduces fault ratio
            improvement = 0.3  # Small but positive improvement
            
            candidates.append({
                'transition_type': 'remove_hold_edge',
                'target_from': from_node,
                'target_to': to_node,
                'target_description': f"remove {from_node} -> {to_node} HOLD edge",
                'predicted_improvement': improvement,
                'constraint_violations': 0
            })
    
    return candidates


def _apply_specific_transformation(graph, transformation_candidate):
    """Apply a specific transformation candidate"""
    trans_type = transformation_candidate['transition_type']
    
    if trans_type == 'privatize_resource':
        return _privatize_specific_resource(
            graph, 
            transformation_candidate['target_resource'],
            transformation_candidate['target_holders']
        )
    elif trans_type == 'add_mediator_pd':
        return _mediate_specific_resource(
            graph,
            transformation_candidate['target_resource'],
            transformation_candidate['target_sharers']
        )
    elif trans_type == 'remove_hold_edge':
        EdgeTransformations.remove_edge(
            graph, 
            transformation_candidate['target_from'],
            transformation_candidate['target_to'],
            EdgeType.HOLD
        )
        return True
    
    return False


def _privatize_specific_resource(graph, resource, holders):
    """Privatize a specific resource for specific holders"""
    _privatize_shared_resource(graph, resource, holders)
    return True


def _mediate_specific_resource(graph, resource, sharers):
    """Add mediation for a specific resource and sharers"""
    _add_mediator_between_pds(graph, resource, sharers)
    return True


# Legacy functions (replaced by smart selection) - kept for reference
# These are now replaced by the _find_*_candidates and _apply_specific_transformation functions


def _check_privatization_constraints(resource, holders, constraints):
    """Check if privatizing a resource violates any constraints"""
    for constraint in constraints:
        if constraint.constraint_type == "requires_resource":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string in holders and constraint.resource_info == "VMR":
                # PD still needs access to some VMR resource, privatization is OK
                return True
    return True  # No blocking constraints found


def _check_mediation_constraints(resource, sharers, constraints):
    """Check if adding mediation violates any constraints"""
    # Generally safe as long as PDs can still access resources through mediator
    return True


def _can_remove_hold_edge(from_node, to_node, constraints):
    """Check if removing a HOLD edge violates constraints"""
    for constraint in constraints:
        if constraint.constraint_type == "requires_resource":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string == from_node and constraint.resource_info == "VMR" and to_node.startswith('VMR_'):
                # This edge is required by constraint, cannot remove
                return False
    return True


def _privatize_shared_resource(graph, shared_resource, holders):
    """Create private copies of a shared resource for each holder"""
    # Get the original resource's properties
    original_data = graph.g.nodes[shared_resource]
    
    # Find which space this resource belongs to
    resource_space = None
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if from_node == shared_resource and edge_data.get('type') == 'SUBSET':
            resource_space = to_node
            break
    
    if resource_space:
        space_id = int(resource_space.split('_')[-1])
        
        # Create private resource for each holder (except the first, reuse original)
        for i, holder in enumerate(holders[1:], 1):
            # Create new private resource
            import json
            extra_data = json.loads(original_data.get('extra', '{}'))
            new_vmr = NodeTransformations.add_vmr_resource(
                graph, space_id, VmrType.HEAP, 
                int(extra_data.get('num_pages', 10)), 
                int(extra_data.get('va', '0x1000'), 16) + i * 0x1000
            )
            
            # Find the holder's hold edge and redirect it to new resource
            new_resource_id = f"VMR_{space_id}_{new_vmr}"
            
            # Remove old hold edge
            EdgeTransformations.remove_edge(graph, holder, shared_resource, EdgeType.HOLD)
            
            # Add new hold edge to private resource
            EdgeTransformations.add_hold_edge(graph, Permission.R, 
                                            int(holder.split('_')[1]), ResourceType.VMR, 
                                            space_id, new_vmr)


def _add_mediator_between_pds(graph, shared_resource, sharers):
    """Add a mediator PD between two PDs sharing a resource"""
    # Create mediator PD
    mediator_id = NodeTransformations.add_pd_node(graph, "mediator")
    
    # Remove direct access from both sharers
    for sharer in sharers:
        EdgeTransformations.remove_edge(graph, sharer, shared_resource, EdgeType.HOLD)
    
    # Add mediator access to resource
    space_id = 1  # Assume VMR_SPACE_1 for now
    resource_num = int(shared_resource.split('_')[-1])
    EdgeTransformations.add_hold_edge(graph, Permission.R | Permission.W, 
                                    mediator_id, ResourceType.VMR, space_id, resource_num)
    
    # Add REQUEST edges from original sharers to mediator
    for sharer in sharers:
        sharer_id = int(sharer.split('_')[1])
        EdgeTransformations.add_request_edge(graph, sharer_id, mediator_id, 
                                           ResourceType.VMR, space_id)


def DesignSpaceExploration():
    """
    Main IsoSearch algorithm for exploring design space
    Returns: list of explored mechanisms
    """
    # Step 1: Initialize components (from pseudocode line 2)
    goals, constraints, transitions, curGraph = Init()
    
    # Initialize the list to store discovered mechanisms
    explored_mechanisms = []
    
    print(f"Starting exploration with {len(goals)} goals, {len(constraints)} constraints, {len(transitions)} transitions")
    
    # Show initial graph structure
    print(f"\n📊 Initial graph:")
    _print_graph_arrows(curGraph)
    
    # Step 2: Main exploration loop (from pseudocode line 8)
    maxIterations = 5  # Keep it small for testing
    
    for i in range(1, maxIterations + 1):
        print(f"Iteration {i}/{maxIterations}")
        
        # Step 3: Generate candidate (from pseudocode line 9-10)
        candidate = GenerateCandidate(curGraph, constraints, transitions, goals)
        
        # Step 4: Break if no candidate found (from pseudocode line 12-13)
        if candidate is None:
            print("  No valid candidate found, stopping exploration")
            break
        
        # Step 5: Compute metrics (from pseudocode line 15)
        metrics = ComputeMetrics(candidate)
        print(f"  Metrics: {metrics}")
        
        # Step 6: Check if goals are met (from pseudocode line 16)
        if GoalsMet(metrics, goals):
            # Step 7: Save the mechanism (from pseudocode line 17-18)
            new_mechanism = (candidate, metrics)
            explored_mechanisms.append(new_mechanism)
            print(f"  ✅ Mechanism saved! Total mechanisms found: {len(explored_mechanisms)}")
        else:
            # Explain why goals were not met
            print(f"  ❌ Goals not met - continuing search")
            _explain_goal_failures(candidate, metrics, goals)
        
        # Step 8: Update current graph for next iteration (from pseudocode line 19)
        curGraph = candidate
        
        # Step 9: Show graph structure after this iteration
        print(f"\n📊 Graph after iteration {i}:")
        _print_graph_arrows(curGraph)
        
    print("Exploration complete!")
    print(f"\n🏁 Final graph:")
    _print_graph_arrows(curGraph)
    return explored_mechanisms


def _print_graph_arrows(graph):
    """Print ASCII art using arrow notation like PD_1 -> VMR_SPACE_1 -> VMR_1_1"""
    
    # Build paths from PDs through their relationships
    pd_nodes = [node for node, data in graph.g.nodes(data=True) 
                if data.get('type') == 'PD']
    pd_nodes.sort()
    
    print("        # Graph structure:")
    
    if not pd_nodes:
        print("        # (no PDs)")
        return
    
    for pd_node in pd_nodes:
        paths = _build_paths_from_pd(graph, pd_node)
        if paths:
            for path in paths:
                print(f"        # {path}")
        else:
            print(f"        # {pd_node} (isolated)")
    
    # Show shared resources if any
    shared_resources = _find_shared_resources(graph)
    if shared_resources:
        print("        #")
        for resource, sharers in shared_resources.items():
            if len(sharers) > 1:
                sharer_list = ", ".join(sharers)
                print(f"        # {resource} shared by: {sharer_list}")
    
    print()


def _build_paths_from_pd(graph, pd_node):
    """Build all paths starting from a PD node"""
    paths = []
    
    # Find all outgoing edges from this PD
    outgoing_edges = [(to_node, edge_data) for from_node, to_node, edge_data 
                      in graph.g.edges(data=True) if from_node == pd_node]
    
    if not outgoing_edges:
        return [pd_node]
    
    for to_node, edge_data in outgoing_edges:
        edge_type = edge_data.get('type', 'UNKNOWN')
        
        if edge_type == 'HOLD':
            # Follow HOLD edges to resources
            path = f"{pd_node} --HOLD--> {to_node}"
            
            # Continue following edges from the resource
            extended_path = _extend_path_from_resource(graph, to_node, path)
            paths.append(extended_path)
            
        elif edge_type == 'REQUEST':
            # Show REQUEST edges to other PDs
            path = f"{pd_node} --REQUEST--> {to_node}"
            paths.append(path)
            
        else:
            # Other edge types
            path = f"{pd_node} --{edge_type}--> {to_node}"
            paths.append(path)
    
    return paths


def _extend_path_from_resource(graph, resource_node, current_path):
    """Extend path by following edges from a resource"""
    
    # Find outgoing edges from this resource
    outgoing_edges = [(to_node, edge_data) for from_node, to_node, edge_data 
                      in graph.g.edges(data=True) if from_node == resource_node]
    
    if not outgoing_edges:
        return current_path
    
    # Follow the first meaningful edge (SUBSET to space, MAP to other resources)
    for to_node, edge_data in outgoing_edges:
        edge_type = edge_data.get('type', 'UNKNOWN')
        
        if edge_type == 'SUBSET':
            # Resource belongs to a space
            return f"{current_path} -> {to_node}"
        elif edge_type == 'MAP':
            # Resource maps to another resource
            return f"{current_path} -> {to_node}"
    
    return current_path


def _find_shared_resources(graph):
    """Find resources that are accessed by multiple PDs"""
    resource_access = {}
    
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_access:
                resource_access[to_node] = []
            resource_access[to_node].append(from_node)
    
    return resource_access


def _explain_goal_failures(graph, metrics, goals):
    """Explain why goals were not met by analyzing the current graph state"""
    
    print("    📋 Goal Analysis:")
    
    for goal in goals:
        metric_value = metrics.get(goal.metric_name, 'N/A')
        target = goal.target_value
        direction = goal.direction
        
        # Handle RSI map format
        if goal.metric_name == "RSI" and isinstance(metric_value, dict):
            print(f"    • RSI by resource type:")
            any_failed = False
            for resource_type, rsi_value in metric_value.items():
                if direction == "minimize":
                    if rsi_value > target:
                        print(f"      - {resource_type}: {rsi_value:.3f} > {target} ❌ (need to reduce by {rsi_value - target:.3f})")
                        any_failed = True
                    else:
                        print(f"      - {resource_type}: {rsi_value:.3f} ≤ {target} ✅")
                elif direction == "maximize":
                    if rsi_value < target:
                        print(f"      - {resource_type}: {rsi_value:.3f} < {target} ❌ (need to increase by {target - rsi_value:.3f})")
                        any_failed = True
                    else:
                        print(f"      - {resource_type}: {rsi_value:.3f} ≥ {target} ✅")
            
            if any_failed:
                _suggest_improvements(graph, goal.metric_name, metric_value, target)
        
        # Handle TCB map format (per-PD authority and sharing lists)
        elif goal.metric_name == "TCB" and isinstance(metric_value, dict):
            print(f"    • TCB by PD (authority + resource sharing dependencies):")
            any_failed = False
            for pd, tcb_list in metric_value.items():
                tcb_count = len(tcb_list)
                dependencies = ", ".join(tcb_list) if tcb_list else "none"
                
                if direction == "minimize":
                    if tcb_count > target:
                        print(f"      - {pd}: {tcb_count} > {target} ❌ (dependencies: {dependencies})")
                        any_failed = True
                    else:
                        print(f"      - {pd}: {tcb_count} ≤ {target} ✅ (dependencies: {dependencies})")
                elif direction == "maximize":
                    if tcb_count < target:
                        print(f"      - {pd}: {tcb_count} < {target} ❌ (dependencies: {dependencies})")
                        any_failed = True
                    else:
                        print(f"      - {pd}: {tcb_count} ≥ {target} ✅ (dependencies: {dependencies})")
            
            if any_failed:
                _suggest_improvements(graph, goal.metric_name, metric_value, target)
        else:
            # Handle scalar metrics
            if direction == "minimize":
                if metric_value > target:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} > {target} (need to reduce by {metric_value - target:.3f})")
                    _suggest_improvements(graph, goal.metric_name, metric_value, target)
                else:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} ≤ {target} ✅")
            elif direction == "maximize":
                if metric_value < target:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} < {target} (need to increase by {target - metric_value:.3f})")
                    _suggest_improvements(graph, goal.metric_name, metric_value, target)
                else:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} ≥ {target} ✅")
    
    print("    📊 Current graph:")
    _print_graph_arrows(graph)


def _suggest_improvements(graph, metric_name, current_value, target_value):
    """Suggest what transformations might improve the metric"""
    
    if metric_name == "RSI":
        # Analyze resource sharing for RSI improvements
        shared_resources = _find_shared_resources(graph)
        sharing_count = sum(1 for resource, sharers in shared_resources.items() if len(sharers) > 1)
        
        if sharing_count > 0:
            print(f"      → {sharing_count} shared resource(s) detected - consider privatization")
        else:
            print(f"      → No shared resources found - RSI should be 0.0")
    
    elif metric_name == "ASR":
        # Analyze attack surface paths
        hold_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'HOLD')
        request_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'REQUEST')
        map_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'MAP')
        total_attack_edges = hold_edges + request_edges + map_edges
        
        if total_attack_edges > 0:
            print(f"      → {total_attack_edges} attack surface edge(s) - consider edge removal or isolation")
        else:
            print(f"      → No attack surface edges found")
    
    elif metric_name == "TCB":
        # Analyze trusted computing base size (authority-based)
        pd_nodes = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']
        authority_pds = 0
        
        for pd_node in pd_nodes:
            has_authority = False
            
            # Check for direct authority relationships
            for f, t, d in graph.g.edges(data=True):
                if f == pd_node and t.startswith('PD_'):
                    if d.get('type') in ['REQUEST', 'AUTHORITY', 'CONTROL']:
                        has_authority = True
                        break
                
                # Check for indirect authority via REQUEST edges targeting this PD
                if d.get('type') == 'REQUEST' and t == pd_node and f.startswith('PD_'):
                    has_authority = True
                    break
            
            if has_authority:
                authority_pds += 1
        
        if authority_pds > 0:
            print(f"      → {authority_pds} PD(s) with authority relationships - consider authority delegation")
        else:
            print(f"      → No authority relationships found")
    


def Init():
    """
    Initialize the design space exploration components
    Returns: goals, constraints, transitions, curGraph
    """
    # Create multiple goals including per-PD authority-based TCB
    goals = [
        Goal("RSI", 0.3, "minimize"),
        Goal("TCB", 0, "minimize")  # Per-PD TCB: minimize authority over each PD
    ]
    
    # Create a simple example constraint: PD1 must have access to VMR
    constraints = [Constraint("requires_resource", 1, "VMR")] 
    
    # Create a simple list of allowed transitions
    transitions = [
        Transition("privatize_resource", "Make a shared resource private"),
        Transition("add_mediator_pd", "Add a PD between two communicating PDs"),
        Transition("remove_hold_edge", "Remove a hold relationship")
    ]
    
    # Create a basic starting graph with 2 PDs and some resources
    curGraph = ModelGraph()
    
    # Add two protection domains
    pd1 = NodeTransformations.add_pd_node(curGraph, "user_process")
    pd2 = NodeTransformations.add_pd_node(curGraph, "database_server")
    
    # Add a VMR space and resource
    vmr_space = NodeTransformations.add_resource_space(curGraph, ResourceType.VMR)
    vmr_resource = NodeTransformations.add_vmr_resource(curGraph, vmr_space, VmrType.HEAP, 10, 0x1000)
    
    # Create scenario with both authority and resource sharing for comprehensive TCB testing
    
    # Add another VMR resource that will be shared
    shared_vmr = NodeTransformations.add_vmr_resource(curGraph, vmr_space, VmrType.STACK, 5, 0x2000)
    
    # PD1 and PD2 both hold the shared resource (resource sharing dependency)
    EdgeTransformations.add_hold_edge(curGraph, Permission.R, pd1, ResourceType.VMR, vmr_space, shared_vmr)
    EdgeTransformations.add_hold_edge(curGraph, Permission.R, pd2, ResourceType.VMR, vmr_space, shared_vmr)
    
    # Add a mediator PD to create authority relationships
    mediator_pd = NodeTransformations.add_pd_node(curGraph, "mediator")
    
    # Mediator holds the first resource
    EdgeTransformations.add_hold_edge(curGraph, Permission.R, mediator_pd, ResourceType.VMR, vmr_space, vmr_resource)
    
    # PD1 requests access through mediator (authority relationship)
    EdgeTransformations.add_request_edge(curGraph, pd1, mediator_pd, ResourceType.VMR, vmr_space)
    
    return goals, constraints, transitions, curGraph


if __name__ == "__main__":
    # Test the complete Init() function
    goals, constraints, transitions, curGraph = Init()
    
    print("=== Initialization Complete ===")
    print(f"Goals ({len(goals)}): {[str(g) for g in goals]}")
    print(f"Constraints ({len(constraints)}): {[str(c) for c in constraints]}")
    print(f"Transitions ({len(transitions)}): {[str(t) for t in transitions]}")
    print(f"Current Graph: {curGraph.g.number_of_nodes()} nodes, {curGraph.g.number_of_edges()} edges")
    
    print("\n=== Graph Details ===")
    for node, data in curGraph.g.nodes(data=True):
        print(f"Node: {node} -> {data}")
    
    print("\n=== Ready for IsoSearch! ===")
    
    # Test the DesignSpaceExploration skeleton
    print("\n=== Testing DesignSpaceExploration() ===")
    result = DesignSpaceExploration()
    print(f"Exploration result: {result}")