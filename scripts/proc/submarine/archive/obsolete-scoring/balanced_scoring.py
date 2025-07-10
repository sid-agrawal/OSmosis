"""
Balanced Scoring System for Graph Exploration
Combines constraint satisfaction and goal progress for improved architectural discovery
"""

import copy
from generic_model import ModelGraph


class BalancedScoring:
    """
    Balanced scoring system that prioritizes:
    1. Constraint satisfaction (reducing violations)
    2. Goal progress (moving toward targets)
    """
    
    def __init__(self, initial_graph=None):
        self.initial_graph = initial_graph
        self.base_scores = {
            # Base scores for different operation types
            "add_pd": 0.1,
            "remove_pd": 0.1,
            "add_file_resource": 0.2,  # Slightly higher for resource creation
            "remove_file_resource": 0.1,
            "add_resource_space": 0.1,
            "remove_resource_space": 0.1,
            "add_hold_edge": 0.2,  # Important for connections
            "remove_hold_edge": 0.15,  # Can help with constraint resolution
            "add_request_edge": 0.25,  # Important for mediation
            "remove_request_edge": 0.1,
            "add_subset_edge": 0.1,
            "remove_subset_edge": 0.1,
        }
        
        # Scoring weights
        self.constraint_weight = 5.0  # High priority for constraint satisfaction
        self.goal_weight = 2.0       # Moderate priority for goal progress
        self.base_weight = 1.0       # Low priority for base exploration
    
    def score_operation(self, operation, candidate, graph, goals, constraints):
        """
        Score an operation based on constraint satisfaction and goal progress
        Returns: float score (higher = better)
        """
        try:
            # Import necessary functions
            from isosearch import ComputeMetrics
            
            # Apply operation to create new graph state
            new_graph = self._apply_operation_to_graph(operation, candidate, graph)
            
            # Score components
            constraint_score = 0.0
            goal_score = 0.0
            base_score = self.base_scores.get(operation.name, 0.1)
            
            # 1. Evaluate constraint satisfaction
            if constraints:
                constraint_score = self._evaluate_constraint_satisfaction(
                    graph, new_graph, constraints, candidate
                )
            
            # 2. Evaluate goal progress
            if goals:
                current_metrics = ComputeMetrics(graph)
                new_metrics = ComputeMetrics(new_graph)
                goal_score = self._evaluate_goal_progress(
                    goals, current_metrics, new_metrics
                )
            
            # 3. Special bonuses for architectural patterns
            pattern_bonus = self._evaluate_architectural_patterns(
                operation, candidate, graph, new_graph, constraints
            )
            
            # Combine scores with weights
            final_score = (
                self.constraint_weight * constraint_score +
                self.goal_weight * goal_score +
                self.base_weight * base_score +
                pattern_bonus
            )
            
            # Debug output for significant scores
            if final_score > 1.0 or (operation.name == 'remove_hold_edge' and constraint_score != 0):
                print(f"  High score {final_score:.2f} for {operation.name}: "
                      f"constraint={constraint_score:.2f}, goal={goal_score:.2f}, "
                      f"pattern={pattern_bonus:.2f}, base={base_score:.2f}")
            
            return max(final_score, 0.001)  # Ensure positive scores
            
        except Exception as e:
            print(f"Warning: Failed to score operation {operation.name}: {e}")
            return self.base_scores.get(operation.name, 0.1)
    
    def _evaluate_constraint_satisfaction(self, old_graph, new_graph, constraints, candidate):
        """
        Evaluate how well an operation addresses constraint violations
        Returns: score between -1.0 and 1.0
        """
        try:
            # Count violations before and after
            old_violations = self._count_constraint_violations(old_graph, constraints)
            new_violations = self._count_constraint_violations(new_graph, constraints)
            
            # Calculate improvement
            violations_reduced = old_violations - new_violations
            
            # Debug for remove_hold_edge operations
            if candidate.get('operation') == 'remove_hold_edge':
                print(f"    Constraint debug: old_violations={old_violations}, new_violations={new_violations}, reduced={violations_reduced}")
            
            if violations_reduced > 0:
                # Strong positive score for reducing violations
                return 1.0 * violations_reduced
            elif violations_reduced < 0:
                # Strong negative score for increasing violations
                return -1.0 * abs(violations_reduced)
            else:
                # Check if operation is setting up for future constraint resolution
                if self._is_constraint_enabling_operation(candidate, constraints):
                    return 0.3  # Modest positive score
                return 0.0
                
        except Exception as e:
            print(f"Warning: Failed to evaluate constraints: {e}")
            return 0.0
    
    def _count_constraint_violations(self, graph, constraints):
        """Count total constraint violations in the graph"""
        violation_count = 0
        
        for constraint in constraints:
            if hasattr(constraint, 'constraint_type'):
                if constraint.constraint_type == 'prohibit_direct_hold':
                    # Check for prohibited hold edges
                    pd = f"PD_{constraint.pd_id}"
                    resource = constraint.resource_info
                    if graph.g.has_edge(pd, resource):
                        edge_data = graph.g.get_edge_data(pd, resource)
                        if edge_data and edge_data.get('type') == 'HOLD':
                            violation_count += 1
                            
                elif constraint.constraint_type == 'requires_resource_access':
                    # Check if PD has required access
                    pd = f"PD_{constraint.pd_id}"
                    resource = constraint.resource_info
                    if not self._has_access_to_resource(graph, pd, resource):
                        violation_count += 1
                        
                elif constraint.constraint_type == 'requires_file_access':
                    # Check if PD has access to required file type
                    pd = f"PD_{constraint.pd_id}"
                    if not self._has_file_type_access(graph, pd, constraint):
                        violation_count += 1
        
        return violation_count
    
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
                # Check if the neighbor has access to the resource
                if self._has_access_to_resource(graph, neighbor, resource):
                    return True
        
        return False
    
    def _has_file_type_access(self, graph, pd, constraint):
        """Check if PD has access to required file type"""
        file_type = constraint.properties.get('file_type', 'any')
        min_size = constraint.properties.get('min_size_kb', 1) * 1024
        
        # Check all resources the PD holds
        for resource in graph.g.neighbors(pd):
            edge_data = graph.g.get_edge_data(pd, resource)
            if edge_data and edge_data.get('type') == 'HOLD':
                node_data = graph.g.nodes[resource]
                if node_data.get('type') == 'RESOURCE' and node_data.get('data') == 'FILE':
                    # Check file type match
                    extra = eval(node_data.get('extra', '{}'))
                    if file_type == 'any' or extra.get('file_type') == file_type:
                        # Check size requirement
                        size = int(extra.get('size_bytes', '0'))
                        if size >= min_size:
                            return True
        
        return False
    
    def _is_constraint_enabling_operation(self, candidate, constraints):
        """Check if operation enables future constraint resolution"""
        operation_type = candidate.get('operation', '')
        
        # Creating mediators can enable indirect access
        if operation_type == 'add_pd':
            for constraint in constraints:
                if hasattr(constraint, 'type') and constraint.type == 'prohibit_direct_hold':
                    return True  # New PD could become mediator
        
        # Request edges enable indirect access patterns
        if operation_type == 'add_request_edge':
            return True
        
        # Creating resources can help satisfy requirements
        if operation_type == 'add_file_resource':
            return True
            
        return False
    
    def _evaluate_goal_progress(self, goals, current_metrics, new_metrics):
        """
        Evaluate progress toward goals
        Returns: score between -1.0 and 1.0
        """
        total_progress = 0.0
        
        for goal in goals:
            progress = self._calculate_goal_progress(
                goal, current_metrics, new_metrics
            )
            total_progress += progress
        
        # Normalize by number of goals
        if goals:
            return total_progress / len(goals)
        return 0.0
    
    def _calculate_goal_progress(self, goal, current_metrics, new_metrics):
        """Calculate progress toward a specific goal"""
        metric_name = goal.metric_name
        target_value = goal.target_value
        direction = getattr(goal, 'direction', 'minimize')
        
        try:
            # Get metric values
            current_value = self._get_metric_value(current_metrics, metric_name, goal)
            new_value = self._get_metric_value(new_metrics, metric_name, goal)
            
            if current_value is None or new_value is None:
                return 0.0
            
            # Convert to float
            current_value = float(current_value)
            new_value = float(new_value)
            target_value = float(target_value)
            
            # Calculate progress
            if direction == 'minimize':
                if new_value < current_value:
                    # Moving in right direction
                    progress = (current_value - new_value) / max(abs(target_value), 1.0)
                    return min(progress, 1.0)
                elif new_value > current_value:
                    # Moving in wrong direction
                    progress = (current_value - new_value) / max(abs(target_value), 1.0)
                    return max(progress, -1.0)
            else:  # maximize
                if new_value > current_value:
                    # Moving in right direction
                    progress = (new_value - current_value) / max(abs(target_value), 1.0)
                    return min(progress, 1.0)
                elif new_value < current_value:
                    # Moving in wrong direction
                    progress = (new_value - current_value) / max(abs(target_value), 1.0)
                    return max(progress, -1.0)
            
            return 0.0
            
        except Exception as e:
            return 0.0
    
    def _evaluate_architectural_patterns(self, operation, candidate, old_graph, new_graph, constraints=None):
        """
        Provide bonuses for operations that create architectural patterns
        """
        bonus = 0.0
        params = candidate.get('param_values', {})
        
        # Mediation pattern detection
        if operation.name == 'add_request_edge':
            from_pd = params.get('from_pd', '')
            to_pd = params.get('to_pd', '')
            
            # Check if to_pd holds resources that from_pd needs
            if self._creates_mediation_pattern(old_graph, from_pd, to_pd):
                bonus += 2.0  # Strong bonus for mediation
        
        # Resource specialization pattern
        elif operation.name == 'add_file_resource':
            # Creating new resources can enable specialization
            bonus += 0.5
        
        # Removing problematic connections
        elif operation.name == 'remove_hold_edge':
            # Check if this removes a constraint violation
            from_pd = params.get('pd', '')
            resource = params.get('resource', '')
            if self._is_prohibited_hold(old_graph, from_pd, resource, constraints):
                bonus += 1.5  # Good bonus for removing violations
        
        return bonus
    
    def _creates_mediation_pattern(self, graph, from_pd, to_pd):
        """Check if adding request edge creates useful mediation"""
        # Check if to_pd holds resources
        resources_held = []
        for resource in graph.g.neighbors(to_pd):
            edge_data = graph.g.get_edge_data(to_pd, resource)
            if edge_data and edge_data.get('type') == 'HOLD':
                resources_held.append(resource)
        
        # If to_pd holds resources and from_pd doesn't, this could be mediation
        return len(resources_held) > 0
    
    def _is_prohibited_hold(self, graph, pd, resource, constraints=None):
        """Check if a hold edge is prohibited"""
        # Check if there's a prohibit_direct_hold constraint for this edge
        if constraints:
            for constraint in constraints:
                if (hasattr(constraint, 'constraint_type') and constraint.constraint_type == 'prohibit_direct_hold' and
                    hasattr(constraint, 'pd_id') and f"PD_{constraint.pd_id}" == pd and
                    hasattr(constraint, 'resource_info') and constraint.resource_info == resource):
                    return True
        return False
    
    def _get_metric_value(self, metrics, metric_name, goal):
        """Extract metric value from metrics dict"""
        if metric_name in metrics:
            metric_value = metrics[metric_name]
            
            if isinstance(metric_value, dict):
                # For metrics like RSI[PD_1,PD_2]
                target_spec = getattr(goal, 'target_spec', None)
                if target_spec and target_spec in metric_value:
                    return metric_value[target_spec]
                elif metric_value:
                    # Use first available value
                    return list(metric_value.values())[0]
            elif isinstance(metric_value, list):
                # For metrics like TCB
                return len(metric_value)
            else:
                return metric_value
        
        return None
    
    def _apply_operation_to_graph(self, operation, candidate, graph):
        """Apply an operation to create new graph state"""
        # Create a deep copy
        new_graph = copy.deepcopy(graph)
        
        # Apply based on operation type
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
    
    # Operation application methods (same as metric_driven_scoring.py)
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


# Integration function for use with isosearch.py
def get_balanced_score(transition, candidate, graph, goals, constraints, initial_graph=None):
    """
    Main entry point for balanced scoring
    Can be used as a drop-in replacement for other scoring systems
    """
    scorer = BalancedScoring(initial_graph)
    return scorer.score_operation(transition, candidate, graph, goals, constraints)