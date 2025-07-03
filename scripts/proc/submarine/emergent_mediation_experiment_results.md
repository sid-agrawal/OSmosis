# Emergent Mediation Discovery Experiment Results

## Experiment Overview
We tested whether mediation patterns could emerge naturally through constraint pressure alone, without any mediation-specific logic in the algorithm.

## Approach
**Simplifications Made:**
1. **`_find_add_pd_candidates()`**: Removed mediation-specific logic that detected orphaned resources and suggested mediator PDs
2. **`_find_add_hold_edge_candidates()`**: Removed complex scoring that prioritized connecting PDs to orphaned resources for mediation
3. **`_find_add_request_edge_candidates()`**: Removed mediation pattern detection and scoring
4. **Exploration Diversity**: Added 15% random selection from top 3 candidates to encourage exploration
5. **Increased Iterations**: From 5 to 10 to allow more time for emergent patterns

## Test Scenario: mediator_test_indirect
**Constraints that should force mediation:**
- `prohibit_direct_hold: PD_1 -> FILE_1_3` (cannot hold directly)
- `prohibit_direct_hold: PD_2 -> FILE_1_3` (cannot hold directly)  
- `requires_resource_access: PD_1 -> FILE_1_3` (must have access)
- `requires_resource_access: PD_2 -> FILE_1_3` (must have access)
- `requires_resource_exists: FILE_1_3` (cannot delete resource)

## Results: **FAILURE** - No Mediation Discovered

### What Actually Happened:
1. **Iterations 1-2**: ✅ Successfully removed prohibited HOLD edges (constraint pressure worked)
2. **Iterations 3-10**: ❌ Got stuck in loop adding disconnected PDs

### Final Graph State:
```
PD_1 --HOLD--> FILE_1_1
PD_2 --HOLD--> FILE_1_2  
PD_3 (disconnected)
PD_4 (disconnected)
PD_5 (disconnected)
PD_6 (disconnected)  
PD_7 (disconnected)
PD_8 (disconnected)
PD_9 (disconnected)
FILE_1_3 (orphaned - no holders)
```

### Why Mediation Didn't Emerge:

1. **Insufficient Scoring for Resource Connection**: 
   - Connecting PDs to orphaned FILE_1_3 scored only 0.5
   - Adding new PDs scored 0.7 (higher priority)
   - Algorithm kept choosing to add PDs instead of connecting existing ones

2. **No Incentive for REQUEST Edges**:
   - REQUEST edges scored only 0.2-0.3  
   - Much lower than adding PDs (0.7)
   - Algorithm never reached the REQUEST edge creation phase

3. **Goal Satisfaction Prevented Exploration**:
   - RSI goal (minimize sharing) satisfied immediately after removing shared access
   - No driving force to create the complex mediation pattern

## Key Insights

### ✅ Constraint Pressure Works for Simple Operations
- Prohibition constraints successfully drove edge removal
- Basic constraint satisfaction is effective for primitive operations

### ❌ Emergent Mediation Requires Coordinated Scoring
- Multi-step patterns need coordinated incentives across different operation types
- Natural scoring (utility-based) insufficient for complex security pattern discovery
- Need explicit recognition of "mediation opportunities" to score them appropriately

### 🎯 Special Cases Were Actually Necessary
The original mediation-specific logic provided essential functions:
1. **Orphaned Resource Detection**: Recognized when resources needed mediators
2. **Mediation Opportunity Scoring**: Prioritized mediator creation over random PD addition
3. **Indirect Access Incentives**: Scored REQUEST edges higher when they enable access to needed resources

## Conclusion

**Mediation discovery requires intentional pattern recognition**, not just constraint pressure. While constraint pressure can drive simple operations (like removing prohibited edges), discovering complex multi-step security patterns requires:

1. **Pattern-Aware Scoring**: Recognizing when a situation calls for mediation
2. **Coordinated Incentives**: Ensuring all steps of a multi-step solution are appropriately prioritized
3. **Strategic Guidance**: Understanding that some configurations are "stepping stones" to solutions rather than final states

The simplified approach successfully demonstrated that **primitive constraint satisfaction works**, but **emergent complex pattern discovery does not work** without pattern-specific guidance.

## Recommendation
Keep the mediation-specific logic in the algorithm. It's not "cheating" - it's providing the strategic pattern recognition necessary for discovering sophisticated security mechanisms that wouldn't emerge through random exploration alone.