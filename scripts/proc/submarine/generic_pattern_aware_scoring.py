"""
Generic Pattern-Aware Scoring System

This module provides the main scoring engine that combines constraint handlers
and pattern detectors to provide intelligent, context-aware operation scoring.
"""

from typing import Dict, List, Optional, Any, Union
from generic_constraint_framework import (
    ConstraintHandler, ScoringContext, DefaultConstraintHandlerRegistry
)
from generic_pattern_detectors import (
    PatternDetector, DefaultPatternDetectorRegistry
)
from generic_resource_type_system import ResourceTypeSystem, create_default_resource_type_system


class GenericPatternAwareScoring:
    """Generic pattern-aware scoring with pluggable constraint handlers and pattern detectors"""
    
    def __init__(self, 
                 resource_type_system: Optional[ResourceTypeSystem] = None,
                 constraint_handlers: Optional[List[ConstraintHandler]] = None,
                 pattern_detectors: Optional[List[PatternDetector]] = None,
                 config: Optional[Dict] = None):
        
        # Initialize systems
        self.resource_type_system = resource_type_system or create_default_resource_type_system()
        self.constraint_handlers = constraint_handlers or DefaultConstraintHandlerRegistry.get_default_handlers()
        self.pattern_detectors = pattern_detectors or DefaultPatternDetectorRegistry.get_default_detectors()
        
        # Configuration
        self.config = config or self._default_config()
        
        # Scoring policies
        self.scoring_policies = self.config.get('scoring_policies', {})
        
        # Base scores for different operations
        self.base_scores = self.config.get('base_scores', self._default_base_scores())
        
        # Pattern state tracking
        self.pattern_states = {
            'orphaned_resources': [],
            'potential_mediators': [],
            'shared_resources': [],
            'recent_operations': [],
            'constraint_violations_removed': 0,
            'original_pds': None
        }
    
    def score_operation(self, operation, candidate, graph, goals, constraints):
        """
        Main scoring function with pluggable constraint and pattern handling
        Returns: float score (higher = better)
        """
        # Get base score
        base_score = self.base_scores.get(operation.name, 0.3)
        
        # Analyze current graph state
        pattern_state = self._analyze_graph_state(graph)
        
        # Create context for handlers and detectors
        context = ScoringContext(
            graph=graph,
            goals=goals,
            resource_type_system=self.resource_type_system,
            pattern_state=pattern_state
        )
        
        # Get operation parameters
        params = candidate.get('param_values', {}) if isinstance(candidate, dict) else {}
        
        # Apply constraint-specific scoring
        constraint_scores = self._apply_constraint_scoring(
            operation, params, graph, constraints, context
        )
        
        # Apply pattern-specific scoring
        pattern_scores = self._apply_pattern_scoring(
            operation, candidate, context
        )
        
        # Apply sequence bonuses
        sequence_bonus = self._apply_sequence_bonuses(operation.name)
        
        # Combine scores using policy
        final_score = self._combine_scores(
            base_score, constraint_scores, pattern_scores, sequence_bonus
        )
        
        # Track operation history
        self._update_operation_history(operation.name, params)
        
        return final_score
    
    def _apply_constraint_scoring(self, operation, params: Dict, graph, constraints, context: ScoringContext) -> List[tuple]:
        """Apply constraint-specific scoring using pluggable handlers"""
        constraint_scores = []
        
        for constraint in constraints:
            for handler in self.constraint_handlers:
                if handler.applies_to(constraint):
                    score = handler.score_operation(operation, params, graph, constraint, context)
                    if score is not None:
                        priority = handler.get_priority_level()
                        constraint_scores.append((score, priority, handler.__class__.__name__))
        
        return constraint_scores
    
    def _apply_pattern_scoring(self, operation, candidate: Dict, context: ScoringContext) -> List[tuple]:
        """Apply pattern-specific scoring using pluggable detectors"""
        pattern_scores = []
        
        for detector in self.pattern_detectors:
            if detector.is_active(context):
                score = detector.score_operation(operation, candidate, context)
                if score is not None:
                    priority = detector.get_priority_level()
                    pattern_scores.append((score, priority, detector.get_pattern_name()))
        
        return pattern_scores
    
    def _apply_sequence_bonuses(self, op_name: str) -> float:
        """Apply sequence-based bonuses"""
        recent = self.pattern_states['recent_operations']
        
        if len(recent) >= 2:
            # After removing prohibited edges, boost infrastructure
            if all('remove_hold_edge' in op for op in recent[-2:]):
                if op_name == "add_pd":
                    return 0.5  # Boost mediator creation
                elif op_name == "add_hold_edge":
                    return 0.3  # Boost resource connection
        
        return 0.0
    
    def _combine_scores(self, base_score: float, 
                       constraint_scores: List[tuple], 
                       pattern_scores: List[tuple], 
                       sequence_bonus: float) -> float:
        """Combine scores according to configured policy"""
        
        policy = self.scoring_policies.get('combination_method', 'priority_override')
        
        if policy == 'priority_override':
            return self._priority_override_combination(
                base_score, constraint_scores, pattern_scores, sequence_bonus
            )
        elif policy == 'weighted_sum':
            return self._weighted_sum_combination(
                base_score, constraint_scores, pattern_scores, sequence_bonus
            )
        elif policy == 'maximum':
            return self._maximum_combination(
                base_score, constraint_scores, pattern_scores, sequence_bonus
            )
        else:
            # Default to priority override
            return self._priority_override_combination(
                base_score, constraint_scores, pattern_scores, sequence_bonus
            )
    
    def _priority_override_combination(self, base_score: float,
                                     constraint_scores: List[tuple],
                                     pattern_scores: List[tuple],
                                     sequence_bonus: float) -> float:
        """Combine scores with priority override (highest priority wins)"""
        
        # Constraint scores by priority level (lower number = higher priority)
        if constraint_scores:
            constraint_scores.sort(key=lambda x: x[1])  # Sort by priority level
            highest_constraint = constraint_scores[0]
            return highest_constraint[0]  # Return highest priority constraint score
        
        # Pattern scores by priority level
        if pattern_scores:
            pattern_scores.sort(key=lambda x: x[1])  # Sort by priority level
            highest_pattern = pattern_scores[0]
            return highest_pattern[0] + sequence_bonus  # Add sequence bonus to pattern scores
        
        # Base score with sequence bonus
        return base_score + sequence_bonus
    
    def _weighted_sum_combination(self, base_score: float,
                                constraint_scores: List[tuple],
                                pattern_scores: List[tuple],
                                sequence_bonus: float) -> float:
        """Combine scores using weighted sum"""
        
        weights = self.scoring_policies.get('weights', {
            'constraint': 0.6,
            'pattern': 0.3,
            'base': 0.1
        })
        
        # Calculate weighted constraint score
        constraint_contribution = 0.0
        if constraint_scores:
            # Use highest constraint score
            max_constraint = max(score for score, _, _ in constraint_scores)
            constraint_contribution = max_constraint * weights['constraint']
        
        # Calculate weighted pattern score
        pattern_contribution = 0.0
        if pattern_scores:
            # Use highest pattern score
            max_pattern = max(score for score, _, _ in pattern_scores)
            pattern_contribution = max_pattern * weights['pattern']
        
        # Base score contribution
        base_contribution = base_score * weights['base']
        
        return constraint_contribution + pattern_contribution + base_contribution + sequence_bonus
    
    def _maximum_combination(self, base_score: float,
                           constraint_scores: List[tuple],
                           pattern_scores: List[tuple],
                           sequence_bonus: float) -> float:
        """Combine scores by taking maximum"""
        
        all_scores = [base_score + sequence_bonus]
        
        # Add constraint scores
        all_scores.extend(score for score, _, _ in constraint_scores)
        
        # Add pattern scores (with sequence bonus)
        all_scores.extend(score + sequence_bonus for score, _, _ in pattern_scores)
        
        return max(all_scores)
    
    def _analyze_graph_state(self, graph) -> Dict:
        """Analyze current graph to identify pattern opportunities"""
        try:
            # Update original PDs if not cached
            if self.pattern_states['original_pds'] is None:
                self.pattern_states['original_pds'] = self._identify_original_pds(graph)
            
            # Find key graph features
            orphaned = self._find_orphaned_resources(graph)
            mediators = self._find_potential_mediators(graph)
            shared = self._find_shared_resources(graph)
            
            # Update pattern state
            self.pattern_states.update({
                'orphaned_resources': orphaned,
                'potential_mediators': mediators,
                'shared_resources': shared
            })
            
            return self.pattern_states.copy()
            
        except Exception as e:
            print(f"Warning: Error analyzing graph state: {e}")
            return self.pattern_states.copy()
    
    def _find_orphaned_resources(self, graph) -> List[str]:
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
    
    def _find_potential_mediators(self, graph) -> List[str]:
        """Find PDs that could serve as mediators"""
        potential_mediators = []
        
        # Get all PDs
        pds = [n for n, d in graph.g.nodes(data=True) 
               if d.get('type') == 'PD']
        
        original_pds = self.pattern_states.get('original_pds', [])
        
        for pd in pds:
            # Newly created PDs are good mediator candidates
            if pd not in original_pds:
                potential_mediators.append(pd)
            # Original PDs with few dependencies can also be mediators
            elif self._get_pd_dependency_count(graph, pd) <= 1:
                potential_mediators.append(pd)
        
        return potential_mediators
    
    def _find_shared_resources(self, graph) -> List[str]:
        """Find all shared resources (held by multiple PDs)"""
        resource_holders = {}
        
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if edge_data.get('type') == 'HOLD':
                if to_node not in resource_holders:
                    resource_holders[to_node] = []
                resource_holders[to_node].append(from_node)
        
        return [r for r, holders in resource_holders.items() if len(holders) > 1]
    
    def _identify_original_pds(self, graph) -> List[str]:
        """Dynamically identify original PDs based on graph structure"""
        all_pds = []
        for node, data in graph.g.nodes(data=True):
            if data.get('type') == 'PD' and node.startswith('PD_'):
                try:
                    pd_id = int(node.split('_')[1])
                    all_pds.append((pd_id, node))
                except (ValueError, IndexError):
                    continue
        
        # Sort by ID and find consecutive sequence
        all_pds.sort(key=lambda x: x[0])
        original_pds = []
        expected_id = 1
        
        for pd_id, pd_name in all_pds:
            if pd_id == expected_id:
                original_pds.append(pd_name)
                expected_id += 1
            else:
                break  # Gap indicates newly created PDs
        
        return original_pds
    
    def _get_pd_dependency_count(self, graph, pd: str) -> int:
        """Get number of dependencies for a PD"""
        dependencies = 0
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if from_node == pd and edge_data.get('type') == 'REQUEST':
                dependencies += 1
        return dependencies
    
    def _update_operation_history(self, op_name: str, params: Dict):
        """Update operation history for sequence recognition"""
        self.pattern_states['recent_operations'].append(f"{op_name}({params})")
        
        # Keep only last 5 operations
        if len(self.pattern_states['recent_operations']) > 5:
            self.pattern_states['recent_operations'].pop(0)
    
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'scoring_policies': {
                'combination_method': 'priority_override',
                'weights': {
                    'constraint': 0.6,
                    'pattern': 0.3,
                    'base': 0.1
                }
            },
            'base_scores': self._default_base_scores(),
            'sequence_bonuses': {
                'enabled': True,
                'decay_factor': 0.9
            }
        }
    
    def _default_base_scores(self) -> Dict[str, float]:
        """Default base scores for operations"""
        return {
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
    
    def set_constraint_handlers(self, handlers: List[ConstraintHandler]):
        """Set custom constraint handlers"""
        self.constraint_handlers = handlers
    
    def add_constraint_handler(self, handler: ConstraintHandler):
        """Add a constraint handler"""
        self.constraint_handlers.append(handler)
    
    def set_pattern_detectors(self, detectors: List[PatternDetector]):
        """Set custom pattern detectors"""
        self.pattern_detectors = detectors
    
    def add_pattern_detector(self, detector: PatternDetector):
        """Add a pattern detector"""
        self.pattern_detectors.append(detector)
    
    def get_scoring_explanation(self, operation, candidate, graph, goals, constraints) -> Dict:
        """Get detailed explanation of how score was calculated"""
        base_score = self.base_scores.get(operation.name, 0.3)
        pattern_state = self._analyze_graph_state(graph)
        context = ScoringContext(graph, goals, self.resource_type_system, pattern_state)
        params = candidate.get('param_values', {}) if isinstance(candidate, dict) else {}
        
        # Get all score components
        constraint_scores = self._apply_constraint_scoring(operation, params, graph, constraints, context)
        pattern_scores = self._apply_pattern_scoring(operation, candidate, context)
        sequence_bonus = self._apply_sequence_bonuses(operation.name)
        final_score = self._combine_scores(base_score, constraint_scores, pattern_scores, sequence_bonus)
        
        return {
            'final_score': final_score,
            'base_score': base_score,
            'constraint_scores': constraint_scores,
            'pattern_scores': pattern_scores,
            'sequence_bonus': sequence_bonus,
            'combination_method': self.scoring_policies.get('combination_method', 'priority_override'),
            'active_patterns': [d.get_pattern_name() for d in self.pattern_detectors if d.is_active(context)],
            'applicable_handlers': [h.__class__.__name__ for h in self.constraint_handlers 
                                  for c in constraints if h.applies_to(c)]
        }


# Convenience function for creating pattern-aware scoring with defaults
def create_pattern_aware_scoring(domain: str = "os_security") -> GenericPatternAwareScoring:
    """Create pattern-aware scoring system configured for specific domain"""
    
    # Get domain-specific components
    if domain == "os_security":
        pattern_detectors = DefaultPatternDetectorRegistry.get_detectors_for_domain("os_security")
    elif domain == "network_security":
        pattern_detectors = DefaultPatternDetectorRegistry.get_detectors_for_domain("network_security")
    else:
        pattern_detectors = DefaultPatternDetectorRegistry.get_default_detectors()
    
    return GenericPatternAwareScoring(
        pattern_detectors=pattern_detectors
    )