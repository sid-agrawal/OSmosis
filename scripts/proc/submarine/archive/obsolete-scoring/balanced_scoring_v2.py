"""
Enhanced Balanced Scoring System v2 for Graph Exploration
Incorporates multi-step planning and better constraint handling
"""

import copy
from generic_model import ModelGraph


class EnhancedBalancedScoring:
    """
    Enhanced balanced scoring with:
    1. Better constraint violation detection
    2. Multi-step planning capability
    3. Dynamic weight adjustment
    4. Pattern recognition
    """
    
    def __init__(self, initial_graph=None, scenario_name=None):
        self.initial_graph = initial_graph
        self.scenario_name = scenario_name
        self.plan_cache = {}
        
        # Base scores for different operation types
        self.base_scores = {
            "add_pd": 0.3,  # Increased for mediation potential
            "remove_pd": 0.1,
            "add_file_resource": 0.2,
            "remove_file_resource": 0.1,
            "add_resource_space": 0.1,
            "remove_resource_space": 0.1,
            "add_hold_edge": 0.2,
            "remove_hold_edge": 0.5,  # Increased for constraint resolution
            "add_request_edge": 0.4,  # Increased for mediation
            "remove_request_edge": 0.1,
            "add_subset_edge": 0.1,
            "remove_subset_edge": 0.1,
        }
        
        # Default weights (will be adjusted dynamically)
        self.default_weights = {
            'constraint': 10.0,  # Increased base weight
            'goal': 2.0,
            'base': 1.0,
            'plan': 5.0  # New weight for plan following
        }
    
    def score_operation(self, operation, candidate, graph, goals, constraints):
        """
        Enhanced scoring with planning and better constraint handling
        """
        try:
            from isosearch import ComputeMetrics
            
            # Apply operation to create new graph state
            new_graph = self._apply_operation_to_graph(operation, candidate, graph)
            
            # Get dynamic weights based on current state
            weights = self._calculate_dynamic_weights(graph, constraints, goals)
            
            # Score components
            constraint_score = 0.0
            goal_score = 0.0
            plan_score = 0.0
            pattern_score = 0.0
            base_score = self.base_scores.get(operation.name, 0.1)
            
            # 1. Enhanced constraint satisfaction evaluation
            if constraints:
                constraint_score = self._evaluate_constraint_satisfaction_v2(
                    graph, new_graph, constraints, candidate, operation
                )
            
            # 2. Goal progress evaluation
            if goals:
                current_metrics = ComputeMetrics(graph)
                new_metrics = ComputeMetrics(new_graph)
                goal_score = self._evaluate_goal_progress(
                    goals, current_metrics, new_metrics
                )
            
            # 3. Multi-step plan scoring
            plan_score = self._evaluate_plan_alignment(
                operation, candidate, graph, constraints
            )
            
            # 4. Pattern recognition bonus
            pattern_score = self._evaluate_patterns_v2(
                operation, candidate, graph, new_graph, constraints
            )
            
            # Combine scores with dynamic weights
            final_score = (
                weights['constraint'] * constraint_score +
                weights['goal'] * goal_score +
                weights['base'] * base_score +
                weights['plan'] * plan_score +
                pattern_score  # Pattern score is additive bonus
            )
            
            # Debug output for significant operations
            if final_score > 2.0 or (operation.name == 'remove_hold_edge' and constraint_score > 0):
                print(f"  ★ High score {final_score:.2f} for {operation.name}: "
                      f"constraint={constraint_score:.2f}, goal={goal_score:.2f}, "
                      f"plan={plan_score:.2f}, pattern={pattern_score:.2f}")
            
            return max(final_score, 0.001)
            
        except Exception as e:
            print(f"Warning: Failed to score operation {operation.name}: {e}")
            return self.base_scores.get(operation.name, 0.1)
    
    def _calculate_dynamic_weights(self, graph, constraints, goals):
        """Adjust weights based on current state"""
        weights = self.default_weights.copy()
        
        # Count violations
        violation_count, _ = self._count_constraint_violations_v2(graph, constraints)
        
        # Dramatically increase constraint weight if violations exist
        if violation_count > 0:
            weights['constraint'] = 20.0 + violation_count * 5.0
            weights['goal'] = 0.5  # Reduce goal priority when constraints violated
            weights['plan'] = 10.0  # Increase plan following
        
        return weights
    
    def _count_constraint_violations_v2(self, graph, constraints):
        """Enhanced constraint violation detection"""
        violations = []
        
        for constraint in constraints:
            if hasattr(constraint, 'constraint_type'):
                if constraint.constraint_type == 'prohibit_direct_hold':
                    pd = f"PD_{constraint.pd_id}"
                    resource = constraint.resource_info
                    
                    if pd in graph.g.nodes() and resource in graph.g.nodes():
                        if graph.g.has_edge(pd, resource):
                            edge_data = graph.g.get_edge_data(pd, resource)
                            if edge_data and edge_data.get('type') == 'HOLD':
                                violations.append({
                                    'type': 'prohibit_direct_hold',
                                    'pd': pd,
                                    'resource': resource,
                                    'constraint': constraint,
                                    'severity': 'critical'
                                })
                
                elif constraint.constraint_type == 'requires_resource_access':
                    pd = f"PD_{constraint.pd_id}"
                    resource = constraint.resource_info
                    if not self._has_access_to_resource(graph, pd, resource):
                        violations.append({
                            'type': 'requires_resource_access',
                            'pd': pd,
                            'resource': resource,
                            'constraint': constraint,
                            'severity': 'high'
                        })
        
        return len(violations), violations
    
    def _evaluate_constraint_satisfaction_v2(self, old_graph, new_graph, constraints, candidate, operation):
        """Enhanced constraint evaluation with detailed scoring"""
        try:
            old_count, old_violations = self._count_constraint_violations_v2(old_graph, constraints)
            new_count, new_violations = self._count_constraint_violations_v2(new_graph, constraints)
            
            score = 0.0
            
            # Find resolved violations
            resolved = []
            for old_v in old_violations:
                found = False
                for new_v in new_violations:
                    if (old_v['pd'] == new_v['pd'] and 
                        old_v['resource'] == new_v['resource'] and
                        old_v['type'] == new_v['type']):
                        found = True
                        break
                if not found:
                    resolved.append(old_v)
            
            # Score based on resolved violations
            for violation in resolved:
                if violation['severity'] == 'critical':
                    score += 3.0  # High reward for critical violations
                elif violation['severity'] == 'high':
                    score += 2.0
                else:
                    score += 1.0
            
            # Penalty for new violations
            new_violation_count = new_count - old_count
            if new_violation_count > 0:
                score -= new_violation_count * 3.0
            
            # Special handling for operations that enable future resolution
            if score == 0 and self._enables_constraint_resolution(operation, candidate, old_violations):
                score = 0.5  # Modest positive score
            
            return score
            
        except Exception as e:
            print(f"Warning: Constraint evaluation failed: {e}")
            return 0.0
    
    def _enables_constraint_resolution(self, operation, candidate, violations):
        """Check if operation enables future constraint resolution"""
        if not violations:
            return False
        
        # Creating PDs can enable mediation
        if operation.name == 'add_pd':
            for v in violations:
                if v['type'] == 'prohibit_direct_hold':
                    return True
        
        # Request edges enable indirect access
        if operation.name == 'add_request_edge':
            params = candidate.get('param_values', {})
            to_pd = params.get('to_pd', '')
            # Check if to_pd holds resources needed by constrained PDs
            for v in violations:
                if v['type'] in ['prohibit_direct_hold', 'requires_resource_access']:
                    return True
        
        return False
    
    def _evaluate_plan_alignment(self, operation, candidate, graph, constraints):
        """Score based on alignment with multi-step resolution plan"""
        # Generate or retrieve plan
        graph_hash = str(sorted(graph.g.nodes()))  # Simple hash
        if graph_hash not in self.plan_cache:
            self.plan_cache[graph_hash] = self._generate_resolution_plan(graph, constraints)
        
        plan = self.plan_cache[graph_hash]
        
        # Check if operation matches plan
        params = candidate.get('param_values', {})
        for i, step in enumerate(plan):
            if self._matches_plan_step(operation, params, step):
                # Higher score for earlier steps
                return 1.0 - (i * 0.1)
        
        return 0.0
    
    def _generate_resolution_plan(self, graph, constraints):
        """Generate a plan to resolve constraint violations"""
        _, violations = self._count_constraint_violations_v2(graph, constraints)
        plan = []
        
        # Group violations by type
        prohibit_holds = [v for v in violations if v['type'] == 'prohibit_direct_hold']
        
        # For each prohibited hold, plan mediation
        for violation in prohibit_holds:
            pd = violation['pd']
            resource = violation['resource']
            mediator_name = f"PD_MEDIATOR_{resource}"
            
            plan.extend([
                {
                    'operation': 'add_pd',
                    'purpose': 'mediator',
                    'params': {'pd_name': mediator_name}
                },
                {
                    'operation': 'add_hold_edge',
                    'purpose': 'mediator_access',
                    'params': {'pd': mediator_name, 'resource': resource}
                },
                {
                    'operation': 'add_request_edge',
                    'purpose': 'enable_indirect',
                    'params': {'from_pd': pd, 'to_pd': mediator_name}
                },
                {
                    'operation': 'remove_hold_edge',
                    'purpose': 'remove_violation',
                    'params': {'pd': pd, 'resource': resource}
                }
            ])
        
        return plan
    
    def _matches_plan_step(self, operation, params, plan_step):
        """Check if operation matches a planned step"""
        if operation.name != plan_step['operation']:
            return False
        
        # Check key parameters
        if plan_step['operation'] == 'remove_hold_edge':
            return (params.get('pd') == plan_step['params'].get('pd') and
                    params.get('resource') == plan_step['params'].get('resource'))
        
        # For other operations, matching operation type is enough
        return True
    
    def _evaluate_patterns_v2(self, operation, candidate, old_graph, new_graph, constraints):
        """Enhanced pattern recognition"""
        bonus = 0.0
        params = candidate.get('param_values', {})
        
        # Strong bonus for removing prohibited holds
        if operation.name == 'remove_hold_edge':
            pd = params.get('pd', '')
            resource = params.get('resource', '')
            if self._is_prohibited_hold_v2(old_graph, pd, resource, constraints):
                bonus += 5.0  # Major bonus
                print(f"    ✓ Removing prohibited hold: {pd} → {resource}")
        
        # Mediation pattern creation
        elif operation.name == 'add_request_edge':
            from_pd = params.get('from_pd', '')
            to_pd = params.get('to_pd', '')
            if self._creates_useful_mediation(old_graph, from_pd, to_pd, constraints):
                bonus += 3.0
                print(f"    ✓ Creating mediation: {from_pd} → {to_pd}")
        
        # Resource creation for constraint resolution
        elif operation.name == 'add_file_resource':
            if self._helps_constraint_resolution(new_graph, constraints):
                bonus += 1.0
        
        return bonus
    
    def _is_prohibited_hold_v2(self, graph, pd, resource, constraints):
        """Check if a hold edge is prohibited"""
        for constraint in constraints:
            if (hasattr(constraint, 'constraint_type') and 
                constraint.constraint_type == 'prohibit_direct_hold' and
                f"PD_{constraint.pd_id}" == pd and 
                constraint.resource_info == resource):
                return True
        return False
    
    def _creates_useful_mediation(self, graph, from_pd, to_pd, constraints):
        """Check if request edge creates useful mediation"""
        # Check if from_pd has prohibited holds
        _, violations = self._count_constraint_violations_v2(graph, constraints)
        
        for v in violations:
            if v['pd'] == from_pd and v['type'] == 'prohibit_direct_hold':
                # Check if to_pd could serve as mediator
                resource = v['resource']
                if not graph.g.has_edge(to_pd, resource):
                    # to_pd could potentially hold the resource
                    return True
        
        return False
    
    def _helps_constraint_resolution(self, graph, constraints):
        """Check if current state helps resolve constraints"""
        _, violations = self._count_constraint_violations_v2(graph, constraints)
        # Resource creation helps if we have unmet access requirements
        for v in violations:
            if v['type'] == 'requires_resource_access':
                return True
        return False
    
    # Include all the operation application methods from original
    def _has_access_to_resource(self, graph, pd, resource):
        """Check if PD has direct or indirect access to resource"""
        # Direct access
        if graph.g.has_edge(pd, resource):
            edge_data = graph.g.get_edge_data(pd, resource)
            if edge_data and edge_data.get('type') == 'HOLD':
                return True
        
        # Indirect access through REQUEST edges
        for neighbor in graph.g.neighbors(pd):
            edge_data = graph.g.get_edge_data(pd, neighbor)
            if edge_data and edge_data.get('type') == 'REQUEST':
                if self._has_access_to_resource(graph, neighbor, resource):
                    return True
        
        return False
    
    def _evaluate_goal_progress(self, goals, current_metrics, new_metrics):
        """Evaluate progress toward goals"""
        total_progress = 0.0
        
        for goal in goals:
            progress = self._calculate_goal_progress(goal, current_metrics, new_metrics)
            total_progress += progress
        
        if goals:
            return total_progress / len(goals)
        return 0.0
    
    def _calculate_goal_progress(self, goal, current_metrics, new_metrics):
        """Calculate progress toward a specific goal"""
        metric_name = goal.metric_name
        target_value = goal.target_value
        direction = getattr(goal, 'direction', 'minimize')
        
        try:
            current_value = self._get_metric_value(current_metrics, metric_name, goal)
            new_value = self._get_metric_value(new_metrics, metric_name, goal)
            
            if current_value is None or new_value is None:
                return 0.0
            
            current_value = float(current_value)
            new_value = float(new_value)
            target_value = float(target_value)
            
            if direction == 'minimize':
                if new_value < current_value:
                    progress = (current_value - new_value) / max(abs(target_value), 1.0)
                    return min(progress, 1.0)
                elif new_value > current_value:
                    progress = (current_value - new_value) / max(abs(target_value), 1.0)
                    return max(progress, -1.0)
            else:  # maximize
                if new_value > current_value:
                    progress = (new_value - current_value) / max(abs(target_value), 1.0)
                    return min(progress, 1.0)
                elif new_value < current_value:
                    progress = (new_value - current_value) / max(abs(target_value), 1.0)
                    return max(progress, -1.0)
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _get_metric_value(self, metrics, metric_name, goal):
        """Extract metric value from metrics dict"""
        if metric_name in metrics:
            metric_value = metrics[metric_name]
            
            if isinstance(metric_value, dict):
                target_spec = getattr(goal, 'target_spec', None)
                if target_spec and target_spec in metric_value:
                    return metric_value[target_spec]
                elif metric_value:
                    return list(metric_value.values())[0]
            elif isinstance(metric_value, list):
                return len(metric_value)
            else:
                return metric_value
        
        return None
    
    def _apply_operation_to_graph(self, operation, candidate, graph):
        """Apply an operation to create new graph state"""
        new_graph = copy.deepcopy(graph)
        
        try:
            if operation.name == "add_pd":
                self._apply_add_pd(new_graph, candidate)
            elif operation.name == "remove_pd":
                self._apply_remove_pd(new_graph, candidate)
            elif operation.name == "add_file_resource":
                self._apply_add_file_resource(new_graph, candidate)
            elif operation.name == "remove_file_resource":
                self._apply_remove_file_resource(new_graph, candidate)
            elif operation.name == "add_hold_edge":
                self._apply_add_hold_edge(new_graph, candidate)
            elif operation.name == "remove_hold_edge":
                self._apply_remove_hold_edge(new_graph, candidate)
            elif operation.name == "add_request_edge":
                self._apply_add_request_edge(new_graph, candidate)
            elif operation.name == "remove_request_edge":
                self._apply_remove_request_edge(new_graph, candidate)
            elif operation.name == "add_subset_edge":
                self._apply_add_subset_edge(new_graph, candidate)
            elif operation.name == "remove_subset_edge":
                self._apply_remove_subset_edge(new_graph, candidate)
        except Exception as e:
            print(f"Warning: Failed to apply {operation.name}: {e}")
            return graph
        
        return new_graph
    
    # Include all operation application methods from original balanced_scoring.py
    def _apply_add_pd(self, graph, candidate):
        params = candidate.get('param_values', {})
        pd_name = params.get('pd_name', f"PD_{len([n for n in graph.g.nodes() if n.startswith('PD_')]) + 1}")
        graph.g.add_node(pd_name, type='PD', data='generated_pd', extra='')
    
    def _apply_remove_pd(self, graph, candidate):
        params = candidate.get('param_values', {})
        pd_name = params.get('pd_name', '')
        if pd_name in graph.g.nodes():
            graph.g.remove_node(pd_name)
    
    def _apply_add_file_resource(self, graph, candidate):
        params = candidate.get('param_values', {})
        resource_name = params.get('resource_name', '')
        space_name = params.get('space_name', 'FILE_SPACE_1')
        if resource_name and space_name:
            graph.g.add_node(resource_name, type='RESOURCE', data='FILE', extra='{"generated": true}')
            if space_name in graph.g.nodes():
                graph.g.add_edge(resource_name, space_name, type='SUBSET')
    
    def _apply_remove_file_resource(self, graph, candidate):
        params = candidate.get('param_values', {})
        resource_name = params.get('resource_name', '')
        if resource_name in graph.g.nodes():
            graph.g.remove_node(resource_name)
    
    def _apply_add_hold_edge(self, graph, candidate):
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('pd', '')
        to_node = params.get('to_node', '') or params.get('resource', '')
        if from_node and to_node and from_node in graph.g.nodes() and to_node in graph.g.nodes():
            graph.g.add_edge(from_node, to_node, type='HOLD')
    
    def _apply_remove_hold_edge(self, graph, candidate):
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('pd', '')
        to_node = params.get('to_node', '') or params.get('resource', '')
        if from_node and to_node and graph.g.has_edge(from_node, to_node):
            edge_data = graph.g.get_edge_data(from_node, to_node)
            if edge_data and edge_data.get('type') == 'HOLD':
                graph.g.remove_edge(from_node, to_node)
    
    def _apply_add_request_edge(self, graph, candidate):
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('from_pd', '')
        to_node = params.get('to_node', '') or params.get('to_pd', '')
        if from_node and to_node and from_node in graph.g.nodes() and to_node in graph.g.nodes():
            graph.g.add_edge(from_node, to_node, type='REQUEST')
    
    def _apply_remove_request_edge(self, graph, candidate):
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('from_pd', '')
        to_node = params.get('to_node', '') or params.get('to_pd', '')
        if from_node and to_node and graph.g.has_edge(from_node, to_node):
            edge_data = graph.g.get_edge_data(from_node, to_node)
            if edge_data and edge_data.get('type') == 'REQUEST':
                graph.g.remove_edge(from_node, to_node)
    
    def _apply_add_subset_edge(self, graph, candidate):
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('resource', '')
        to_node = params.get('to_node', '') or params.get('space', '')
        if from_node and to_node and from_node in graph.g.nodes() and to_node in graph.g.nodes():
            graph.g.add_edge(from_node, to_node, type='SUBSET')
    
    def _apply_remove_subset_edge(self, graph, candidate):
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('resource', '')
        to_node = params.get('to_node', '') or params.get('space', '')
        if from_node and to_node and graph.g.has_edge(from_node, to_node):
            edge_data = graph.g.get_edge_data(from_node, to_node)
            if edge_data and edge_data.get('type') == 'SUBSET':
                graph.g.remove_edge(from_node, to_node)


# Integration function
def get_enhanced_balanced_score(transition, candidate, graph, goals, constraints, initial_graph=None):
    """Main entry point for enhanced balanced scoring"""
    scorer = EnhancedBalancedScoring(initial_graph)
    return scorer.score_operation(transition, candidate, graph, goals, constraints)