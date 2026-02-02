# Pattern-Aware Scoring: RSI Maximization Support

## Problem Analysis

The current pattern-aware scoring system is designed to minimize RSI (reduce sharing) but our reduce_isolation scenario needs to maximize RSI. The system currently:

1. **Activates sharing reduction pattern** when it sees shared resources
2. **Scores removal of shared edges highly** (2.8)
3. **Penalizes adding to shared resources** (0.1 multiplier)
4. **Doesn't check goal direction** (minimize vs maximize)

## Required Modifications

### 1. Goal Direction Detection

```python
def has_rsi_maximization_goal(goals):
    """Check if any RSI goal is set to maximize"""
    for goal in goals:
        if goal.metric_name == 'RSI' and goal.direction == 'maximize':
            return True
    return False
```

### 2. Invert Sharing Pattern Logic

When RSI maximization is detected:

```python
def _score_for_sharing_maximization_pattern(self, op_name, params, base_score, state_analysis, graph, constraints, goals):
    """Invert sharing pattern for RSI maximization"""
    
    shared_resources = state_analysis.get('shared_resources', [])
    
    # For maximization, we want to CREATE sharing, not reduce it
    if op_name == "add_hold_edge":
        to_resource = params.get('to_node', '') or params.get('resource', '')
        from_pd = params.get('from_node', '') or params.get('pd', '')
        
        # Get the target PDs from the RSI goal
        rsi_target_pds = self._get_rsi_target_pds(goals)
        
        # HIGH PRIORITY: Connect target PDs to shared resources
        if from_pd in rsi_target_pds and to_resource in shared_resources:
            return 2.9  # Very high priority for increasing sharing
        
        # MEDIUM PRIORITY: Connect target PDs to any resource the other holds
        if from_pd in rsi_target_pds:
            other_pd = rsi_target_pds[1] if from_pd == rsi_target_pds[0] else rsi_target_pds[0]
            other_pd_resources = self._get_pd_resources(graph, other_pd)
            if to_resource in other_pd_resources:
                return 2.8  # High priority for creating new sharing
    
    # PENALTY: Removing shared edges when maximizing
    if op_name == "remove_hold_edge":
        to_resource = params.get('to_node', '') or params.get('resource', '')
        if to_resource in shared_resources:
            return base_score * 0.1  # Strong penalty for reducing sharing
    
    return base_score
```

### 3. Direct Access Promotion

For reduce_isolation specifically:

```python
# Boost direct connections when PDs have only indirect access
if op_name == "add_hold_edge":
    from_pd = params.get('from_node', '') or params.get('pd', '')
    to_resource = params.get('to_node', '') or params.get('resource', '')
    
    # Check if PD currently has only indirect access
    if self._has_only_indirect_access(graph, from_pd):
        # Check if resource satisfies access constraints
        if self._satisfies_access_constraints(from_pd, to_resource, constraints):
            return 3.0  # Maximum priority for establishing direct access
```

## Implementation Strategy

1. **Add goal direction check** in `_apply_pattern_scoring`
2. **Create separate maximization pattern** that inverts sharing logic  
3. **Boost direct connections** for PDs with only REQUEST edges
4. **Penalize operations that reduce sharing** when maximizing RSI

## Expected Behavior After Fix

1. **Iteration 1**: Connect PD_1 → FILE_1_1 (Score: 3.0)
2. **Iteration 2**: Connect PD_2 → FILE_1_1 (Score: 3.0)
3. **Result**: RSI[PD_1,PD_2] = 1.0 (both share FILE_1_1)
4. **Optional**: Remove mediators PD_3, PD_4 as they're no longer needed

This would achieve the de-mediation goal by establishing direct shared access.