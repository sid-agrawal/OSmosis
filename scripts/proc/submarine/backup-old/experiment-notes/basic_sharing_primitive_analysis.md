# Deep Analysis: basic_sharing_primitive Scenario

## Scenario Setup

### Goals (All must be achieved):
1. **RSI[PD_1,PD_2] ≤ 0.3** - Minimize sharing between PD_1 and PD_2
2. **TCB[PD_1] = 0** - PD_1 should have no entities in its trusted computing base
3. **ASR ≤ 1.0** - Minimize system-wide attack surface ratio

### Constraints (All must be satisfied):
1. **PD_1 needs CONFIG file access** (≥1KB)
2. **PD_2 needs DATABASE file access** (≥1KB)  
3. **PD_1 needs TEMP file access** (≥1KB)
4. **PD_2 needs TEMP file access** (≥1KB)

### Starting Graph:
```
PD_1 --HOLD--> FILE_1_1 (CONFIG, 4KB)
PD_1 --HOLD--> FILE_1_3 (TEMP, 2KB)    ← SHARED RESOURCE
PD_2 --HOLD--> FILE_1_2 (DATABASE, 8KB)
PD_2 --HOLD--> FILE_1_3 (TEMP, 2KB)    ← SHARED RESOURCE
```

### Initial Metrics:
- **RSI[PD_1,PD_2]: 0.333** > 0.3 ❌ (sharing FILE_1_3)
- **TCB[PD_1]: ['PD_2']** ≠ 0 ❌ (PD_2 in trusted base)
- **ASR: 2.0** > 1.0 ❌ (attack surface too high)

**Problem**: FILE_1_3 is the shared TEMP resource causing all three goals to fail.

## The Core Challenge

The algorithm needs to eliminate sharing of FILE_1_3 while maintaining TEMP file access for both PDs. This requires **resource specialization**.

## Optimal Solution

### Step 1: Create separate TEMP files
```bash
add_file_resource(FILE_1_4, TEMP, for_PD_1)  # Private TEMP for PD_1
add_file_resource(FILE_1_5, TEMP, for_PD_2)  # Private TEMP for PD_2
```

### Step 2: Establish specialized access
```bash
add_hold_edge(PD_1 → FILE_1_4)  # PD_1 uses private TEMP
add_hold_edge(PD_2 → FILE_1_5)  # PD_2 uses private TEMP
```

### Step 3: Remove shared resource access
```bash
remove_hold_edge(PD_1 → FILE_1_3)  # Remove shared access
remove_hold_edge(PD_2 → FILE_1_3)  # Remove shared access
```

### Step 4: Clean up (optional)
```bash
remove_file_resource(FILE_1_3)  # Remove unused shared resource
```

**Expected Final State:**
```
PD_1 --HOLD--> FILE_1_1 (CONFIG, 4KB)
PD_1 --HOLD--> FILE_1_4 (TEMP, 2KB)     ← PRIVATE
PD_2 --HOLD--> FILE_1_2 (DATABASE, 8KB)
PD_2 --HOLD--> FILE_1_5 (TEMP, 2KB)     ← PRIVATE
```

**Expected Metrics:**
- **RSI[PD_1,PD_2]: 0.0** ≤ 0.3 ✅ (no sharing)
- **TCB[PD_1]: []** = 0 ✅ (no trusted base)
- **ASR: 2.0** ≤ 1.0 ❌ (still needs optimization)

## Why Enhanced Balanced Scoring v2 Failed

Looking at the actual run results:

### What It Did:
```
Final paths: add_pd → add_pd → add_pd (created empty PDs)
Final scores: 0.330-0.337 (very low)
```

### What It Should Have Done:
```
Optimal path: add_file_resource → add_hold_edge → remove_hold_edge
Expected scores: 5.0+ (resource specialization)
```

### Root Cause Analysis:

#### 1. **No Resource Specialization Recognition**
```python
# Current scoring gives same bonus for any file creation
if operation.name == 'add_file_resource':
    bonus += 1.0  # Generic bonus
```

**Fix needed:**
```python
# Should recognize TEMP file creation for specialization
if operation.name == 'add_file_resource':
    if self._enables_resource_specialization(params, constraints):
        bonus += 5.0  # Major bonus for specialization
```

#### 2. **No Multi-Resource Coordination**
The algorithm doesn't understand that:
- Creating FILE_1_4 enables PD_1 to disconnect from FILE_1_3
- Creating FILE_1_5 enables PD_2 to disconnect from FILE_1_3
- Both are needed for complete specialization

#### 3. **Insufficient Remove Operation Scoring**
```python
# Current: remove_hold_edge gets base score only
return base_score  # 0.5
```

**Should be:**
```python
# If removing shared resource access after specialization
if self._removes_sharing_after_specialization(operation, graph):
    return 10.0  # Major bonus
```

#### 4. **Missing Goal Coordination**
The algorithm evaluates each goal independently:
- RSI improvement: Prioritizes removing shared access
- TCB improvement: Prioritizes removing dependencies  
- ASR improvement: Prioritizes reducing resources

But doesn't recognize that **resource specialization achieves all three goals simultaneously**.

## Specific Fixes for basic_sharing_primitive

### Fix 1: Resource Specialization Detection
```python
def _detect_resource_specialization_opportunity(self, graph, constraints):
    """Detect when shared resource can be specialized"""
    shared_resources = self._find_shared_resources(graph)
    opportunities = []
    
    for resource in shared_resources:
        holders = self._get_resource_holders(graph, resource)
        
        # Check if all holders need same resource type
        resource_type = self._get_resource_type(graph, resource)
        
        # Check if constraints allow specialization
        can_specialize = True
        for holder in holders:
            if not self._can_create_private_resource(holder, resource_type, constraints):
                can_specialize = False
                break
        
        if can_specialize:
            opportunities.append({
                'shared_resource': resource,
                'holders': holders,
                'resource_type': resource_type,
                'specialization_plan': self._generate_specialization_plan(holders, resource_type)
            })
    
    return opportunities
```

### Fix 2: Specialization-Aware Scoring
```python
def score_operation(self, operation, candidate, graph, goals, constraints):
    # ... existing scoring ...
    
    # Check for resource specialization patterns
    specialization_opportunities = self._detect_resource_specialization_opportunity(graph, constraints)
    
    if specialization_opportunities:
        for opp in specialization_opportunities:
            plan = opp['specialization_plan']
            
            # Score based on position in specialization plan
            if self._operation_advances_specialization(operation, candidate, plan):
                step_bonus = 10.0 - plan['current_step'] * 0.5
                pattern_score += step_bonus
                
                print(f"    ✓ Specialization step {plan['current_step']}: {operation.name}")
```

### Fix 3: Multi-Goal Coordination
```python
def _evaluate_multi_goal_impact(self, operation, candidate, old_graph, new_graph, goals):
    """Evaluate impact across all goals simultaneously"""
    
    # Check if operation helps multiple goals
    goal_improvements = []
    for goal in goals:
        improvement = self._calculate_goal_improvement(goal, old_graph, new_graph)
        goal_improvements.append(improvement)
    
    # Bonus for operations that help multiple goals
    positive_improvements = [imp for imp in goal_improvements if imp > 0]
    
    if len(positive_improvements) >= 2:
        # Major bonus for multi-goal operations
        return sum(positive_improvements) * 2.0
    elif len(positive_improvements) == 1:
        return sum(positive_improvements)
    else:
        return 0.0
```

## Testing the Fix

To test if these fixes work, the algorithm should:

1. **Iteration 1**: Create FILE_1_4 (TEMP for PD_1) - Score: ~10.0
2. **Iteration 2**: Create FILE_1_5 (TEMP for PD_2) - Score: ~10.0  
3. **Iteration 3**: Connect PD_1 to FILE_1_4 - Score: ~8.0
4. **Iteration 4**: Connect PD_2 to FILE_1_5 - Score: ~8.0
5. **Iteration 5**: Remove PD_1 → FILE_1_3 - Score: ~15.0
6. **Iteration 6**: Remove PD_2 → FILE_1_3 - Score: ~15.0

**Expected Final Metrics:**
- RSI[PD_1,PD_2]: 0.0 ≤ 0.3 ✅
- TCB[PD_1]: [] = 0 ✅  
- ASR: 2.0 ≤ 1.0 ❌ (may need additional optimization)

## Key Insight

The basic_sharing_primitive scenario fails because **resource specialization** is a **4-6 step coordinated pattern**, not individual operations. The scoring system needs to:

1. **Recognize** resource specialization opportunities
2. **Plan** the complete specialization sequence
3. **Score** individual operations based on their role in the sequence
4. **Coordinate** across multiple goals simultaneously

This is fundamentally a **pattern recognition and multi-step planning problem**, not a constraint satisfaction problem.