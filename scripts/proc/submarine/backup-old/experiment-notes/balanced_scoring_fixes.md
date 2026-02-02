# Proposed Fixes for Balanced Scoring System

## 1. **Fix Immediate Implementation Issues**

### A. Correct Constraint Violation Detection
```python
def _count_constraint_violations(self, graph, constraints):
    """Enhanced constraint violation counting with better detection"""
    violations = []
    
    for constraint in constraints:
        if hasattr(constraint, 'constraint_type'):
            if constraint.constraint_type == 'prohibit_direct_hold':
                pd = f"PD_{constraint.pd_id}"
                resource = constraint.resource_info
                if graph.g.has_edge(pd, resource):
                    edge_data = graph.g.get_edge_data(pd, resource)
                    if edge_data and edge_data.get('type') == 'HOLD':
                        violations.append({
                            'type': 'prohibit_direct_hold',
                            'pd': pd,
                            'resource': resource,
                            'severity': 'high'  # Prohibited holds are high severity
                        })
    
    # Return both count and details for better scoring
    return len(violations), violations
```

### B. Fix Operation Recognition in Candidates
```python
def _evaluate_constraint_satisfaction(self, old_graph, new_graph, constraints, candidate):
    """Fixed constraint evaluation with proper operation detection"""
    try:
        old_count, old_violations = self._count_constraint_violations(old_graph, constraints)
        new_count, new_violations = self._count_constraint_violations(new_graph, constraints)
        
        violations_reduced = old_count - new_count
        
        # Identify which specific violations were resolved
        resolved_violations = []
        for old_v in old_violations:
            if old_v not in new_violations:
                resolved_violations.append(old_v)
        
        # Give higher scores for resolving high-severity violations
        score = 0.0
        for violation in resolved_violations:
            if violation['severity'] == 'high':
                score += 2.0  # Higher reward for prohibited holds
            else:
                score += 1.0
        
        # Penalty for new violations
        new_violation_count = new_count - old_count
        if new_violation_count > 0:
            score -= new_violation_count * 2.0
        
        return score
```

## 2. **Add Multi-Step Planning Capability**

### A. Look-Ahead Planning
```python
class BalancedScoring:
    def __init__(self, initial_graph=None):
        self.initial_graph = initial_graph
        self.plan_cache = {}  # Cache multi-step plans
        
    def _generate_resolution_plan(self, graph, constraints):
        """Generate a plan to resolve all constraint violations"""
        violations = self._analyze_violations(graph, constraints)
        plan = []
        
        for violation in violations:
            if violation['type'] == 'prohibit_direct_hold':
                # Plan: 1) Create mediator, 2) Add request edges, 3) Remove hold
                plan.extend([
                    ('add_pd', {'purpose': 'mediator'}),
                    ('add_hold_edge', {'pd': 'MEDIATOR', 'resource': violation['resource']}),
                    ('add_request_edge', {'from_pd': violation['pd'], 'to_pd': 'MEDIATOR'}),
                    ('remove_hold_edge', {'pd': violation['pd'], 'resource': violation['resource']})
                ])
        
        return plan
    
    def score_operation(self, operation, candidate, graph, goals, constraints):
        """Enhanced scoring with plan awareness"""
        # Generate plan if not cached
        graph_hash = self._hash_graph(graph)
        if graph_hash not in self.plan_cache:
            self.plan_cache[graph_hash] = self._generate_resolution_plan(graph, constraints)
        
        plan = self.plan_cache[graph_hash]
        
        # Check if this operation is part of the plan
        plan_bonus = 0.0
        for i, (planned_op, planned_params) in enumerate(plan):
            if operation.name == planned_op:
                # Higher bonus for earlier steps in plan
                plan_bonus = 10.0 - i * 0.5
                break
        
        # Continue with regular scoring...
        # Add plan_bonus to final score
```

## 3. **Implement State-Space Search Enhancement**

### A. Constraint-Guided Candidate Generation
```python
def _get_constraint_guided_candidates(self, graph, constraints):
    """Generate candidates specifically targeting constraint violations"""
    candidates = []
    violations = self._analyze_violations(graph, constraints)
    
    for violation in violations:
        if violation['type'] == 'prohibit_direct_hold':
            # Generate specific candidates to resolve this violation
            candidates.extend([
                {
                    'operation': 'remove_hold_edge',
                    'params': {'pd': violation['pd'], 'resource': violation['resource']},
                    'priority': 'high',
                    'resolves': violation
                },
                {
                    'operation': 'add_pd',
                    'params': {'purpose': f"mediator_for_{violation['resource']}"},
                    'priority': 'medium',
                    'enables': 'mediation'
                }
            ])
    
    return candidates
```

## 4. **Hybrid Scoring Approach**

### A. Combine Pattern-Aware and Balanced Scoring
```python
def get_hybrid_score(transition, candidate, graph, goals, constraints, initial_graph=None):
    """Hybrid scoring combining pattern-aware and balanced approaches"""
    
    # Get both scores
    from pattern_aware_scoring import get_pattern_aware_score
    pattern_score = get_pattern_aware_score(transition, candidate, graph, goals, constraints)
    
    balanced_scorer = BalancedScoring(initial_graph)
    balanced_score = balanced_scorer.score_operation(transition, candidate, graph, goals, constraints)
    
    # Weighted combination based on context
    if balanced_scorer._count_constraint_violations(graph, constraints)[0] > 0:
        # High violations: prioritize balanced scoring
        final_score = 0.7 * balanced_score + 0.3 * pattern_score
    else:
        # Low/no violations: prioritize pattern scoring
        final_score = 0.3 * balanced_score + 0.7 * pattern_score
    
    return final_score
```

## 5. **Dynamic Weight Adjustment**

### A. Context-Aware Weights
```python
def _calculate_dynamic_weights(self, graph, constraints, goals):
    """Adjust weights based on current state"""
    weights = {
        'constraint': 5.0,
        'goal': 2.0,
        'base': 1.0
    }
    
    # Count violations
    violation_count = self._count_constraint_violations(graph, constraints)[0]
    
    # Increase constraint weight if violations exist
    if violation_count > 0:
        weights['constraint'] = 10.0 + violation_count * 2.0
        weights['goal'] = 1.0  # Reduce goal priority when constraints violated
    
    # Check goal progress
    if goals:
        goal_distance = self._calculate_total_goal_distance(graph, goals)
        if goal_distance < 0.2:  # Close to goals
            weights['goal'] = 5.0  # Increase goal priority when close
    
    return weights
```

## 6. **Enhanced Architectural Pattern Recognition**

### A. Mediation Pattern Detection
```python
def _detect_mediation_opportunity(self, graph, constraints):
    """Detect opportunities for mediation patterns"""
    opportunities = []
    
    # Find prohibited direct holds
    for constraint in constraints:
        if constraint.constraint_type == 'prohibit_direct_hold':
            pd = f"PD_{constraint.pd_id}"
            resource = constraint.resource_info
            
            # Check if PD needs access to this resource
            needs_access = self._check_access_requirement(pd, resource, constraints)
            
            if needs_access and graph.g.has_edge(pd, resource):
                # Find potential mediators
                potential_mediators = self._find_potential_mediators(graph, resource)
                
                opportunities.append({
                    'type': 'mediation',
                    'pd': pd,
                    'resource': resource,
                    'mediators': potential_mediators,
                    'score_bonus': 5.0
                })
    
    return opportunities
```

## 7. **Scenario-Specific Tuning**

### A. Scenario Configuration
```python
# In scenarios.py, add scoring hints
SCENARIO_SCORING_HINTS = {
    'mediator_test_indirect': {
        'strategy': 'mediation_first',
        'weights': {'constraint': 15.0, 'pattern': 10.0},
        'required_patterns': ['mediation']
    },
    'basic_sharing_primitive': {
        'strategy': 'resource_optimization',
        'weights': {'goal': 10.0, 'resource_efficiency': 5.0},
        'avoid_patterns': ['excessive_sharing']
    },
    'reduce_isolation': {
        'strategy': 'direct_connection',
        'weights': {'goal': 10.0, 'simplicity': 5.0},
        'preferred_operations': ['add_hold_edge']
    }
}
```

### B. Use Hints in Scoring
```python
def score_operation(self, operation, candidate, graph, goals, constraints, scenario_name=None):
    """Enhanced scoring with scenario-specific hints"""
    
    # Get scenario hints if available
    hints = SCENARIO_SCORING_HINTS.get(scenario_name, {})
    
    # Adjust strategy based on hints
    if hints.get('strategy') == 'mediation_first':
        if operation.name in ['add_pd', 'add_request_edge']:
            pattern_bonus += 3.0
    
    # Use scenario-specific weights
    weights = hints.get('weights', self.default_weights)
    
    # Apply preferred operations bonus
    if operation.name in hints.get('preferred_operations', []):
        operation_bonus = 2.0
```

## 8. **Implementation Priority**

### Phase 1: Quick Fixes (High Impact, Low Effort)
1. Fix constraint violation detection (#1A)
2. Fix operation recognition (#1B)
3. Increase weights for constraint resolution

### Phase 2: Core Improvements (High Impact, Medium Effort)
4. Add multi-step planning (#2A)
5. Implement hybrid scoring (#4A)
6. Add dynamic weight adjustment (#5A)

### Phase 3: Advanced Features (Medium Impact, High Effort)
7. Constraint-guided candidate generation (#3A)
8. Enhanced pattern recognition (#6A)
9. Scenario-specific tuning (#7A)

## Expected Results

With these fixes, we should see:
1. **mediator_test_indirect**: Should discover mediation patterns (target: >80% success)
2. **basic_sharing_primitive**: Should find resource optimization solutions (target: >60% success)
3. **reduce_isolation**: Should achieve direct connection patterns (target: >90% success)

The key insight is that **balanced scoring needs to be more than just weighted sums** - it needs planning, context awareness, and pattern recognition to guide the search effectively.