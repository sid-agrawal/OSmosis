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
    
    # Calculate RSI (Resource Sharing Index) between all PD pairs
    if len(pd_nodes) >= 2:
        rsi_values = []
        for i in range(len(pd_nodes)):
            for j in range(i + 1, len(pd_nodes)):
                pd1_id = int(pd_nodes[i].split('_')[1])
                pd2_id = int(pd_nodes[j].split('_')[1])
                rsi = _calculate_rsi(candidate, pd1_id, pd2_id)
                rsi_values.append(rsi)
        
        # Use average RSI as overall metric
        metrics['RSI'] = sum(rsi_values) / len(rsi_values) if rsi_values else 0.0
    else:
        metrics['RSI'] = 0.0
    
    # Calculate FR (Fault Ratio) - simplified version
    metrics['FR'] = _calculate_fr(candidate, pd_nodes)
    
    # Calculate TCB (Trusted Computing Base) size
    metrics['TCB'] = _calculate_tcb(candidate, pd_nodes)
    
    # Calculate IB (Information Boundary) violations
    metrics['IB'] = _calculate_ib(candidate, pd_nodes)
    
    print(f"    RSI: {metrics['RSI']:.3f}, FR: {metrics['FR']}, TCB: {metrics['TCB']}, IB: {metrics['IB']}")
    return metrics


def _calculate_rsi(graph, pd1_id, pd2_id):
    """Calculate RSI (Resource Sharing Index) between two PDs"""
    pd1_node = f"PD_{pd1_id}"
    pd2_node = f"PD_{pd2_id}"
    
    # Find resources held by each PD
    pd1_resources = set()
    pd2_resources = set()
    
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD':
            if from_node == pd1_node:
                pd1_resources.add(to_node)
            elif from_node == pd2_node:
                pd2_resources.add(to_node)
    
    # Calculate sharing ratio
    if not pd1_resources and not pd2_resources:
        return 0.0
    
    shared_resources = pd1_resources.intersection(pd2_resources)
    total_resources = pd1_resources.union(pd2_resources)
    
    return len(shared_resources) / len(total_resources) if total_resources else 0.0


def _calculate_fr(graph, pd_nodes):
    """Calculate FR (Fault Ratio) - number of fault propagation paths"""
    # Count edges that could propagate faults (HOLD, REQUEST, MAP edges)
    fault_edges = 0
    
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        edge_type = edge_data.get('type')
        if edge_type in ['HOLD', 'REQUEST', 'MAP']:
            fault_edges += 1
    
    # Normalize by number of PDs
    return fault_edges / len(pd_nodes) if pd_nodes else 0


def _calculate_tcb(graph, pd_nodes):
    """Calculate TCB (Trusted Computing Base) size - count of privileged components"""
    # Count PDs with privileged access (multiple resource holdings)
    tcb_size = 0
    
    for pd_node in pd_nodes:
        # Count resources held by this PD
        resource_count = 0
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd_node and edge_data.get('type') == 'HOLD':
                resource_count += 1
        
        # PDs holding multiple resources are considered part of TCB
        if resource_count > 1:
            tcb_size += 1
    
    return tcb_size


def _calculate_ib(graph, pd_nodes):
    """Calculate IB (Information Boundary) violations - shared resource access"""
    # Count resources accessed by multiple PDs (boundary violations)
    resource_access_count = {}
    
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_access_count:
                resource_access_count[to_node] = 0
            resource_access_count[to_node] += 1
    
    # Count resources accessed by more than one PD
    violations = sum(1 for count in resource_access_count.values() if count > 1)
    return violations


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
        
        # Step 8: Update current graph for next iteration (from pseudocode line 19)
        curGraph = candidate
        
    print("Exploration complete!")
    return explored_mechanisms


def Init():
    """
    Initialize the design space exploration components
    Returns: goals, constraints, transitions, curGraph
    """
    # Create a simple example goal: minimize RSI to 0.3
    goals = [Goal("RSI", 0.3, "minimize")]
    
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
    
    # Both PDs hold the same resource (shared)
    EdgeTransformations.add_hold_edge(curGraph, Permission.R, pd1, ResourceType.VMR, vmr_space, vmr_resource)
    EdgeTransformations.add_hold_edge(curGraph, Permission.R, pd2, ResourceType.VMR, vmr_space, vmr_resource)
    
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