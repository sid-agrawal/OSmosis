"""
Pattern-Aware Scoring System for Mediation Discovery
Recognizes multi-step patterns and adjusts scores dynamically
"""

import json


class PatternAwareScoring:
    """
    Enhanced scoring system that recognizes multi-step security patterns
    and adjusts operation scores based on graph context
    """
    
    def __init__(self):
        # Base scores remain as fallback
        self.base_scores = {
            # Multi-step transitions
            "privatize_resource": 1.0,
            "add_mediator": 0.5,
            
            # High-impact primitives
            "remove_file_resource": 0.4,
            "add_file_resource": 0.6,
            "remove_hold_edge": 0.5,
            "add_hold_edge": 0.4,
            
            # Medium-impact primitives
            "remove_pd": 0.3,
            "add_subset_edge": 0.3,
            "remove_subset_edge": 0.3,
            "add_request_edge": 0.2,
            "remove_request_edge": 0.3,
            
            # Low-impact primitives
            "add_pd": 0.2,
            "add_resource_space": 0.1,
            "remove_resource_space": 0.2
        }
        
        # Pattern state tracking
        self.pattern_states = {
            'orphaned_resources': [],
            'potential_mediators': [],
            'recent_operations': [],
            'constraint_violations_removed': 0
        }
    
    def analyze_graph_state(self, graph):
        """Analyze current graph to identify pattern opportunities"""
        try:
            orphaned = self._find_orphaned_resources(graph)
            mediators = self._find_potential_mediators(graph)
            
            self.pattern_states['orphaned_resources'] = orphaned
            self.pattern_states['potential_mediators'] = mediators
            
            # Check for mediation opportunity
            has_orphaned = len(orphaned) > 0
            has_pds_needing_access = self._find_pds_needing_access(graph)
            
            return {
                'has_orphaned_resources': has_orphaned,
                'orphaned_resources': orphaned,
                'has_access_needs': has_pds_needing_access,
                'mediation_opportunity': has_orphaned and has_pds_needing_access,
                'potential_mediators': mediators
            }
        except Exception as e:
            print(f"Warning: Error analyzing graph state: {e}")
            return {
                'has_orphaned_resources': False,
                'orphaned_resources': [],
                'has_access_needs': False,
                'mediation_opportunity': False,
                'potential_mediators': []
            }
    
    def score_operation(self, operation, candidate, graph, goals, constraints):
        """
        Score an operation with pattern awareness
        Returns: float score (higher = better)
        """
        # Get base score
        base_score = self.base_scores.get(operation.name, 0.3)
        
        # Analyze current graph state
        state_analysis = self.analyze_graph_state(graph)
        
        # Get operation parameters
        params = candidate.get('param_values', {}) if isinstance(candidate, dict) else {}
        
        # Apply pattern-aware adjustments
        score = self._apply_pattern_scoring(
            operation.name, params, base_score, state_analysis, graph, constraints
        )
        
        # Track operation history
        self._update_operation_history(operation.name, params)
        
        return score
    
    def _apply_pattern_scoring(self, op_name, params, base_score, state_analysis, graph, constraints):
        """Apply pattern-aware scoring adjustments"""
        score = base_score
        
        # CRITICAL: Constraint violation removal gets maximum priority
        if op_name == "remove_hold_edge":
            # Handle both parameter naming conventions
            from_pd = params.get('from_node', '') or params.get('pd', '')
            to_resource = params.get('to_node', '') or params.get('resource', '')
            
            # Check if this removes a prohibited edge
            if self._is_prohibited_edge(from_pd, to_resource, constraints):
                return 3.0  # MAXIMUM PRIORITY
        
        # Pattern 1: Mediation Opportunity Detection
        if state_analysis['mediation_opportunity']:
            score = self._score_for_mediation_pattern(
                op_name, params, score, state_analysis, graph, constraints
            )
        
        # Pattern 2: Sequence Recognition
        score = self._apply_sequence_bonuses(op_name, score)
        
        # Pattern 3: Constraint-Driven Scoring
        score = self._apply_constraint_scoring(op_name, params, score, graph, constraints)
        
        return score
    
    def _score_for_mediation_pattern(self, op_name, params, base_score, state_analysis, graph, constraints):
        """Special scoring when mediation pattern is possible"""
        
        # Phase 1: If orphaned resources exist
        if state_analysis['has_orphaned_resources']:
            orphaned = state_analysis.get('orphaned_resources', [])
            
            # Boost PD creation as potential mediator
            if op_name == "add_pd":
                return base_score + 1.3  # 0.2 + 1.3 = 1.5
            
            # CRITICAL: Boost connecting to orphaned resources
            if op_name == "add_hold_edge":
                # Handle both parameter naming conventions
                to_resource = params.get('to_node', '') or params.get('resource', '')
                if to_resource in orphaned:
                    from_pd = params.get('from_node', '') or params.get('pd', '')
                    
                    # EXTRA BOOST: If resource is mentioned in constraints (like FILE_1_3)
                    constraint_priority = self._is_constraint_mentioned_resource(to_resource, constraints)
                    
                    # Check if this PD could be a mediator
                    if self._could_be_mediator(from_pd, graph):
                        if constraint_priority:
                            return 3.0  # MAXIMUM PRIORITY for constraint-required resources
                        else:
                            return 2.5  # VERY HIGH PRIORITY for other orphaned resources
                    else:
                        if constraint_priority:
                            return 1.5  # HIGH PRIORITY for constraint-required resources
                        else:
                            return 1.0  # Still good but not mediator
            
            # If mediator exists and is connected, boost REQUEST edges
            if op_name == "add_request_edge":
                if self._mediator_ready_for_requests(graph):
                    return 1.8  # HIGH PRIORITY for completing mediation
        
        # Phase 2: Building toward mediation
        elif self._building_toward_mediation(graph):
            if op_name == "remove_hold_edge":
                # Removing shared edges creates orphaned resources
                to_resource = params.get('to_node', '')
                if self._is_shared_resource(graph, to_resource):
                    return base_score + 0.8  # Encourage creating orphaned resources
        
        return base_score
    
    def _apply_sequence_bonuses(self, op_name, current_score):
        """Bonus scores based on operation sequences"""
        recent = self.pattern_states['recent_operations']
        
        if len(recent) >= 2:
            # After removing prohibited edges, boost infrastructure
            if all('remove_hold_edge' in op for op in recent[-2:]):
                if op_name == "add_pd":
                    return current_score + 0.5
                elif op_name == "add_hold_edge":
                    return current_score + 0.3
        
        return current_score
    
    def _apply_constraint_scoring(self, op_name, params, score, graph, constraints):
        """Adjust scoring based on constraint satisfaction"""
        
        # Check if operation helps satisfy constraints
        if op_name == "add_request_edge":
            from_pd = params.get('from_pd', '')
            to_pd = params.get('to_pd', '')
            
            # Check if this REQUEST edge helps with access constraints
            if self._helps_access_constraint(from_pd, to_pd, graph, constraints):
                score += 0.8
        
        return score
    
    # Helper methods
    
    def _find_orphaned_resources(self, graph):
        """Find resources with no holders"""
        orphaned = []
        
        # Get all resources
        resources = [n for n, d in graph.g.nodes(data=True) 
                    if d.get('type') == 'RESOURCE']
        
        for resource in resources:
            holders = []
            for from_node, to_node, edge_data in graph.g.edges(data=True):
                if to_node == resource and edge_data.get('type') == 'HOLD':
                    holders.append(from_node)
            
            if len(holders) == 0:
                orphaned.append(resource)
        
        return orphaned
    
    def _find_potential_mediators(self, graph):
        """Find PDs that could serve as mediators"""
        mediators = []
        
        pds = [n for n, d in graph.g.nodes(data=True) if d.get('type') == 'PD']
        
        for pd in pds:
            # A good mediator has few dependencies and holds resources
            resources_held = self._get_pd_resources(graph, pd)
            dependencies = self._get_pd_dependencies(graph, pd)
            
            if len(resources_held) > 0 and len(dependencies) < 2:
                mediators.append(pd)
        
        return mediators
    
    def _find_pds_needing_access(self, graph):
        """Check if any PDs need access to resources they don't have"""
        # Simplified check - in real implementation would check constraints
        orphaned = self._find_orphaned_resources(graph)
        return len(orphaned) > 0
    
    def _could_be_mediator(self, pd, graph):
        """Check if a PD could serve as mediator"""
        # Don't use original PDs as mediators
        if pd in ['PD_1', 'PD_2']:
            return False
        
        # New PDs (PD_3, etc.) are good mediator candidates
        return True
    
    def _mediator_ready_for_requests(self, graph):
        """Check if a mediator is connected to orphaned resources"""
        orphaned = self._find_orphaned_resources(graph)
        
        if not orphaned:
            # No orphaned resources, check for mediation pattern
            for pd in self.pattern_states['potential_mediators']:
                resources = self._get_pd_resources(graph, pd)
                if resources:
                    return True
        
        return False
    
    def _building_toward_mediation(self, graph):
        """Check if we're building toward a mediation pattern"""
        # Check for shared resources that could be mediated
        shared = self._find_shared_resources(graph)
        return len(shared) > 0
    
    def _is_shared_resource(self, graph, resource):
        """Check if a resource is shared by multiple PDs"""
        holders = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if to_node == resource and edge_data.get('type') == 'HOLD':
                holders.append(from_node)
        return len(holders) > 1
    
    def _find_shared_resources(self, graph):
        """Find all shared resources"""
        resource_holders = {}
        
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'HOLD':
                if to_node not in resource_holders:
                    resource_holders[to_node] = []
                resource_holders[to_node].append(from_node)
        
        return [r for r, holders in resource_holders.items() if len(holders) > 1]
    
    def _get_pd_resources(self, graph, pd):
        """Get resources held by a PD"""
        resources = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd and edge_data.get('type') == 'HOLD':
                resources.append(to_node)
        return resources
    
    def _get_pd_dependencies(self, graph, pd):
        """Get PDs that this PD depends on"""
        dependencies = []
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd and edge_data.get('type') == 'REQUEST':
                dependencies.append(to_node)
        return dependencies
    
    def _is_prohibited_edge(self, from_pd, to_resource, constraints):
        """Check if an edge is explicitly prohibited by constraints"""
        for constraint in constraints:
            if (hasattr(constraint, 'constraint_type') and 
                constraint.constraint_type == "prohibit_direct_hold"):
                
                pd_id = getattr(constraint, 'pd_id', None)
                resource_info = getattr(constraint, 'resource_info', None)
                
                if (pd_id and from_pd == f"PD_{pd_id}" and 
                    resource_info and to_resource == resource_info):
                    return True
        
        return False
    
    def _helps_access_constraint(self, from_pd, to_pd, graph, constraints):
        """Check if REQUEST edge helps satisfy access constraints"""
        # Check if to_pd has resources that from_pd needs
        to_pd_resources = self._get_pd_resources(graph, to_pd)
        
        for constraint in constraints:
            if (hasattr(constraint, 'constraint_type') and 
                constraint.constraint_type == "requires_resource_access"):
                
                pd_id = getattr(constraint, 'pd_id', None)
                if pd_id and from_pd == f"PD_{pd_id}":
                    # This PD needs access, check if to_pd can provide it
                    return len(to_pd_resources) > 0
        
        return False
    
    def _update_operation_history(self, op_name, params):
        """Track recent operations for sequence detection"""
        self.pattern_states['recent_operations'].append(op_name)
        
        # Keep only last 5 operations
        if len(self.pattern_states['recent_operations']) > 5:
            self.pattern_states['recent_operations'].pop(0)
        
        # Track constraint fixes
        if op_name == "remove_hold_edge" and self._is_constraint_fix(params):
            self.pattern_states['constraint_violations_removed'] += 1
    
    def _is_constraint_fix(self, params):
        """Check if operation fixes a constraint violation"""
        # Simplified check - would need actual constraint validation
        return True  # Assume removes help constraints
    
    def _is_constraint_mentioned_resource(self, resource, constraints):
        """Check if a resource is specifically mentioned in constraints"""
        for constraint in constraints:
            # Check if constraint mentions this resource
            if hasattr(constraint, 'resource_info') and constraint.resource_info == resource:
                return True
            # Also check if resource is in constraint description
            if hasattr(constraint, 'description') and resource in str(constraint.description):
                return True
        return False


# Integration function
def get_pattern_aware_score(transition, candidate, graph, goals, constraints):
    """
    Main entry point for pattern-aware scoring
    Replaces _predict_improvement in isosearch.py
    """
    scorer = PatternAwareScoring()
    return scorer.score_operation(transition, candidate, graph, goals, constraints)