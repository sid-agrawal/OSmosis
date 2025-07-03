# Current Scoring System - Detailed Analysis

## Overview of Three-Layer Scoring Architecture

### Layer 1: Base Scores (in `_predict_improvement`)

```python
base_scores = {
    # Multi-step transitions
    "privatize_resource": 1.0,      # Highest - complete solution
    "add_mediator": 0.5,            # Medium - complex pattern
    
    # High-impact primitives (problem-solving)
    "remove_file_resource": 0.4,    
    "add_file_resource": 0.6,       # Creates new resources
    "remove_hold_edge": 0.5,        # Removes connections
    "add_hold_edge": 0.4,           # Creates connections
    
    # Medium-impact primitives (structural)
    "remove_pd": 0.3,              
    "add_subset_edge": 0.3,        
    "remove_subset_edge": 0.3,     
    "add_request_edge": 0.2,        # CRITICAL FOR MEDIATION - TOO LOW!
    "remove_request_edge": 0.3,    
    
    # Low-impact primitives (infrastructure)
    "add_pd": 0.2,                  # CRITICAL FOR MEDIATION - TOO LOW!
    "add_resource_space": 0.1,     
    "remove_resource_space": 0.2   
}
```

### Layer 2: Context Adjustments (in `_apply_context_adjustments`)

```python
def _apply_context_adjustments(transition, candidate, graph, goals, base_score):
    score = base_score
    
    # Specific adjustments by operation type
    if transition.name == "add_file_resource":
        score = _adjust_add_file_resource_score(...)  # +0.3 if solving sharing
    elif transition.name == "remove_file_resource":
        score = _adjust_remove_file_resource_score(...)  # Set to 0.0 if violates constraints
    elif transition.name == "add_hold_edge":
        score = _adjust_add_hold_edge_score(...)  # +0.5 if connecting to private resource
    elif transition.name == "remove_hold_edge":
        score = _adjust_remove_hold_edge_score(...)  # +0.5 if PD has alternatives
    
    return score
```

### Layer 3: Constraint/Goal Adjustments

```python
def _apply_constraint_adjustments(score, transition, param_values, graph):
    # Special handling for constraint violations
    if transition.name == "remove_hold_edge":
        # Check for prohibition constraints
        if is_prohibited_edge(from_pd, to_resource):
            return 2.0  # MAXIMUM PRIORITY
    
    # Mediation-aware adjustments (insufficient)
    elif transition.name == "add_pd":
        if shared_resources_exist:
            score += 0.5  # 0.2 + 0.5 = 0.7
    
    elif transition.name == "add_request_edge":
        if pd_could_be_mediator:
            score += 0.4  # 0.2 + 0.4 = 0.6
            
    return score
```

## Detailed Scoring Flow Example

### Scenario: mediator_test_indirect at Iteration 3
**State**: PD_1 and PD_2 have no access to FILE_1_3 (orphaned), PD_3 just created

#### Candidate Generation and Scoring:

1. **add_file_resource** (create CONFIG file)
   - Base score: 0.6
   - Context adjustment: +0.3 (shared files exist)
   - Final score: **0.9**

2. **add_pd** (create PD_4)
   - Base score: 0.2
   - Constraint adjustment: +0.5 (shared resources exist)
   - Final score: **0.7**

3. **add_hold_edge** (connect PD_3 to FILE_1_3)
   - Base score: 0.4
   - Context adjustment: 0 (not recognized as critical)
   - Final score: **0.4** ❌ MEDIATION PATH

4. **add_hold_edge** (connect PD_1 to FILE_1_2)
   - Base score: 0.4
   - Context adjustment: 0
   - Final score: **0.4**

5. **add_request_edge** (PD_1 → PD_3)
   - Base score: 0.2
   - Constraint adjustment: +0.4 (PD_3 could be mediator)
   - Final score: **0.6** (but never reached)

**Result**: Beam search selects top 3: file creation (0.9), PD creation (0.7), and some other operation. The critical mediation step (connect PD_3 to FILE_1_3) is discarded.

## Key Problems in Current Scoring

### 1. Static Base Scores
- Don't adapt to current graph state
- REQUEST edges always score low (0.2)
- PD creation always scores low (0.2)

### 2. Limited Pattern Recognition
```python
# Current system recognizes:
- Shared resources exist → boost PD creation
- PD could be mediator → boost REQUEST edge

# Current system DOESN'T recognize:
- Orphaned resource needs connection
- Multi-step mediation sequence in progress
- Connection operations enable REQUEST edges
```

### 3. Local Optimization Bias
Each operation scored independently:
- "Create file" scores 0.9 (solves sharing locally)
- "Connect to orphaned" scores 0.4 (enables mediation globally)
- System chooses local optimization

### 4. Missing Contextual Factors

The scoring system doesn't consider:
- **Orphaned resources**: Resources with no holders but required by constraints
- **Constraint path**: Whether operation moves toward constraint satisfaction
- **Sequential dependencies**: Operation A enables operation B
- **Pattern completion**: How close we are to completing a security pattern

## Scoring Decision Points

### Where Scoring Happens:
1. **GenerateCandidate()**: Selects single best candidate (greedy mode)
2. **BeamSearchExploration()**: Selects top K candidates for beam
3. Both use same scoring function: `candidate['predicted_improvement']`

### How Scores Are Used:
```python
# In beam search
candidates_with_scores = []
for candidate in all_candidates:
    score = _predict_improvement(transition, candidate, graph, goals)
    candidate['predicted_improvement'] = score
    candidates_with_scores.append(candidate)

# Select top beam_width candidates
candidates_with_scores.sort(key=lambda x: x['predicted_improvement'], reverse=True)
next_beam_candidates = candidates_with_scores[:beam_width]
```

## Summary: Why Mediation Fails

The mediation sequence requires:
1. Remove prohibited edges (score: 2.0) ✅
2. Create mediator PD (score: 0.7) ✅  
3. **Connect PD to orphaned resource (score: 0.4)** ❌ - Lost to file creation (0.9)
4. Add REQUEST edges (score: 0.6) - Never reached

The scoring system's preference for high-scoring local operations (file creation) prevents discovery of lower-scoring intermediate steps that lead to better global solutions (mediation pattern).