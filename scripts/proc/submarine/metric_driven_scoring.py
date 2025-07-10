"""
Metric-Driven Scoring System for Graph Exploration
Scores operations based purely on progress toward metric-based goals
"""

import copy
from generic_model import ModelGraph


class MetricDrivenScoring:
    """
    Pure metric-driven scoring system that evaluates operations based solely
    on their impact on goal metrics, without any pattern-aware heuristics.
    """
    
    def __init__(self, initial_graph=None):
        self.initial_graph = initial_graph
        self.base_scores = {
            # Fallback scores for operations that don't improve metrics
            "add_pd": 0.1,
            "remove_pd": 0.1,
            "add_file_resource": 0.1,
            "remove_file_resource": 0.1,
            "add_resource_space": 0.1,
            "remove_resource_space": 0.1,
            "add_hold_edge": 0.1,
            "remove_hold_edge": 0.1,
            "add_request_edge": 0.1,
            "remove_request_edge": 0.1,
            "add_subset_edge": 0.1,
            "remove_subset_edge": 0.1,
        }
    
    def score_operation(self, operation, candidate, graph, goals, constraints):
        """
        Score an operation based purely on its impact on goal metrics
        Returns: float score (higher = better progress toward goals)
        """
        if not goals:
            # No goals defined, use base scoring
            return self.base_scores.get(operation.name, 0.1)
        
        try:
            # Import ComputeMetrics function
            from isosearch import ComputeMetrics
            
            # Apply operation to create new graph state
            new_graph = self._apply_operation_to_graph(operation, candidate, graph)
            
            # Compute metrics on both current and new graph
            current_metrics = ComputeMetrics(graph)
            new_metrics = ComputeMetrics(new_graph)
            
            # Calculate total improvement across all goals
            total_improvement = 0.0
            
            for goal in goals:
                improvement = self._calculate_goal_improvement(
                    goal, current_metrics, new_metrics
                )
                total_improvement += improvement
            
            # Add base score to ensure exploration even when no metric improvement
            base_score = self.base_scores.get(operation.name, 0.1)
            
            # Scale metric improvements and add base score
            final_score = base_score + (total_improvement * 10.0)
            
            return max(final_score, 0.001)  # Ensure positive scores
            
        except Exception as e:
            # If operation simulation fails, return base score
            print(f"Warning: Failed to simulate operation {operation.name}: {e}")
            return self.base_scores.get(operation.name, 0.1)
    
    def _apply_operation_to_graph(self, operation, candidate, graph):
        """
        Apply an operation to a graph to simulate its effect
        Returns: new GraphModel with operation applied
        """
        # Create a deep copy of the graph
        new_graph = copy.deepcopy(graph)
        
        # Apply the operation based on its type
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
            else:
                # Unknown operation, return original graph
                pass
                
        except Exception as e:
            print(f"Warning: Failed to apply operation {operation.name}: {e}")
            # Return original graph if operation fails
            return graph
        
        return new_graph
    
    def _apply_add_pd(self, graph, candidate):
        """Apply add_pd operation to graph"""
        params = candidate.get('param_values', {})
        pd_name = params.get('pd_name', f"PD_{len([n for n in graph.g.nodes() if n.startswith('PD_')]) + 1}")
        
        graph.g.add_node(pd_name, type='PD', data='generated_pd', extra='')
    
    def _apply_remove_pd(self, graph, candidate):
        """Apply remove_pd operation to graph"""
        params = candidate.get('param_values', {})
        pd_name = params.get('pd_name', '')
        
        if pd_name in graph.g.nodes():
            graph.g.remove_node(pd_name)
    
    def _apply_add_file_resource(self, graph, candidate):
        """Apply add_file_resource operation to graph"""
        params = candidate.get('param_values', {})
        resource_name = params.get('resource_name', '')
        space_name = params.get('space_name', 'FILE_SPACE_1')
        
        if resource_name and space_name:
            # Add the resource node
            graph.g.add_node(resource_name, type='RESOURCE', data='FILE', extra='{"generated": true}')
            
            # Add subset edge to space
            if space_name in graph.g.nodes():
                graph.g.add_edge(resource_name, space_name, type='SUBSET')
    
    def _apply_remove_file_resource(self, graph, candidate):
        """Apply remove_file_resource operation to graph"""
        params = candidate.get('param_values', {})
        resource_name = params.get('resource_name', '')
        
        if resource_name in graph.g.nodes():
            graph.g.remove_node(resource_name)
    
    def _apply_add_hold_edge(self, graph, candidate):
        """Apply add_hold_edge operation to graph"""
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('pd', '')
        to_node = params.get('to_node', '') or params.get('resource', '')
        
        if from_node and to_node and from_node in graph.g.nodes() and to_node in graph.g.nodes():
            graph.g.add_edge(from_node, to_node, type='HOLD')
    
    def _apply_remove_hold_edge(self, graph, candidate):
        """Apply remove_hold_edge operation to graph"""
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('pd', '')
        to_node = params.get('to_node', '') or params.get('resource', '')
        
        if from_node and to_node and graph.g.has_edge(from_node, to_node):
            edge_data = graph.g.get_edge_data(from_node, to_node)
            if edge_data and edge_data.get('type') == 'HOLD':
                graph.g.remove_edge(from_node, to_node)
    
    def _apply_add_request_edge(self, graph, candidate):
        """Apply add_request_edge operation to graph"""
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('from_pd', '')
        to_node = params.get('to_node', '') or params.get('to_pd', '')
        
        if from_node and to_node and from_node in graph.g.nodes() and to_node in graph.g.nodes():
            graph.g.add_edge(from_node, to_node, type='REQUEST')
    
    def _apply_remove_request_edge(self, graph, candidate):
        """Apply remove_request_edge operation to graph"""
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('from_pd', '')
        to_node = params.get('to_node', '') or params.get('to_pd', '')
        
        if from_node and to_node and graph.g.has_edge(from_node, to_node):
            edge_data = graph.g.get_edge_data(from_node, to_node)
            if edge_data and edge_data.get('type') == 'REQUEST':
                graph.g.remove_edge(from_node, to_node)
    
    def _apply_add_subset_edge(self, graph, candidate):
        """Apply add_subset_edge operation to graph"""
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('resource', '')
        to_node = params.get('to_node', '') or params.get('space', '')
        
        if from_node and to_node and from_node in graph.g.nodes() and to_node in graph.g.nodes():
            graph.g.add_edge(from_node, to_node, type='SUBSET')
    
    def _apply_remove_subset_edge(self, graph, candidate):
        """Apply remove_subset_edge operation to graph"""
        params = candidate.get('param_values', {})
        from_node = params.get('from_node', '') or params.get('resource', '')
        to_node = params.get('to_node', '') or params.get('space', '')
        
        if from_node and to_node and graph.g.has_edge(from_node, to_node):
            edge_data = graph.g.get_edge_data(from_node, to_node)
            if edge_data and edge_data.get('type') == 'SUBSET':
                graph.g.remove_edge(from_node, to_node)
    
    def _calculate_goal_improvement(self, goal, current_metrics, new_metrics):
        """
        Calculate improvement toward a specific goal
        Returns: float improvement (positive = better, negative = worse)
        """
        metric_name = goal.metric_name
        target_value = goal.target_value
        direction = getattr(goal, 'direction', 'minimize')  # Default to minimize
        
        try:
            # Get current and new metric values
            current_value = self._get_metric_value(current_metrics, metric_name, goal)
            new_value = self._get_metric_value(new_metrics, metric_name, goal)
            
            if current_value is None or new_value is None:
                return 0.0
            
            # Convert to float to avoid type issues
            current_value = float(current_value)
            new_value = float(new_value)
            target_value = float(target_value)
            
            # Calculate distances from target
            current_distance = abs(current_value - target_value)
            new_distance = abs(new_value - target_value)
            
            # Calculate improvement based on direction
            if direction == 'minimize':
                # For minimize goals, improvement is reduction in distance to target
                improvement = current_distance - new_distance
            elif direction == 'maximize':
                # For maximize goals, improvement is also reduction in distance to target
                # (since we're measuring absolute distance)
                improvement = current_distance - new_distance
            else:
                # Unknown direction, default to minimize
                improvement = current_distance - new_distance
            
            return improvement
        except (TypeError, ValueError) as e:
            # Handle conversion errors gracefully
            return 0.0
    
    def _get_metric_value(self, metrics, metric_name, goal):
        """
        Extract metric value from metrics dict, handling different metric types
        """
        if metric_name in metrics:
            metric_value = metrics[metric_name]
            
            # Handle different metric types
            if isinstance(metric_value, dict):
                # For metrics like RSI[PD_1,PD_2], extract specific pair
                target_spec = getattr(goal, 'target_spec', None)
                if target_spec and target_spec in metric_value:
                    return metric_value[target_spec]
                else:
                    # If no specific target, use average or first value
                    if metric_value:
                        # Handle nested lists/dicts in metric values
                        values = []
                        for val in metric_value.values():
                            if isinstance(val, (list, dict)):
                                values.append(len(val))  # Use length for lists/dicts
                            else:
                                values.append(val)
                        if values:
                            return sum(values) / len(values)
                    return 0.0
            elif isinstance(metric_value, list):
                # For metrics like TCB which return lists
                return len(metric_value)
            else:
                # Scalar metric
                return metric_value
        
        return None


# Integration function for use with isosearch.py
def get_metric_driven_score(transition, candidate, graph, goals, constraints, initial_graph=None):
    """
    Main entry point for metric-driven scoring
    Can be used as a drop-in replacement for pattern-aware scoring
    """
    scorer = MetricDrivenScoring(initial_graph)
    return scorer.score_operation(transition, candidate, graph, goals, constraints)