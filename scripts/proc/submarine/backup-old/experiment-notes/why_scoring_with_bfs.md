# Why Do We Need Scoring with Beam Search (Limited BFS)?

## The Key Insight: Beam Search ≠ Full BFS

### What We're Actually Doing
```python
# Beam Search (LIMITED BFS)
beam_width = 3  # Only keep top 3 paths
for iteration in range(max_iterations):
    next_beam = []
    for state in current_beam:
        candidates = generate_candidates(state)  # Could be 20-30 candidates!
        next_beam.extend(candidates)
    # CRITICAL: We must SELECT which paths to keep
    current_beam = sorted(next_beam, key=score)[:beam_width]  # SCORING REQUIRED HERE
```

### If We Did Full BFS (No Scoring Needed)
```python
# TRUE BFS - Explore ALL paths
queue = [initial_state]
while queue:
    state = queue.pop(0)
    candidates = generate_candidates(state)
    queue.extend(candidates)  # Keep ALL candidates
    # No scoring needed - we explore everything!
```

## The Combinatorial Explosion Problem

### Example from mediator_test_indirect
At each state, we might have:
- 12 primitive operations available
- 10-30 valid parameter combinations per operation
- **Total: 120-360 candidates per state**

After just 3 iterations:
- Iteration 1: 200 candidates
- Iteration 2: 200 × 200 = 40,000 states
- Iteration 3: 40,000 × 200 = 8,000,000 states
- **Memory/computation becomes infeasible**

## Why Beam Search Needs Scoring

### 1. Path Selection Problem
```
Current beam has 3 states
Each state generates 30 candidates
Total: 90 candidates
Must select: top 3 for next beam
Question: WHICH 3? → Need scoring!
```

### 2. The Scoring Determines Everything
```python
# With current scoring:
Beam iteration 3 candidates:
- add_file_resource: score 0.9 ✅ (selected)
- add_pd: score 0.7 ✅ (selected)  
- connect_to_orphaned: score 0.4 ❌ (discarded)
- add_request_edge: score 0.3 ❌ (discarded)

# Result: Mediation path is DISCARDED, not explored
```

### 3. Beam Search Trade-offs
- **Full BFS**: Explores all paths, finds optimal, computationally infeasible
- **Greedy**: Explores 1 path, computationally cheap, misses optimal solutions
- **Beam Search**: Explores K paths, balanced trade-off, **but which K paths?**

## The Fundamental Issue

### Current Scoring System Failure
```
State: PD_3 created, FILE_1_3 orphaned
Next step options:
1. Connect PD_3 to FILE_1_3 (mediation path) - Score: 0.4
2. Create new file - Score: 0.9
3. Create another PD - Score: 0.7

Beam width = 3, so we keep all... BUT in next iteration:
From option 1: Add REQUEST edges (0.3) - CRITICAL FOR MEDIATION
From option 2: More file operations (0.6-0.9)
From option 3: More PD operations (0.7)

The REQUEST edge path gets eliminated!
```

### What Perfect Scoring Would Do
```
State: PD_3 created, FILE_1_3 orphaned
Scoring recognizes: "This is step 3/5 of mediation pattern"
Adjusts scores:
1. Connect PD_3 to FILE_1_3 - Score: 2.0 (pattern continuation)
2. Create new file - Score: 0.1 (doesn't help pattern)
3. Create another PD - Score: 0.1 (doesn't help pattern)
```

## Alternative: True BFS Without Scoring?

### Option 1: Full BFS
```python
def true_bfs_exploration(scenario):
    queue = [initial_state]
    visited = set()
    
    while queue:
        state = queue.pop(0)
        if goals_met(state):
            save_mechanism(state)
        
        for candidate in generate_all_candidates(state):
            new_state = apply(state, candidate)
            if new_state not in visited:
                queue.append(new_state)
                visited.add(new_state)
```
**Problem**: Exponential explosion, runs out of memory

### Option 2: Depth-Limited BFS
```python
def depth_limited_bfs(scenario, max_depth=5):
    # Explore all paths up to depth 5
    # More feasible but still exponential
```
**Problem**: Still exponential within depth limit

### Option 3: Iterative Deepening
```python
def iterative_deepening(scenario):
    for depth in range(1, max_depth):
        if dfs_to_depth(initial_state, depth):
            return solution
```
**Problem**: Repeatedly explores shallow states

## Conclusion: Scoring is Essential for Beam Search

1. **Beam search is NOT full BFS** - it's a heuristic search that explores K most promising paths
2. **Scoring determines which paths survive** - bad scoring = good paths discarded
3. **Without scoring, we'd need full BFS** - computationally infeasible
4. **The scoring system IS the intelligence** - it encodes what paths are worth exploring

### The Real Question
Not "Why do we need scoring?" but "How do we make scoring smart enough to recognize that lower-scoring intermediate steps lead to better final solutions?"

### Current Reality
```
Beam Search: ✅ (Can explore multiple paths)
Scoring System: ❌ (Discards mediation path for higher local scores)
Result: Mediation patterns never discovered
```

### What We Need
**Pattern-aware scoring** that recognizes:
- Multi-step sequences
- Intermediate states that enable final solutions  
- Global optimization over local optimization