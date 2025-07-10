"""
Goal-Driven Scoring System

Provides intelligent scoring that directly connects operations to goal achievement,
replacing the broken metric-driven scoring that gives uniform 0.100 scores.
"""

from isosearch import ComputeMetrics


def calculate_goal_driven_score(operation_name, params, current_graph, new_graph, goals, constraints, transition_history=None):
    """
    Calculate score based on direct goal improvement and constraint satisfaction
    
    OPTION A: Fix Goal-Driven Scoring
    - Add constraint violation penalties to the scoring function
    - Weight constraint satisfaction higher than goal achievement
    - Recognize when operations lead to unsatisfiable states
    
    Args:
        operation_name: Name of the operation (e.g., 'remove_hold_edge')
        params: Operation parameters
        current_graph: Graph before operation
        new_graph: Graph after operation  
        goals: List of Goal objects
        constraints: List of Constraint objects
        transition_history: List of recent operation names for diversity bonus
    
    Returns:
        float: Score reflecting goal improvement and constraint satisfaction
    """
    base_score = 0.1
    
    # Calculate current and new metrics
    current_metrics = ComputeMetrics(current_graph)
    new_metrics = ComputeMetrics(new_graph)
    
    # OPTION A: Constraint satisfaction gets HIGHEST priority
    constraint_score = calculate_enhanced_constraint_score(operation_name, params, constraints, current_graph, new_graph)
    
    # Check if this operation creates unsatisfiable constraint state
    unsatisfiable_penalty = check_unsatisfiable_state(new_graph, constraints)
    
    # ENHANCED: Goal improvement with special handling for RSI maximization
    total_improvement = 0.0
    for goal in goals:
        if goal.metric_name == "RSI":
            improvement = calculate_rsi_improvement(goal, current_metrics, new_metrics)
            
            # SPECIAL BOOST: For RSI maximization goals, add extra rewards for HOLD edge additions that create target sharing
            if goal.direction == "maximize" and operation_name == "add_hold_edge":
                # Extract the actual parameters from the candidate dictionary
                actual_params = params.get('param_values', params) if isinstance(params, dict) else params
                rsi_boost = calculate_rsi_maximization_boost(goal, actual_params, current_graph, new_graph)
                improvement += rsi_boost
                
            total_improvement += improvement
        elif goal.metric_name == "ASR":
            improvement = calculate_asr_improvement(goal, current_metrics, new_metrics)
            total_improvement += improvement
        elif goal.metric_name == "TCB":
            improvement = calculate_tcb_improvement(goal, current_metrics, new_metrics)
            total_improvement += improvement
    
    # Calculate diversity bonus for different transition types
    diversity_bonus = calculate_diversity_bonus(operation_name, transition_history)
    
    # OPTION A: Weight constraint satisfaction much higher than goal achievement
    final_score = base_score + (constraint_score * 3.0) + (total_improvement * 0.5) + unsatisfiable_penalty + diversity_bonus
    
    # Debug output
    if total_improvement != 0 or constraint_score != 0 or unsatisfiable_penalty != 0 or diversity_bonus != 0:
        print(f"    🎯 {operation_name} goal: {total_improvement:.2f}, constraint: {constraint_score:.2f}, unsatisfiable: {unsatisfiable_penalty:.2f}, diversity: {diversity_bonus:.2f} → total: {final_score:.2f}")
    
    return final_score


def calculate_rsi_improvement(goal, current_metrics, new_metrics):
    """Calculate RSI improvement score"""
    target_pair = goal.target_spec  # e.g., "PD_1,PD_2"
    target_value = goal.target_value  # e.g., 0.8
    
    # Check if the target pair exists in both current and new metrics
    current_rsi = current_metrics['RSI'].get(target_pair)
    new_rsi = new_metrics['RSI'].get(target_pair)
    
    # Handle missing PD pairs gracefully - occurs when nodes are removed
    if current_rsi is None and new_rsi is None:
        # Neither current nor new state has this PD pair (both nodes missing)
        return 0.0
    elif current_rsi is None:
        # Current state missing pair, new state has it (nodes were added)
        current_rsi = 1.0 if goal.direction == "minimize" else 0.0  # Worst case baseline
    elif new_rsi is None:
        # New state missing pair, current state had it (nodes were removed)
        if goal.direction == "minimize":
            # For minimization, removing the pair achieves the goal perfectly
            return 50.0  # Large bonus for eliminating unwanted sharing
        else:
            # For maximization, losing the pair is bad
            return -50.0  # Large penalty for losing target pair
    
    if goal.direction == "minimize":
        if new_rsi < current_rsi:
            # Reward reduction proportional to improvement
            improvement = (current_rsi - new_rsi) * 20.0  # Scale factor for visibility
            
            # Bonus if we reach the target
            if new_rsi <= target_value:
                improvement += 10.0  # Target achievement bonus
                
            return improvement
        elif new_rsi > current_rsi:
            # Penalty for making it worse
            return -(new_rsi - current_rsi) * 10.0
    elif goal.direction == "maximize":
        if new_rsi > current_rsi:
            # Reward increase for maximization goals
            improvement = (new_rsi - current_rsi) * 20.0
            
            # Bonus if we reach the target
            if new_rsi >= target_value:
                improvement += 10.0
                
            return improvement
        elif new_rsi < current_rsi:
            # Penalty for making it worse
            return -(current_rsi - new_rsi) * 10.0
    
    return 0.0


def calculate_asr_improvement(goal, current_metrics, new_metrics):
    """Calculate ASR improvement score"""
    current_asr = current_metrics['ASR']
    new_asr = new_metrics['ASR']
    target_value = goal.target_value
    
    if goal.direction == "minimize":
        if new_asr < current_asr:
            improvement = (current_asr - new_asr) * 15.0
            
            if new_asr <= target_value:
                improvement += 8.0
                
            return improvement
        elif new_asr > current_asr:
            return -(new_asr - current_asr) * 8.0
    elif goal.direction == "maximize":
        if new_asr > current_asr:
            improvement = (new_asr - current_asr) * 15.0
            
            if new_asr >= target_value:
                improvement += 8.0
                
            return improvement
        elif new_asr < current_asr:
            return -(current_asr - new_asr) * 8.0
    
    return 0.0


def calculate_tcb_improvement(goal, current_metrics, new_metrics):
    """Calculate TCB improvement score"""
    target_pd = goal.target_spec  # e.g., "PD_1"
    target_value = goal.target_value  # e.g., 0
    
    current_tcb = len(current_metrics['TCB'].get(target_pd, []))
    new_tcb = len(new_metrics['TCB'].get(target_pd, []))
    
    if goal.direction == "minimize":
        if new_tcb < current_tcb:
            improvement = (current_tcb - new_tcb) * 12.0
            
            if new_tcb <= target_value:
                improvement += 6.0
                
            return improvement
        elif new_tcb > current_tcb:
            return -(new_tcb - current_tcb) * 6.0
    elif goal.direction == "maximize":
        if new_tcb > current_tcb:
            improvement = (new_tcb - current_tcb) * 12.0
            
            if new_tcb >= target_value:
                improvement += 6.0
                
            return improvement
        elif new_tcb < current_tcb:
            return -(current_tcb - new_tcb) * 6.0
    
    return 0.0


def calculate_constraint_score(operation_name, params, constraints, current_graph, new_graph):
    """Calculate score based on constraint satisfaction improvement"""
    
    current_violations = count_constraint_violations(current_graph, constraints)
    new_violations = count_constraint_violations(new_graph, constraints)
    
    violation_improvement = current_violations - new_violations
    
    # Maximum priority for fixing constraint violations
    if violation_improvement > 0:
        return violation_improvement * 25.0  # Highest priority
    elif violation_improvement < 0:
        return violation_improvement * 15.0  # Strong penalty for creating violations
    
    # Special scoring for constraint-relevant operations
    constraint_relevance_score = score_constraint_relevance(operation_name, params, constraints)
    
    return constraint_relevance_score


def score_constraint_relevance(operation_name, params, constraints):
    """Score operations based on relevance to constraint requirements"""
    
    for constraint in constraints:
        if constraint.constraint_type == "prohibit_direct_hold":
            # Operations that remove prohibited edges get high priority
            if operation_name == "remove_hold_edge":
                if is_prohibited_edge(params, constraint):
                    return 20.0  # High priority for constraint compliance
                    
        elif constraint.constraint_type == "requires_resource_access":
            # Operations that enable required access get medium priority
            if operation_name == "add_request_edge":
                if enables_required_access(params, constraint):
                    return 12.0  # Medium priority for access enablement
                    
            elif operation_name == "add_hold_edge":
                if enables_direct_access(params, constraint):
                    return 8.0  # Lower priority for direct access (may violate other constraints)
    
    return 0.0


def is_prohibited_edge(params, constraint):
    """Check if edge removal fixes a prohibited direct hold constraint"""
    try:
        # Extract PD and resource from parameters
        if 'from_node' in params and 'to_node' in params:
            pd_node = params['from_node']
            resource_node = params['to_node']
        elif 'pd' in params and 'resource' in params:
            pd_node = params['pd']
            resource_node = params['resource']
        else:
            return False
            
        # Check if this matches the prohibited constraint
        constraint_pd = f"PD_{constraint.pd_id}"
        constraint_resource = constraint.resource_info
        
        return pd_node == constraint_pd and resource_node == constraint_resource
        
    except Exception:
        return False


def enables_required_access(params, constraint):
    """Check if request edge enables required access"""
    try:
        if 'from_node' in params and 'to_node' in params:
            from_pd = params['from_node']
            to_pd = params['to_node']
        else:
            return False
            
        constraint_pd = f"PD_{constraint.pd_id}"
        
        # Check if this creates indirect access for the constrained PD
        return from_pd == constraint_pd
        
    except Exception:
        return False


def enables_direct_access(params, constraint):
    """Check if hold edge enables required direct access"""
    try:
        if 'from_node' in params and 'to_node' in params:
            pd_node = params['from_node']
            resource_node = params['to_node']
        elif 'pd' in params and 'resource' in params:
            pd_node = params['pd']
            resource_node = params['resource']
        else:
            return False
            
        constraint_pd = f"PD_{constraint.pd_id}"
        constraint_resource = constraint.resource_info
        
        return pd_node == constraint_pd and resource_node == constraint_resource
        
    except Exception:
        return False


def calculate_enhanced_constraint_score(operation_name, params, constraints, current_graph, new_graph):
    """
    OPTION A: Enhanced constraint scoring with higher priority than goal achievement
    
    This function implements sophisticated constraint awareness that:
    1. Detects constraint violations in both current and new states
    2. Rewards operations that fix violations
    3. Penalizes operations that create new violations
    4. Recognizes operations that enable constraint satisfaction
    5. Handles indirect access requirements properly
    """
    
    current_violations = count_constraint_violations(current_graph, constraints)
    new_violations = count_constraint_violations(new_graph, constraints)
    
    violation_improvement = current_violations - new_violations
    
    # OPTION A: Maximum priority for fixing constraint violations
    constraint_score = 0.0
    
    if violation_improvement > 0:
        # Reward fixing violations with highest priority
        constraint_score += violation_improvement * 30.0
    elif violation_improvement < 0:
        # Strong penalty for creating new violations
        constraint_score += violation_improvement * 20.0
    
    # Enhanced constraint-specific operation scoring
    relevance_score = score_enhanced_constraint_relevance(operation_name, params, constraints, current_graph, new_graph)
    constraint_score += relevance_score
    
    # Special handling for indirect access requirements
    indirect_access_score = score_indirect_access_enablement(operation_name, params, constraints, current_graph, new_graph)
    constraint_score += indirect_access_score
    
    return constraint_score


def score_enhanced_constraint_relevance(operation_name, params, constraints, current_graph, new_graph):
    """Enhanced constraint relevance scoring for complex patterns"""
    relevance_score = 0.0
    
    for constraint in constraints:
        if constraint.constraint_type == "prohibit_direct_hold":
            if operation_name == "remove_hold_edge":
                if is_prohibited_edge(params, constraint):
                    relevance_score += 25.0  # High priority for constraint compliance
            elif operation_name == "add_hold_edge":
                if would_create_prohibited_edge(params, constraint):
                    relevance_score -= 30.0  # Strong penalty for violation creation
                    
        elif constraint.constraint_type == "requires_resource_access":
            access_type = constraint.properties.get('access_type', 'direct_or_indirect')
            
            if access_type == "indirect":
                # For indirect access requirements, prioritize mediation patterns
                if operation_name == "add_request_edge":
                    if enables_mediation_pattern(params, constraint, current_graph):
                        relevance_score += 15.0  # Medium-high priority for mediation
                elif operation_name == "add_pd":
                    if creates_potential_mediator(params, constraint, current_graph):
                        relevance_score += 10.0  # Medium priority for mediator creation
                        
            elif access_type == "direct_or_indirect":
                # For flexible access, score based on what enables access
                if operation_name == "add_hold_edge":
                    if enables_direct_access(params, constraint):
                        relevance_score += 8.0  # Lower priority for direct access
                elif operation_name == "add_request_edge":
                    if enables_indirect_access(params, constraint, current_graph):
                        relevance_score += 12.0  # Medium priority for indirect access
    
    return relevance_score


def score_indirect_access_enablement(operation_name, params, constraints, current_graph, new_graph):
    """Score operations that enable indirect access patterns"""
    score = 0.0
    
    # Check if operation creates or improves mediation patterns
    if operation_name == "add_request_edge":
        # Check if this REQUEST edge enables access to resources that PDs need
        from_pd = params.get('from_node', params.get('from_pd', ''))
        to_pd = params.get('to_node', params.get('to_pd', ''))
        
        if from_pd and to_pd:
            # Check if the target PD has resources that the source PD needs
            for constraint in constraints:
                if constraint.constraint_type == "requires_resource_access":
                    if from_pd == f"PD_{constraint.pd_id}":
                        required_resource = constraint.resource_info
                        
                        # Check if to_pd has access to required_resource
                        if new_graph.g.has_edge(to_pd, required_resource):
                            edge_data = new_graph.g[to_pd][required_resource]
                            if edge_data.get('type') == 'HOLD':
                                score += 18.0  # High priority for enabling indirect access
    
    elif operation_name == "add_hold_edge":
        # Check if this creates a resource that can be accessed indirectly
        pd_node = params.get('from_node', params.get('pd', ''))
        resource_node = params.get('to_node', params.get('resource', ''))
        
        if pd_node and resource_node:
            # Check if other PDs need this resource and could access it through this PD
            for constraint in constraints:
                if constraint.constraint_type == "requires_resource_access":
                    if constraint.resource_info == resource_node:
                        access_type = constraint.properties.get('access_type', 'direct_or_indirect')
                        constrained_pd = f"PD_{constraint.pd_id}"
                        
                        if constrained_pd != pd_node and access_type in ['indirect', 'direct_or_indirect']:
                            score += 10.0  # Medium priority for creating accessible resources
    
    return score


def check_unsatisfiable_state(new_graph, constraints):
    """
    OPTION A: Check if the new graph state creates unsatisfiable constraint combinations
    
    Returns negative penalty if state is unsatisfiable
    """
    penalty = 0.0
    
    # Check for impossible constraint combinations
    for constraint in constraints:
        if constraint.constraint_type == "requires_resource_access":
            pd_node = f"PD_{constraint.pd_id}"
            resource_node = constraint.resource_info
            access_type = constraint.properties.get('access_type', 'direct_or_indirect')
            
            # Check if resource exists at all
            if resource_node not in new_graph.g.nodes():
                penalty -= 50.0  # Severe penalty for requiring non-existent resource
                continue
            
            # Check if PD exists
            if pd_node not in new_graph.g.nodes():
                penalty -= 50.0  # Severe penalty for constraint on non-existent PD
                continue
            
            # Check if resource has any holders (if not, indirect access is impossible)
            has_any_holder = False
            for edge_source, edge_target, edge_data in new_graph.g.edges(data=True):
                if edge_target == resource_node and edge_data.get('type') == 'HOLD':
                    has_any_holder = True
                    break
            
            if not has_any_holder and access_type in ['indirect', 'direct_or_indirect']:
                # Resource has no holders - indirect access impossible
                penalty -= 40.0  # High penalty for creating impossible indirect access
    
    # Check for prohibition violations that make access impossible
    for constraint in constraints:
        if constraint.constraint_type == "prohibit_direct_hold":
            pd_node = f"PD_{constraint.pd_id}"
            resource_node = constraint.resource_info
            
            # If this PD is prohibited from direct access, check if indirect access is possible
            if new_graph.g.has_edge(pd_node, resource_node):
                edge_data = new_graph.g[pd_node][resource_node]
                if edge_data.get('type') == 'HOLD':
                    # Check if there's also a requirement for this PD to access this resource
                    for req_constraint in constraints:
                        if (req_constraint.constraint_type == "requires_resource_access" and
                            req_constraint.pd_id == constraint.pd_id and
                            req_constraint.resource_info == resource_node):
                            # This is a violation of prohibition + requirement
                            penalty -= 25.0  # High penalty for direct violation
    
    return penalty


def enables_mediation_pattern(params, constraint, current_graph):
    """Check if REQUEST edge enables mediation pattern for constraint"""
    from_pd = params.get('from_node', params.get('from_pd', ''))
    to_pd = params.get('to_node', params.get('to_pd', ''))
    
    if from_pd and to_pd:
        constraint_pd = f"PD_{constraint.pd_id}"
        required_resource = constraint.resource_info
        
        # Check if this creates: constraint_pd -> REQUEST -> to_pd -> HOLD -> required_resource
        if from_pd == constraint_pd:
            # Check if to_pd has access to required_resource
            if current_graph.g.has_edge(to_pd, required_resource):
                edge_data = current_graph.g[to_pd][required_resource]
                if edge_data.get('type') == 'HOLD':
                    return True
    
    return False


def creates_potential_mediator(params, constraint, current_graph):
    """Check if adding PD creates potential mediator for constraint"""
    # Simple heuristic: if we're adding a PD and there are unmet indirect access requirements,
    # this could potentially become a mediator
    required_resource = constraint.resource_info
    
    # Check if the required resource exists and is accessible
    if required_resource in current_graph.g.nodes():
        return True
    
    return False


def enables_indirect_access(params, constraint, current_graph):
    """Check if REQUEST edge enables indirect access to required resource"""
    return enables_mediation_pattern(params, constraint, current_graph)


def would_create_prohibited_edge(params, constraint):
    """Check if hold edge would create prohibited direct hold"""
    return is_prohibited_edge(params, constraint)


def count_constraint_violations(graph, constraints):
    """Count total constraint violations in graph"""
    violations = 0
    
    for constraint in constraints:
        if constraint.constraint_type == "requires_pd_exists":
            target_pd = constraint.resource_info
            if target_pd not in graph.g.nodes():
                violations += 1
                
        elif constraint.constraint_type == "requires_tcb_dependency":
            dependent_pd = f"PD_{constraint.pd_id}"
            target_pd = constraint.resource_info
            
            # Check if both PDs exist first
            if dependent_pd not in graph.g.nodes() or target_pd not in graph.g.nodes():
                violations += 1
            else:
                # Check TCB dependency
                from isosearch import ComputeMetrics
                metrics = ComputeMetrics(graph)
                tcb = metrics.get('TCB', {})
                dependent_tcb = tcb.get(dependent_pd, [])
                
                if target_pd not in dependent_tcb:
                    violations += 1
                    
        elif constraint.constraint_type == "prohibit_direct_hold":
            pd_node = f"PD_{constraint.pd_id}"
            resource_node = constraint.resource_info
            
            # Check if prohibited edge exists
            if graph.g.has_edge(pd_node, resource_node):
                edge_data = graph.g[pd_node][resource_node]
                if edge_data.get('type') == 'HOLD':
                    violations += 1
                    
        elif constraint.constraint_type == "requires_resource_access":
            pd_node = f"PD_{constraint.pd_id}"
            resource_node = constraint.resource_info
            access_type = constraint.properties.get('access_type', 'direct_or_indirect')
            
            has_access = False
            
            if access_type == "direct":
                # Check direct access only
                if graph.g.has_edge(pd_node, resource_node):
                    edge_data = graph.g[pd_node][resource_node]
                    if edge_data.get('type') == 'HOLD':
                        has_access = True
                        
            elif access_type == "indirect":
                # Check indirect access only (no direct access allowed)
                # First verify no direct access exists
                if graph.g.has_edge(pd_node, resource_node):
                    edge_data = graph.g[pd_node][resource_node]
                    if edge_data.get('type') == 'HOLD':
                        # Has direct access but should only have indirect - violation
                        violations += 1
                        continue
                
                # Check for indirect access through REQUEST edges
                for neighbor in graph.g.neighbors(pd_node):
                    if graph.g.has_edge(pd_node, neighbor):
                        edge_data = graph.g[pd_node][neighbor]
                        if edge_data.get('type') == 'REQUEST':
                            # Check if neighbor has access to resource
                            if graph.g.has_edge(neighbor, resource_node):
                                neighbor_edge = graph.g[neighbor][resource_node]
                                if neighbor_edge.get('type') == 'HOLD':
                                    has_access = True
                                    break
                                    
            elif access_type == "direct_or_indirect":
                # Check direct access
                if graph.g.has_edge(pd_node, resource_node):
                    edge_data = graph.g[pd_node][resource_node]
                    if edge_data.get('type') == 'HOLD':
                        has_access = True
                
                # Check indirect access (through REQUEST edges)
                if not has_access:
                    for neighbor in graph.g.neighbors(pd_node):
                        if graph.g.has_edge(pd_node, neighbor):
                            edge_data = graph.g[pd_node][neighbor]
                            if edge_data.get('type') == 'REQUEST':
                                # Check if neighbor has access to resource
                                if graph.g.has_edge(neighbor, resource_node):
                                    neighbor_edge = graph.g[neighbor][resource_node]
                                    if neighbor_edge.get('type') == 'HOLD':
                                        has_access = True
                                        break
            
            if not has_access:
                violations += 1
    
    return violations


def detect_mediation_pattern_opportunity(graph, constraints):
    """Detect when mediation patterns would help with constraints"""
    
    # Find orphaned resources (resources with no holders)
    orphaned_resources = []
    required_access = []
    
    for node in graph.g.nodes():
        if node.startswith('FILE_'):
            # Check if resource has any holders
            has_holders = False
            for neighbor in graph.g.predecessors(node):
                if graph.g.has_edge(neighbor, node):
                    edge_data = graph.g[neighbor][node]
                    if edge_data.get('type') == 'HOLD':
                        has_holders = True
                        break
            
            if not has_holders:
                orphaned_resources.append(node)
    
    # Find required access that's currently missing
    for constraint in constraints:
        if constraint.constraint_type == "requires_resource_access":
            pd_node = f"PD_{constraint.pd_id}"
            resource_node = constraint.resource_info
            
            # Check if PD has any access to resource
            has_any_access = False
            if graph.g.has_edge(pd_node, resource_node):
                has_any_access = True
            else:
                # Check indirect access
                for neighbor in graph.g.neighbors(pd_node):
                    if graph.g.has_edge(pd_node, neighbor):
                        edge_data = graph.g[pd_node][neighbor]
                        if edge_data.get('type') == 'REQUEST':
                            if graph.g.has_edge(neighbor, resource_node):
                                has_any_access = True
                                break
            
            if not has_any_access:
                required_access.append((pd_node, resource_node))
    
    return len(orphaned_resources) > 0 and len(required_access) > 0


def calculate_diversity_bonus(operation_name, transition_history):
    """
    Calculate bonus for operation diversity to prevent getting stuck in repetitive loops
    
    Args:
        operation_name: Current operation being considered
        transition_history: List of recent operation names
    
    Returns:
        float: Diversity bonus (positive for diverse operations, negative for repetitive)
    """
    if not transition_history:
        return 0.0
    
    # Consider last 5 operations for diversity calculation
    recent_history = transition_history[-5:] if len(transition_history) >= 5 else transition_history
    
    if not recent_history:
        return 0.0
    
    # Count how many times this operation appears in recent history
    operation_count = recent_history.count(operation_name)
    total_recent_ops = len(recent_history)
    
    # Calculate diversity metrics
    unique_operations = len(set(recent_history))
    repetition_ratio = operation_count / total_recent_ops
    
    # Strong penalties for excessive repetition
    if operation_count >= 3:
        # 3+ repetitions of same operation = major penalty
        return -25.0  # Strong penalty to break repetitive loops
    elif operation_count == 2:
        # 2 repetitions = moderate penalty
        return -10.0
    elif operation_count == 1:
        # Recent use = small penalty
        return -3.0
    else:
        # New operation type = diversity bonus
        return 15.0  # Reward trying different operation types
    
    # Additional bonus for high diversity (many different operation types)
    if unique_operations >= 4 and operation_name not in recent_history:
        return 20.0  # Extra bonus for continuing diverse exploration
    
    return 0.0


def calculate_rsi_maximization_boost(goal, params, current_graph, new_graph):
    """Calculate extra boost for HOLD edge additions that create target RSI sharing patterns"""
    
    # Extract target pair from goal (e.g., "PD_1,PD_2")
    target_pair = goal.target_spec
    if not target_pair or ',' not in target_pair:
        return 0.0
    
    pd1, pd2 = target_pair.split(',')
    
    # Extract the PD and resource from the operation parameters
    pd = params.get('pd', params.get('from_node', ''))
    resource = params.get('resource', params.get('to_node', ''))
    
    # Check if this operation directly involves the target PDs
    if pd not in [pd1, pd2]:
        return 0.0
    
    # Check if this operation connects a target PD to a resource
    other_target_pd = pd2 if pd == pd1 else pd1
    
    # Check if the other target PD already has access to this resource
    other_has_resource = False
    for from_node, to_node, edge_data in current_graph.g.edges(data=True):
        if (from_node == other_target_pd and to_node == resource and 
            edge_data.get('type') == 'HOLD'):
            other_has_resource = True
            break
    
    if other_has_resource:
        # This completes the sharing pattern for RSI maximization!
        print(f"    🎯 RSI MAXIMIZATION BOOST: {pd} -> {resource} completes sharing with {other_target_pd}")
        return 100.0  # Massive boost for completing the target sharing pattern
    else:
        # This is the first step toward the sharing pattern
        print(f"    🎯 RSI preparation: {pd} -> {resource} enables future sharing")
        return 30.0  # Good boost for enabling the sharing pattern
