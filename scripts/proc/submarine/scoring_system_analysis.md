# Scoring System Analysis: Why Mediation Discovery Fails

## Current Scoring Hierarchy Problem

### Base Scores (from `_predict_improvement`)
```python
base_scores = {
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
    "add_request_edge": 0.2,  # TOO LOW FOR MEDIATION!
    "remove_request_edge": 0.3,
    
    # Low-impact primitives
    "add_pd": 0.2,  # TOO LOW BUT GETS BOOSTED
    "add_resource_space": 0.1,
    "remove_resource_space": 0.2
}
```

### Three-Layer Scoring System

#### Layer 1: Base Scores
- Fixed priorities based on operation type
- REQUEST edges get lowest score (0.2)
- File creation gets high score (0.6)

#### Layer 2: Context Adjustments (`_apply_context_adjustments`)
- Boosts scores based on current graph state
- Limited mediation awareness

#### Layer 3: Constraint/Goal Adjustments
- Violation fixing gets maximum priority (2.0)
- Mediation-specific boosts are insufficient

## Critical Issues for Mediation Discovery

### 1. REQUEST Edge Score Too Low
```python
"add_request_edge": 0.2  # Base score
# Even with boosts, rarely exceeds 0.6
```
**Problem**: REQUEST edges are essential for mediation but have lowest priority

### 2. Orphaned Resource Connection Not Prioritized
```python
# No specific scoring for connecting to orphaned resources
# Falls under general add_hold_edge (0.4 base)
```
**Problem**: Connecting mediator PD to orphaned resource not recognized as critical

### 3. Sequential Dependency Not Recognized
The scoring system evaluates each operation independently, missing the sequential dependency:
```
1. Remove prohibited edges (score: 2.0) ✅
2. Add mediator PD (score: 0.7) ✅
3. Connect mediator to resource (score: 0.4) ❌ <- Lost to file creation (0.9)
4. Add REQUEST edges (score: 0.2-0.6) ❌ <- Never reached
```

### 4. Scoring Boosts Insufficient

Current mediation-aware boosts:
```python
if transition.name == "add_pd":
    if shared_resources:
        score += 0.5  # 0.2 + 0.5 = 0.7

if transition.name == "add_request_edge":
    if _pd_could_be_mediator(graph, from_pd, to_pd):
        score += 0.4  # 0.2 + 0.4 = 0.6
```

But file creation gets:
```python
if shared_files_of_type:
    return base_score + 0.3  # 0.6 + 0.3 = 0.9
```

## Root Cause: Local vs Global Optimization

The scoring system optimizes each step locally:
- **Local view**: "Creating a file solves sharing" (score: 0.9)
- **Global view**: "Mediation pattern requires 4 coordinated steps" (not recognized)

## Why Beam Search Doesn't Help

Even with multi-path exploration:
```
Beam[0]: remove_edges → add_pd → add_file (0.9) → dead end
Beam[1]: remove_edges → add_pd → add_file (0.9) → dead end  
Beam[2]: remove_edges → add_file → add_pd → dead end
```

All paths prefer high-scoring file creation over lower-scoring connections.

## Solutions Needed

### 1. Pattern-Aware Scoring
Recognize when graph state indicates mediation opportunity:
- Orphaned resource + PDs needing access = boost connection scores
- Mediator PD + orphaned resource = maximize connection priority

### 2. Sequential Planning
Track multi-step patterns:
- If orphaned resource created, prioritize connection over creation
- If mediator connected, prioritize REQUEST edges

### 3. Dynamic Score Adjustment
Adjust scores based on exploration context:
- Reduce file creation score when orphaned resources exist
- Boost connection operations in mediation-ready states

### 4. Goal-Directed Scoring
Let constraint satisfaction guide scoring:
- If "requires_resource_access" unsatisfied, boost access-enabling operations
- If indirect access needed, prioritize REQUEST edges