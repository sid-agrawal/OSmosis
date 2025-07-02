"""
IsoSearch Algorithm Implementation - Baby Steps
"""

# Import our graph transformation capabilities
from graph_transformations import NodeTransformations, EdgeTransformations
from generic_model import ModelGraph, ResourceType, VmrType, FileType, Permission, EdgeType
from scenarios import get_scenario, list_scenarios, SCENARIOS, Goal, Constraint, Transition
from visualization import IsoSearchVisualizer
from decision_tree_viz import DecisionTreeVisualizer

# Goal, Constraint, and Transition classes are now imported from scenarios.py


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
    
    # Calculate RSI (Resource Sharing Index) as per PD pair metric
    metrics['RSI'] = _calculate_rsi_per_pd_pair(candidate, pd_nodes)
    
    # Calculate ASR (Attack Surface Ratio) - attack paths per PD
    metrics['ASR'] = _calculate_asr(candidate, pd_nodes)
    
    # Calculate TCB (Trusted Computing Base) size
    metrics['TCB'] = _calculate_tcb(candidate, pd_nodes)
    
    # Calculate FR (Fault Radius) - distance to common ancestor via REQUEST edges
    metrics['FR'] = _calculate_fr(candidate, pd_nodes)
    
    print(f"    RSI: {metrics['RSI']}, ASR: {metrics['ASR']}, TCB: {metrics['TCB']}, FR: {metrics['FR']}")
    return metrics


def _calculate_rsi_per_pd_pair(graph, pd_nodes):
    """Calculate RSI (Resource Sharing Index) as per PD pair metric
    
    RSI[PD_i, PD_j] = (Resources shared by PD_i and PD_j) / (Total resources accessed by either PD_i or PD_j)
    
    Returns a dictionary mapping PD pairs to their RSI values
    """
    # Build resource access map: PD -> set of resources
    pd_resources = {}
    for pd in pd_nodes:
        pd_resources[pd] = set()
    
    # Find all HOLD edges from PDs to resources
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if from_node in pd_resources:
                pd_resources[from_node].add(to_node)
    
    # Calculate RSI for each PD pair
    rsi_pairs = {}
    
    for i, pd_i in enumerate(pd_nodes):
        for j, pd_j in enumerate(pd_nodes):
            if i < j:  # Only calculate for unique pairs (avoid duplicates)
                pair_key = f"{pd_i},{pd_j}"
                
                resources_i = pd_resources[pd_i]
                resources_j = pd_resources[pd_j]
                
                # Resources shared by both PDs
                shared_resources = resources_i.intersection(resources_j)
                
                # Total resources accessed by either PD
                total_resources = resources_i.union(resources_j)
                
                # Calculate RSI for this pair
                if len(total_resources) > 0:
                    rsi_pairs[pair_key] = len(shared_resources) / len(total_resources)
                else:
                    rsi_pairs[pair_key] = 0.0
    
    return rsi_pairs


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
        if 'FILE' in resource_node:
            return 'FILE'
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


def _calculate_fr(graph, pd_nodes):
    """Calculate FR (Fault Radius) - distance to common ancestor for PD pairs via REQUEST edges"""
    
    # Build REQUEST edge graph (authority relationships)
    request_graph = {}
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'REQUEST' and from_node.startswith('PD_') and to_node.startswith('PD_'):
            if from_node not in request_graph:
                request_graph[from_node] = []
            request_graph[from_node].append(to_node)
    
    # Calculate fault radius for each PD pair
    fr_by_pair = {}
    
    for i in range(len(pd_nodes)):
        for j in range(i + 1, len(pd_nodes)):
            pd1 = pd_nodes[i]
            pd2 = pd_nodes[j]
            pair_key = f"{pd1},{pd2}"
            
            # Find common ancestor and calculate distance
            distance = _find_common_ancestor_distance(pd1, pd2, request_graph)
            fr_by_pair[pair_key] = distance
    
    return fr_by_pair


def _find_common_ancestor_distance(pd1, pd2, request_graph):
    """Find distance to common ancestor between two PDs via REQUEST edges"""
    
    # Get all ancestors for each PD with their distances
    ancestors1 = _get_ancestors_with_distance(pd1, request_graph)
    ancestors2 = _get_ancestors_with_distance(pd2, request_graph)
    
    # Find common ancestors and their total distances
    min_distance = float('inf')
    
    for ancestor in ancestors1:
        if ancestor in ancestors2:
            # Total distance = distance from pd1 to ancestor + distance from pd2 to ancestor
            total_distance = ancestors1[ancestor] + ancestors2[ancestor]
            min_distance = min(min_distance, total_distance)
    
    return min_distance


def _get_ancestors_with_distance(pd, request_graph):
    """Get all ancestors of a PD with their distances via REQUEST edges"""
    ancestors = {}
    visited = set()
    queue = [(pd, 0)]  # (node, distance)
    
    while queue:
        current_pd, distance = queue.pop(0)
        
        if current_pd in visited:
            continue
        visited.add(current_pd)
        
        # Add current node as ancestor (except for the starting PD itself)
        if distance > 0:
            ancestors[current_pd] = distance
        
        # Follow REQUEST edges to find more ancestors
        if current_pd in request_graph:
            for parent in request_graph[current_pd]:
                if parent not in visited:
                    queue.append((parent, distance + 1))
    
    return ancestors




def GoalsMet(metrics, goals):
    """
    Check if the computed metrics meet the specified goals
    Supports targeted goals: TCB for specific PD, RSI/FR for specific PD pairs, ASR system-wide
    Returns: boolean indicating if all goals are satisfied
    """
    for goal in goals:
        metric_value = metrics.get(goal.metric_name)
        if metric_value is None:
            print(f"    Warning: Metric {goal.metric_name} not found in results")
            return False
        
        # Handle targeted goals
        if goal.target_spec:
            if goal.metric_name == "TCB" and isinstance(metric_value, dict):
                # TCB goal for specific PD
                target_pd = goal.target_spec
                if target_pd not in metric_value:
                    print(f"    Warning: PD {target_pd} not found in TCB metrics")
                    return False
                
                tcb_list = metric_value[target_pd]
                tcb_count = len(tcb_list)
                
                if goal.direction == "minimize":
                    if tcb_count > goal.target_value:
                        dependencies = ", ".join(tcb_list) if tcb_list else "none"
                        print(f"    Goal not met: TCB[{target_pd}]={tcb_count} > {goal.target_value} (dependencies: {dependencies})")
                        return False
                elif goal.direction == "maximize":
                    if tcb_count < goal.target_value:
                        dependencies = ", ".join(tcb_list) if tcb_list else "none"
                        print(f"    Goal not met: TCB[{target_pd}]={tcb_count} < {goal.target_value} (dependencies: {dependencies})")
                        return False
                        
            elif goal.metric_name in ["RSI", "FR"] and isinstance(metric_value, dict):
                # RSI or FR goal for specific PD pair
                target_pair = goal.target_spec
                if target_pair not in metric_value:
                    print(f"    Warning: PD pair {target_pair} not found in {goal.metric_name} metrics")
                    return False
                
                pair_value = metric_value[target_pair]
                
                if goal.direction == "minimize":
                    if pair_value > goal.target_value:
                        value_str = "infinity" if pair_value == float('inf') else f"{pair_value:.3f}"
                        print(f"    Goal not met: {goal.metric_name}[{target_pair}]={value_str} > {goal.target_value}")
                        return False
                elif goal.direction == "maximize":
                    if pair_value < goal.target_value:
                        value_str = "infinity" if pair_value == float('inf') else f"{pair_value:.3f}"
                        print(f"    Goal not met: {goal.metric_name}[{target_pair}]={value_str} < {goal.target_value}")
                        return False
            else:
                print(f"    Warning: Targeted goal for {goal.metric_name} not supported or metric format unexpected")
                return False
        
        # Handle non-targeted goals (system-wide)
        else:
            if goal.metric_name == "ASR":
                # ASR is system-wide scalar metric
                if goal.direction == "minimize":
                    if metric_value > goal.target_value:
                        print(f"    Goal not met: {goal.metric_name}={metric_value:.3f} > {goal.target_value}")
                        return False
                elif goal.direction == "maximize":
                    if metric_value < goal.target_value:
                        print(f"    Goal not met: {goal.metric_name}={metric_value:.3f} < {goal.target_value}")
                        return False
            
            elif goal.metric_name in ["RSI", "TCB", "FR"] and isinstance(metric_value, dict):
                # Non-targeted goals for dictionary metrics check all entries
                goal_violated = False
                for key, value in metric_value.items():
                    if goal.metric_name == "TCB":
                        check_value = len(value)  # TCB uses length of dependency list
                    else:
                        check_value = value  # RSI and FR use the value directly
                    
                    if goal.direction == "minimize":
                        if check_value > goal.target_value:
                            if goal.metric_name == "TCB":
                                dependencies = ", ".join(value) if value else "none"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={check_value} > {goal.target_value} (dependencies: {dependencies})")
                            else:
                                value_str = "infinity" if check_value == float('inf') else f"{check_value:.3f}"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={value_str} > {goal.target_value}")
                            goal_violated = True
                    elif goal.direction == "maximize":
                        if check_value < goal.target_value:
                            if goal.metric_name == "TCB":
                                dependencies = ", ".join(value) if value else "none"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={check_value} < {goal.target_value} (dependencies: {dependencies})")
                            else:
                                value_str = "infinity" if check_value == float('inf') else f"{check_value:.3f}"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={value_str} < {goal.target_value}")
                            goal_violated = True
                
                if goal_violated:
                    return False
            else:
                # Handle other scalar metrics
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
    Returns: tuple of (new graph or None, candidate_info dict)
    """
    import copy
    
    # Get all possible transformations with their predicted impact
    transformation_candidates = []
    
    for transition in transitions:
        # Use new transition system's find_candidates method
        candidates = transition.find_candidates(graph, constraints)
        # Add predicted improvement and other metadata
        for candidate in candidates:
            candidate['transition_name'] = transition.name
            candidate['transition_type'] = transition.transition_type
            candidate['predicted_improvement'] = _predict_improvement(transition, candidate, graph, goals)
        transformation_candidates.extend(candidates)
    
    # Prepare candidate info for tracking
    candidate_info = {
        'all_candidates': transformation_candidates.copy(),
        'selected_candidate': None,
        'discarded_candidates': [],
        'success': False
    }
    
    if not transformation_candidates:
        print("  No valid transitions found")
        return None, candidate_info
    
    # Prioritize constraint-relevant candidates (Strategy 3)
    def candidate_priority(candidate):
        base_improvement = candidate['predicted_improvement']
        constraint_relevance = candidate.get('constraint_relevance', 0.1)
        addresses_violation = candidate.get('addresses_violation', False)
        
        # Boost priority for constraint-addressing candidates
        if addresses_violation:
            return base_improvement + constraint_relevance + 0.5
        return base_improvement
    
    transformation_candidates.sort(key=candidate_priority, reverse=True)
    
    # Try the best transformation candidate
    best_candidate = transformation_candidates[0]
    candidate_info['selected_candidate'] = best_candidate
    candidate_info['discarded_candidates'] = transformation_candidates[1:]  # All except the best
    
    candidate_graph = copy.deepcopy(graph)
    
    print(f"  Trying best transition: {best_candidate['transition_type']}")
    print(f"    Target: {best_candidate['target_description']}")
    print(f"    Predicted improvement: {best_candidate['predicted_improvement']:.3f}")
    
    # Show discarded options if there are any
    if len(candidate_info['discarded_candidates']) > 0:
        print(f"    Considered {len(candidate_info['discarded_candidates'])} other option(s):")
        for i, discarded in enumerate(candidate_info['discarded_candidates'][:3], 1):  # Show top 3 discarded
            print(f"      {i}. {discarded['transition_type']}: {discarded['target_description']} (improvement: {discarded['predicted_improvement']:.3f})")
        if len(candidate_info['discarded_candidates']) > 3:
            print(f"      ... and {len(candidate_info['discarded_candidates']) - 3} more")
    
    # Apply transformation using new transition system
    try:
        # Find the transition object
        transition = None
        for t in transitions:
            if t.name == best_candidate['transition_name']:
                transition = t
                break
        
        if transition is None:
            print(f"    ❌ Transition {best_candidate['transition_name']} not found")
            return None, candidate_info
        
        # Apply the transition with the candidate's parameter values
        success = transition.apply(candidate_graph, best_candidate.get('param_values', {}))
        candidate_info['success'] = success
        
        if success:
            print(f"    ✅ Applied {best_candidate['transition_name']}")
            return candidate_graph, candidate_info
        else:
            print(f"    ❌ Failed to apply {best_candidate['transition_name']}")
            return None, candidate_info
    except Exception as e:
        print(f"    ❌ Error applying {best_candidate.get('transition_name', 'unknown')}: {e}")
        candidate_info['success'] = False
        return None, candidate_info


def _predict_improvement(transition, candidate, graph, goals):
    """
    Predict the improvement a transformation will have on the goals
    Returns: float representing predicted improvement (higher = better)
    """
    # Basic improvement prediction based on transition type
    improvement_map = {
        # Multi-step transitions
        "privatize_resource": 1.0,  # High impact on RSI
        "add_mediator": 0.5,        # Medium impact on security
        
        # High-impact primitives (problem-solving)
        "remove_file_resource": 0.6,    # Can eliminate shared resources
        "add_file_resource": 0.5,       # Can create private files to solve sharing
        "remove_hold_edge": 0.5,       # Can disconnect from shared resources
        "add_hold_edge": 0.4,          # Can connect PDs to new private resources
        
        # Medium-impact primitives (structural)
        "remove_pd": 0.3,              # Can remove unnecessary components
        "add_subset_edge": 0.3,        # Can connect resources to spaces
        "remove_subset_edge": 0.3,     # Can disconnect resources from spaces
        "add_request_edge": 0.2,       # Can add authority relationships
        "remove_request_edge": 0.3,    # Can remove authority relationships
        
        # Low-impact primitives (infrastructure)
        "add_pd": 0.2,                 # Lower priority - doesn't solve sharing directly
        "add_resource_space": 0.1,     # Infrastructure operation
        "remove_resource_space": 0.2   # Cleanup operation
    }
    
    base_improvement = improvement_map.get(transition.name, 0.3)
    
    # Could add goal-specific adjustments here
    # For now, return base improvement
    return base_improvement


def _find_transformation_candidates(graph, transition, constraints, goals):
    """
    Legacy function - replaced by new transition system
    """
    # This function is no longer used with the new transition system
    return []


def _find_privatization_candidates(graph, constraints, goals):
    """Find all shared resources that could be privatized and estimate RSI improvement"""
    candidates = []
    resource_holders = {}
    
    # Find all shared resources
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_'):
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
        if constraint.constraint_type == "requires_file_access":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string in holders and resource.startswith('FILE_'):
                # Check if the PD's FILE access requirements are still met after privatization
                file_type = constraint.properties.get('file_type', 'any')
                if file_type == 'any' or file_type.upper() in resource:
                    continue  # Requirement is satisfied
                else:
                    return False  # FILE type requirement not met
        elif constraint.constraint_type == "requires_communication":
            # Communication constraints are not affected by resource privatization
            continue
    return True  # No blocking constraints found


def _check_mediation_constraints(resource, sharers, constraints):
    """Check if adding mediation violates any constraints"""
    for constraint in constraints:
        if constraint.constraint_type == "requires_file_access":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string in sharers and resource.startswith('FILE_'):
                # Check if mediated access still meets FILE requirements
                file_type = constraint.properties.get('file_type', 'any')
                permissions = constraint.properties.get('permissions', 'R')
                # Mediation might restrict permissions, check if still compatible
                if 'W' in permissions and resource.startswith('FILE_'):
                    # Write access through mediator might be problematic for some FILE types
                    if file_type == 'LOG':
                        return False  # Log files need direct write access
        elif constraint.constraint_type == "requires_communication":
            # Communication constraints not directly affected by resource mediation
            continue
    return True  # Mediation is acceptable


def _can_remove_hold_edge(from_node, to_node, constraints):
    """Check if removing a HOLD edge violates constraints"""
    for constraint in constraints:
        if constraint.constraint_type == "requires_file_access":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string == from_node and to_node.startswith('FILE_'):
                # Check if this specific FILE is required by the constraint
                file_type = constraint.properties.get('file_type', 'any')
                if file_type == 'any' or file_type.upper() in to_node:
                    # This edge is required by constraint, cannot remove
                    return False
        elif constraint.constraint_type == "requires_communication":
            # Check if removing this edge affects required communication paths
            pd_string = f"PD_{constraint.pd_id}"
            target_pd_string = f"PD_{constraint.target_pd}"
            if pd_string == from_node and to_node == target_pd_string:
                # This is a direct communication edge required by constraint
                return False
            # Could also check for indirect communication paths through shared resources
            if (pd_string == from_node and to_node.startswith('FILE_') and 
                constraint.resource_info in ['REQUEST', 'REPLY']):
                # Removing access to communication FILE might break required communication
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
            new_file = NodeTransformations.add_file_resource(
                graph, space_id, FileType.CONFIG, 
                f"/etc/private_{holder.split('_')[1]}.conf", 
                int(extra_data.get('size_bytes', '1024'))
            )
            
            # Find the holder's hold edge and redirect it to new resource
            new_resource_id = f"FILE_{space_id}_{new_file}"
            
            # Remove old hold edge
            EdgeTransformations.remove_edge(graph, holder, shared_resource, EdgeType.HOLD)
            
            # Add new hold edge to private resource
            EdgeTransformations.add_hold_edge(graph, Permission.R, 
                                            int(holder.split('_')[1]), ResourceType.FILE, 
                                            space_id, new_file)


def _add_mediator_between_pds(graph, shared_resource, sharers):
    """Add a mediator PD between two PDs sharing a resource"""
    # Create mediator PD
    mediator_id = NodeTransformations.add_pd_node(graph, "mediator")
    
    # Remove direct access from both sharers
    for sharer in sharers:
        EdgeTransformations.remove_edge(graph, sharer, shared_resource, EdgeType.HOLD)
    
    # Add mediator access to resource
    space_id = 1  # Assume FILE_SPACE_1 for now
    resource_num = int(shared_resource.split('_')[-1])
    EdgeTransformations.add_hold_edge(graph, Permission.R | Permission.W, 
                                    mediator_id, ResourceType.FILE, space_id, resource_num)
    
    # Add REQUEST edges from original sharers to mediator
    for sharer in sharers:
        sharer_id = int(sharer.split('_')[1])
        EdgeTransformations.add_request_edge(graph, sharer_id, mediator_id, 
                                           ResourceType.FILE, space_id)


def DesignSpaceExplorationWithVisualization(scenario, visualizer=None, tree_visualizer=None):
    """
    Main IsoSearch algorithm for exploring design space with optional visualization
    Args: 
        scenario - Scenario object with goals, constraints, transitions, and graph builder
        visualizer - Optional IsoSearchVisualizer object for HTML generation
    Returns: list of explored mechanisms
    """
    # Step 1: Initialize components from scenario (from pseudocode line 2)
    goals = scenario.goals
    constraints = scenario.constraints
    transitions = scenario.get_allowed_transitions()  # Use new transition system
    curGraph = scenario.build_graph()
    
    # Initialize the list to store discovered mechanisms
    explored_mechanisms = []
    
    # Track all exploration decisions for summary
    exploration_summary = {
        'iterations': [],
        'total_candidates_considered': 0,
        'total_candidates_discarded': 0,
        'transformation_types_tried': set(),
        'transformation_types_discarded': set()
    }
    
    print(f"Starting exploration with {len(goals)} goals, {len(constraints)} constraints, {len(transitions)} transitions")
    
    # Show initial graph structure
    print(f"\n📊 Initial graph:")
    _print_graph_arrows(curGraph)
    
    # Add initial state to visualization
    if visualizer:
        initial_metrics = ComputeMetrics(curGraph)
        visualizer.add_iteration(0, curGraph, initial_metrics, [], None)
    
    if tree_visualizer:
        initial_metrics = ComputeMetrics(curGraph)
        tree_visualizer.add_decision_node(0, curGraph, initial_metrics, [])
    
    # Step 2: Main exploration loop (from pseudocode line 8)
    maxIterations = 5  # Keep it small for testing
    
    for i in range(1, maxIterations + 1):
        print(f"Iteration {i}/{maxIterations}")
        
        # Step 3: Generate candidate (from pseudocode line 9-10)
        candidate, candidate_info = GenerateCandidate(curGraph, constraints, transitions, goals)
        
        # Track exploration decisions
        iteration_info = {
            'iteration': i,
            'candidate_info': candidate_info,
            'goals_met': False,
            'mechanism_saved': False
        }
        
        # Update exploration statistics
        exploration_summary['total_candidates_considered'] += len(candidate_info['all_candidates'])
        exploration_summary['total_candidates_discarded'] += len(candidate_info['discarded_candidates'])
        
        # Track transformation types
        for candidate_data in candidate_info['all_candidates']:
            exploration_summary['transformation_types_discarded'].add(candidate_data['transition_type'])
        
        if candidate_info['selected_candidate']:
            exploration_summary['transformation_types_tried'].add(candidate_info['selected_candidate']['transition_type'])
        
        # Check if any valid candidate was found
        if candidate is None:
            print("  No valid candidate found, stopping exploration")
            iteration_info['candidate_info']['success'] = False
            exploration_summary['iterations'].append(iteration_info)
            break
        
        # Step 4: Compute metrics for the candidate (from pseudocode line 11)
        metrics = ComputeMetrics(candidate)
        
        # Step 5: Check if goals are met (from pseudocode line 12-16)
        goals_met = GoalsMet(metrics, goals)
        iteration_info['goals_met'] = goals_met
        
        if goals_met:
            print("    All {} goal(s) met!".format(len(goals)))
        else:
            print("    Goals not yet satisfied, continuing exploration")
        
        # Step 6: Save the mechanism (from pseudocode line 17)
        print("  ✅ Mechanism saved! Total mechanisms found: {}".format(len(explored_mechanisms) + 1))
        explored_mechanisms.append({
            'iteration': i,
            'graph': candidate,
            'metrics': metrics,
            'transformation': candidate_info['selected_candidate']['transition_type'] if candidate_info['selected_candidate'] else None,
            'goals_met': goals_met
        })
        iteration_info['mechanism_saved'] = True
        iteration_info['candidate_info']['success'] = True
        
        # Add iteration data to visualization
        if visualizer:
            visualizer.add_iteration(
                i, candidate, metrics, 
                candidate_info['all_candidates'], 
                candidate_info['selected_candidate']
            )
            
            # Add decision data
            if candidate_info['selected_candidate'] and candidate_info['discarded_candidates']:
                visualizer.add_decision(
                    i,
                    candidate_info['selected_candidate']['target_description'],
                    [c['target_description'] for c in candidate_info['discarded_candidates']],
                    f"Selected based on predicted improvement: {candidate_info['selected_candidate']['predicted_improvement']:.3f}"
                )
        
        # Add tree visualization data
        if tree_visualizer:
            # Add selected path
            tree_visualizer.add_decision_node(
                i, candidate, metrics, 
                candidate_info['all_candidates'],
                candidate_info['selected_candidate'],
                parent_id=f"iter_{i-1}_selected" if i > 1 else "root",
                is_selected=True
            )
            
            # Add discarded paths
            if candidate_info['discarded_candidates']:
                tree_visualizer.add_discarded_paths(
                    i, curGraph, candidate_info['discarded_candidates']
                )
        
        # Step 7: Update current graph (from pseudocode line 18)
        curGraph = candidate
        
        # Show graph structure after this iteration
        print(f"\n📊 Graph after iteration {i}:")
        _print_graph_arrows(curGraph)
        
        exploration_summary['iterations'].append(iteration_info)
        
        print()  # Add spacing between iterations
    
    print("Exploration complete!")
    
    # Show final graph structure
    print(f"\n🏁 Final graph:")
    _print_graph_arrows(curGraph)
    
    # Print comprehensive decision summary
    _print_exploration_summary(exploration_summary)
    
    return explored_mechanisms


def DesignSpaceExploration(scenario):
    """
    Main IsoSearch algorithm for exploring design space
    Args: scenario - Scenario object with goals, constraints, transitions, and graph builder
    Returns: list of explored mechanisms
    """
    # Step 1: Initialize components from scenario (from pseudocode line 2)
    goals = scenario.goals
    constraints = scenario.constraints
    transitions = scenario.get_allowed_transitions()  # Use new transition system
    curGraph = scenario.build_graph()
    
    # Initialize the list to store discovered mechanisms
    explored_mechanisms = []
    
    # Track all exploration decisions for summary
    exploration_summary = {
        'iterations': [],
        'total_candidates_considered': 0,
        'total_candidates_discarded': 0,
        'transformation_types_tried': set(),
        'transformation_types_discarded': set()
    }
    
    print(f"Starting exploration with {len(goals)} goals, {len(constraints)} constraints, {len(transitions)} transitions")
    
    # Show initial graph structure
    print(f"\n📊 Initial graph:")
    _print_graph_arrows(curGraph)
    
    # Step 2: Main exploration loop (from pseudocode line 8)
    maxIterations = 5  # Keep it small for testing
    
    for i in range(1, maxIterations + 1):
        print(f"Iteration {i}/{maxIterations}")
        
        # Step 3: Generate candidate (from pseudocode line 9-10)
        candidate, candidate_info = GenerateCandidate(curGraph, constraints, transitions, goals)
        
        # Track exploration decisions
        iteration_info = {
            'iteration': i,
            'candidate_info': candidate_info,
            'goals_met': False,
            'mechanism_saved': False
        }
        
        # Update summary statistics
        exploration_summary['total_candidates_considered'] += len(candidate_info['all_candidates'])
        exploration_summary['total_candidates_discarded'] += len(candidate_info['discarded_candidates'])
        
        if candidate_info['selected_candidate']:
            exploration_summary['transformation_types_tried'].add(candidate_info['selected_candidate']['transition_type'])
        
        for discarded in candidate_info['discarded_candidates']:
            exploration_summary['transformation_types_discarded'].add(discarded['transition_type'])
        
        # Step 4: Break if no candidate found (from pseudocode line 12-13)
        if candidate is None:
            print("  No valid candidate found, stopping exploration")
            exploration_summary['iterations'].append(iteration_info)
            break
        
        # Step 5: Compute metrics (from pseudocode line 15)
        metrics = ComputeMetrics(candidate)
        print(f"  Metrics: {metrics}")
        
        # Step 6: Check if goals are met (from pseudocode line 16)
        goals_met = GoalsMet(metrics, goals)
        iteration_info['goals_met'] = goals_met
        
        if goals_met:
            # Step 7: Save the mechanism (from pseudocode line 17-18)
            new_mechanism = (candidate, metrics)
            explored_mechanisms.append(new_mechanism)
            iteration_info['mechanism_saved'] = True
            print(f"  ✅ Mechanism saved! Total mechanisms found: {len(explored_mechanisms)}")
        else:
            # Explain why goals were not met
            print(f"  ❌ Goals not met - continuing search")
            _explain_goal_failures(candidate, metrics, goals)
        
        # Step 8: Update current graph for next iteration (from pseudocode line 19)
        curGraph = candidate
        
        # Add iteration info to summary
        exploration_summary['iterations'].append(iteration_info)
        
        # Step 9: Show graph structure after this iteration
        print(f"\n📊 Graph after iteration {i}:")
        _print_graph_arrows(curGraph)
        
    print("Exploration complete!")
    print(f"\n🏁 Final graph:")
    _print_graph_arrows(curGraph)
    
    # Print exploration summary
    _print_exploration_summary(exploration_summary)
    
    return explored_mechanisms


def _print_exploration_summary(summary):
    """Print a comprehensive summary of all options considered during exploration"""
    
    print(f"\n{'='*60}")
    print("📊 EXPLORATION DECISION SUMMARY")
    print(f"{'='*60}")
    
    # Overall statistics
    total_iterations = len(summary['iterations'])
    mechanisms_found = sum(1 for iter_info in summary['iterations'] if iter_info['mechanism_saved'])
    
    print(f"Total iterations completed: {total_iterations}")
    print(f"Total transformation candidates considered: {summary['total_candidates_considered']}")
    print(f"Total transformation candidates discarded: {summary['total_candidates_discarded']}")
    print(f"Mechanisms discovered: {mechanisms_found}")
    print(f"Success rate: {mechanisms_found / max(total_iterations, 1) * 100:.1f}%")
    
    # Transformation type analysis
    print(f"\n🔧 Transformation Types:")
    print(f"   Tried: {', '.join(sorted(summary['transformation_types_tried'])) if summary['transformation_types_tried'] else 'None'}")
    print(f"   Available but never selected: {', '.join(sorted(summary['transformation_types_discarded'] - summary['transformation_types_tried'])) if summary['transformation_types_discarded'] - summary['transformation_types_tried'] else 'None'}")
    
    # Detailed per-iteration breakdown
    print(f"\n📋 Per-Iteration Decision Breakdown:")
    
    for iter_info in summary['iterations']:
        iteration = iter_info['iteration']
        candidate_info = iter_info['candidate_info']
        goals_met = iter_info['goals_met']
        mechanism_saved = iter_info['mechanism_saved']
        
        print(f"\n  Iteration {iteration}:")
        
        if not candidate_info['all_candidates']:
            print(f"    ❌ No transformation candidates found")
            continue
            
        selected = candidate_info['selected_candidate']
        discarded = candidate_info['discarded_candidates']
        
        if selected:
            status = "✅ SUCCESS" if candidate_info['success'] else "❌ FAILED"
            goal_status = "🎯 GOALS MET" if goals_met else "🔄 CONTINUING"
            print(f"    {status} Selected: {selected['transition_type']}")
            print(f"      Target: {selected['target_description']}")
            print(f"      Predicted improvement: {selected['predicted_improvement']:.3f}")
            print(f"      Result: {goal_status}")
        
        if discarded:
            print(f"    🗂️  Discarded {len(discarded)} alternatives:")
            for i, option in enumerate(discarded[:5], 1):  # Show top 5 discarded
                print(f"      {i}. {option['transition_type']}: {option['target_description']} (improvement: {option['predicted_improvement']:.3f})")
            if len(discarded) > 5:
                print(f"      ... and {len(discarded) - 5} more")
    
    # Analysis of decision patterns
    print(f"\n🔍 Decision Pattern Analysis:")
    
    # Most frequently selected transformation types
    selected_types = []
    for iter_info in summary['iterations']:
        if iter_info['candidate_info']['selected_candidate']:
            selected_types.append(iter_info['candidate_info']['selected_candidate']['transition_type'])
    
    if selected_types:
        from collections import Counter
        type_counts = Counter(selected_types)
        print(f"   Most frequently selected:")
        for trans_type, count in type_counts.most_common():
            print(f"     - {trans_type}: {count} time(s)")
    
    # Average improvement scores
    all_improvements = []
    selected_improvements = []
    discarded_improvements = []
    
    for iter_info in summary['iterations']:
        candidate_info = iter_info['candidate_info']
        for candidate in candidate_info['all_candidates']:
            all_improvements.append(candidate['predicted_improvement'])
        
        if candidate_info['selected_candidate']:
            selected_improvements.append(candidate_info['selected_candidate']['predicted_improvement'])
        
        for discarded in candidate_info['discarded_candidates']:
            discarded_improvements.append(discarded['predicted_improvement'])
    
    if all_improvements:
        print(f"   Average predicted improvement:")
        print(f"     - All candidates: {sum(all_improvements) / len(all_improvements):.3f}")
        if selected_improvements:
            print(f"     - Selected candidates: {sum(selected_improvements) / len(selected_improvements):.3f}")
        if discarded_improvements:
            print(f"     - Discarded candidates: {sum(discarded_improvements) / len(discarded_improvements):.3f}")
    
    print(f"\n{'='*60}")


def _print_graph_arrows(graph):
    """Print ASCII art using arrow notation like PD_1 -> FILE_SPACE_1 -> FILE_1_1"""
    
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
        
        # Handle FR map format (distance between PD pairs)
        elif goal.metric_name == "FR" and isinstance(metric_value, dict):
            print(f"    • FR by PD pair (fault radius via REQUEST edges):")
            any_failed = False
            for pair, fr_distance in metric_value.items():
                distance_str = "infinity" if fr_distance == float('inf') else f"{fr_distance:.1f}"
                
                if direction == "minimize":
                    if fr_distance > target:
                        print(f"      - {pair}: {distance_str} > {target} ❌")
                        any_failed = True
                    else:
                        print(f"      - {pair}: {distance_str} ≤ {target} ✅")
                elif direction == "maximize":
                    if fr_distance < target:
                        print(f"      - {pair}: {distance_str} < {target} ❌")
                        any_failed = True
                    else:
                        print(f"      - {pair}: {distance_str} ≥ {target} ✅")
            
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
    
    elif metric_name == "FR":
        # Analyze fault radius improvements
        request_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'REQUEST')
        
        if request_edges > 0:
            print(f"      → {request_edges} REQUEST edge(s) found - consider adding REQUEST edges for shorter fault radius")
        else:
            print(f"      → No REQUEST edges found - consider adding authority relationships for fault isolation")
    


def run_scenario(scenario_name, enable_visualization=False):
    """
    Run IsoSearch exploration on a specific scenario
    Args: 
        scenario_name - name of the scenario to run
        enable_visualization - if True, generates HTML visualization
    Returns: list of discovered mechanisms
    """
    try:
        scenario = get_scenario(scenario_name)
        print(f"🎯 Running scenario: {scenario.name}")
        print(f"   Description: {scenario.description}")
        print(f"   Goals ({len(scenario.goals)}): {[str(g) for g in scenario.goals]}")
        print(f"   Constraints ({len(scenario.constraints)}): {[str(c) for c in scenario.constraints]}")
        transitions = scenario.get_allowed_transitions()
        print(f"   Transitions ({len(transitions)}): {[str(t) for t in transitions]}")
        
        # Build the graph and show details
        graph = scenario.build_graph()
        print(f"   Starting Graph: {graph.g.number_of_nodes()} nodes, {graph.g.number_of_edges()} edges")
        
        print("\n=== Graph Details ===")
        for node, data in graph.g.nodes(data=True):
            print(f"Node: {node} -> {data}")
        
        print("\n=== Ready for IsoSearch! ===")
        
        # Initialize visualization if enabled
        visualizer = None
        tree_visualizer = None
        if enable_visualization:
            visualizer = IsoSearchVisualizer(scenario_name)
            tree_visualizer = DecisionTreeVisualizer(scenario_name)
            print("🎨 Visualization enabled - HTML reports will be generated")
        
        # Run the exploration
        print(f"\n=== Exploring {scenario.name} ===")
        result = DesignSpaceExplorationWithVisualization(scenario, visualizer, tree_visualizer)
        
        # Generate visualization if enabled
        if enable_visualization:
            if visualizer:
                viz_file = visualizer.generate_html()
                print(f"📊 Timeline visualization saved: {viz_file}")
            if tree_visualizer:
                tree_file = tree_visualizer.generate_html()
                print(f"🌳 Decision tree visualization saved: {tree_file}")
        
        print(f"\n✅ Scenario '{scenario.name}' complete!")
        print(f"   Mechanisms discovered: {len(result)}")
        
        return result
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        return []


def run_multiple_scenarios(scenario_names=None):
    """
    Run IsoSearch exploration on multiple scenarios
    Args: scenario_names - list of scenario names to run (default: all scenarios)
    Returns: dict mapping scenario names to their results
    """
    if scenario_names is None:
        scenario_names = list(SCENARIOS.keys())
    
    results = {}
    
    print("🚀 Starting multi-scenario IsoSearch exploration")
    print(f"Scenarios to explore: {', '.join(scenario_names)}")
    
    for i, scenario_name in enumerate(scenario_names, 1):
        print(f"\n{'='*80}")
        print(f"SCENARIO {i}/{len(scenario_names)}: {scenario_name.upper()}")
        print(f"{'='*80}")
        
        result = run_scenario(scenario_name)
        results[scenario_name] = result
        
        if i < len(scenario_names):
            print(f"\n⏳ Moving to next scenario...")
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 EXPLORATION SUMMARY")
    print(f"{'='*80}")
    
    total_mechanisms = 0
    for scenario_name, result in results.items():
        mechanism_count = len(result)
        total_mechanisms += mechanism_count
        status = "✅ SUCCESS" if mechanism_count > 0 else "❌ NO MECHANISMS"
        print(f"{scenario_name:20} | {mechanism_count:2} mechanisms | {status}")
    
    print(f"\nTotal mechanisms discovered: {total_mechanisms}")
    
    return results


def create_cli_parser():
    """Create and configure the command-line argument parser"""
    import argparse
    
    parser = argparse.ArgumentParser(
        prog='isosearch',
        description='IsoSearch Algorithm for Automated Security Mechanism Discovery',
        epilog='''
Examples:
  %(prog)s                                    # Run default scenario (basic_sharing)
  %(prog)s --list                             # List all available scenarios
  %(prog)s basic_sharing                      # Run single scenario
  %(prog)s rsi_focused authority_chain        # Run multiple scenarios
  %(prog)s --all                              # Run all scenarios
  %(prog)s --verbose rsi_focused              # Run with detailed output
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Positional arguments
    parser.add_argument(
        'scenarios',
        nargs='*',
        help='Names of scenarios to run. If none specified, runs default scenario.'
    )
    
    # Optional arguments
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available scenarios and exit'
    )
    
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Run all available scenarios'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output with detailed exploration tracking'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress detailed output, show only final results'
    )
    
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=5,
        help='Maximum number of iterations per scenario (default: 5)'
    )
    
    parser.add_argument(
        '--visualize', '-z',
        action='store_true',
        help='Generate HTML visualizations: timeline view and decision tree showing OSmosis graph states'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='IsoSearch v1.0 - Automated Security Mechanism Discovery'
    )
    
    return parser


def validate_scenarios(scenario_names):
    """Validate that all requested scenarios exist"""
    available = set(SCENARIOS.keys())
    requested = set(scenario_names)
    invalid = requested - available
    
    if invalid:
        print(f"❌ Error: Unknown scenario(s): {', '.join(sorted(invalid))}")
        print(f"\nAvailable scenarios:")
        list_scenarios()
        return False
    
    return True


def print_detailed_scenario_info():
    """Print detailed information about all scenarios"""
    print("📋 AVAILABLE SCENARIOS")
    print("=" * 60)
    
    for name, scenario in SCENARIOS.items():
        print(f"\n🎯 {name}")
        print(f"   Description: {scenario.description}")
        print(f"   Goals ({len(scenario.goals)}):")
        for goal in scenario.goals:
            print(f"     • {goal}")
        print(f"   Constraints ({len(scenario.constraints)}):")
        if scenario.constraints:
            for constraint in scenario.constraints:
                print(f"     • {constraint}")
        else:
            print(f"     • None")
        transitions = scenario.get_allowed_transitions()
        print(f"   Transitions ({len(transitions)}):")
        for transition in transitions:
            print(f"     • {transition.transition_type}: {transition.description}")


if __name__ == "__main__":
    parser = create_cli_parser()
    args = parser.parse_args()
    
    # Handle list scenarios option
    if args.list:
        print_detailed_scenario_info()
        exit(0)
    
    # Determine which scenarios to run
    if args.all:
        if args.scenarios:
            print("⚠️  Warning: --all flag specified, ignoring individual scenario arguments")
        scenario_names = list(SCENARIOS.keys())
    elif args.scenarios:
        scenario_names = args.scenarios
        # Validate scenarios exist
        if not validate_scenarios(scenario_names):
            exit(1)
    else:
        # Default behavior
        scenario_names = ['basic_sharing']
        if not args.quiet:
            print("No scenarios specified, running default scenario: basic_sharing")
            print("Use --help for more options or --list to see all scenarios")
    
    # Configure verbosity (placeholder for future implementation)
    if args.verbose:
        print("🔍 Verbose mode enabled - detailed exploration tracking")
    elif args.quiet:
        print("🔇 Quiet mode enabled - minimal output")
    
    # Set max iterations (placeholder for future implementation) 
    if args.max_iterations != 5:
        print(f"📊 Using {args.max_iterations} maximum iterations per scenario")
    
    # Configure visualization
    if args.visualize:
        print("🎨 HTML visualization enabled")
    
    try:
        # Run the scenarios
        if len(scenario_names) == 1:
            print(f"\n🎯 Running scenario: {scenario_names[0]}")
            result = run_scenario(scenario_names[0], enable_visualization=args.visualize)
        else:
            print(f"\n🚀 Running {len(scenario_names)} scenarios: {', '.join(scenario_names)}")
            results = run_multiple_scenarios(scenario_names)
            
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Exploration interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Error during exploration: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        exit(1)
    
    print(f"\n✅ Exploration complete!")