# Proposed Solutions for Architectural Pattern Discovery

## 1. Lookahead Search with Rollback

The most direct solution is to explore sequences of primitives before committing:

```python
def evaluate_with_lookahead(graph, primitives, depth=4):
    """
    Explore primitive sequences up to 'depth' moves ahead
    """
    sequences = []
    
    # Generate all possible sequences up to depth
    for sequence in generate_sequences(primitives, depth):
        # Simulate the sequence
        temp_graph = deep_copy(graph)
        sequence_valid = True
        
        for primitive in sequence:
            if not can_apply(primitive, temp_graph):
                sequence_valid = False
                break
            apply_primitive(temp_graph, primitive)
        
        if sequence_valid:
            # Score the final state
            final_score = evaluate_state(temp_graph, goals)
            sequences.append((sequence, final_score))
    
    # Return best sequence
    return max(sequences, key=lambda x: x[1])
```

**Advantages:**
- Can discover patterns requiring multiple setup moves
- Doesn't require pre-encoded knowledge
- Maintains primitive composability

**Challenges:**
- Exponential search space (12 primitives ^ 4 depth = 20,736 combinations)
- Need pruning strategies
- Higher computational cost

## 2. Architectural Hints System

Add a hint system that recognizes architectural opportunities:

```python
class ArchitecturalHints:
    @staticmethod
    def get_hints(graph, goals):
        hints = []
        
        # Detect sharing violations
        shared_resources = find_shared_resources(graph)
        if shared_resources and has_rsi_goal(goals):
            hints.append({
                'pattern': 'mediation_opportunity',
                'boost_operations': [
                    ('add_pd', 0.5),          # Boost PD creation
                    ('add_request_edge', 0.3)  # Boost REQUEST edges
                ],
                'reason': 'Shared resources could benefit from mediation'
            })
        
        return hints

def apply_hints_to_scoring(base_score, operation, hints):
    """Modify primitive scores based on architectural hints"""
    score = base_score
    
    for hint in hints:
        for op, boost in hint['boost_operations']:
            if operation.name == op:
                score += boost
                
    return score
```

**Advantages:**
- Maintains primitive autonomy while guiding toward patterns
- Can be learned/tuned based on successful discoveries
- Low computational overhead

**Challenges:**
- Requires encoding some pattern knowledge
- May bias exploration

## 3. Compositional Primitives

Create higher-level compositional primitives that maintain atomicity while enabling patterns:

```python
COMPOSITIONAL_PRIMITIVES = {
    "create_mediator_structure": {
        "description": "Create PD with REQUEST relationships",
        "parameters": ["pd_type", "connected_pds"],
        "composed_of": [
            "add_pd",
            "add_request_edge",  # For each connected PD
        ],
        "atomic": True
    },
    
    "transfer_resource_control": {
        "description": "Transfer resource from one PD to another",
        "parameters": ["resource", "from_pd", "to_pd"],
        "composed_of": [
            "remove_hold_edge",
            "add_hold_edge"
        ],
        "atomic": True
    }
}
```

**Advantages:**
- Reduces steps needed for patterns (6 → 3)
- Maintains primitive philosophy
- Discoverable through normal exploration

**Challenges:**
- Increases primitive vocabulary
- Risk of over-specialization

## 4. Goal-Directed Planning

Add planning intelligence that works backward from goals:

```python
class GoalPlanner:
    def plan_for_rsi_reduction(self, graph, target_rsi):
        """
        Work backward from RSI goal to identify strategies
        """
        strategies = []
        
        # Strategy 1: Privatization
        shared = find_shared_resources(graph)
        privatization_steps = len(shared) * 3  # Build, connect, remove
        strategies.append({
            'name': 'privatization',
            'estimated_steps': privatization_steps,
            'first_move': 'add_file_resource'
        })
        
        # Strategy 2: Mediation
        if len(shared) <= 2:  # Mediation works well for focused sharing
            mediation_steps = 6  # Fixed pattern
            strategies.append({
                'name': 'mediation',
                'estimated_steps': mediation_steps,
                'first_move': 'add_pd'
            })
        
        return strategies
```

Then bias primitive selection toward planned strategies:

```python
def score_with_planning(primitive, graph, goals, active_strategy):
    base_score = calculate_base_score(primitive, graph, goals)
    
    if active_strategy and primitive.name == active_strategy['first_move']:
        return base_score + 0.5  # Boost planned moves
    
    return base_score
```

## 5. Learning from Multi-Step Decomposition

Analyze successful multi-step transitions to learn scoring patterns:

```python
def learn_from_multistep(multistep_transition, graph, goals):
    """
    Decompose successful multi-step transitions to learn scoring
    """
    initial_metrics = compute_metrics(graph)
    temp_graph = deep_copy(graph)
    
    step_scores = []
    for i, primitive in enumerate(multistep_transition.primitives):
        apply_primitive(temp_graph, primitive)
        metrics = compute_metrics(temp_graph)
        
        # Record how metrics evolved
        step_scores.append({
            'step': i,
            'primitive': primitive.name,
            'metric_delta': metrics - initial_metrics,
            'distance_to_goal': distance_to_goals(metrics, goals)
        })
    
    # Learn pattern: "These primitives in sequence achieve goals"
    return step_scores
```

## 6. Hybrid Approach: Staged Exploration

Combine multiple strategies in stages:

```python
class StagedExploration:
    def explore(self, graph, goals, transitions):
        # Stage 1: Try primitives with normal scoring (fast)
        result = explore_primitives(graph, goals, max_iterations=3)
        
        if goals_met(result):
            return result
            
        # Stage 2: Try with hints and lookahead (medium cost)
        hints = ArchitecturalHints.get_hints(graph, goals)
        result = explore_with_hints(graph, goals, hints, lookahead=2)
        
        if goals_met(result):
            return result
            
        # Stage 3: Try multi-step transitions (when available)
        result = explore_multistep(graph, goals, transitions)
        
        return result
```

## Recommended Implementation Path

I suggest starting with **Option 2 (Architectural Hints)** because:

1. **Lowest implementation complexity** - Just modify scoring
2. **Preserves primitive autonomy** - No new primitive types
3. **Tunable** - Can adjust hint strength
4. **Extensible** - Can add more hint patterns

Here's a concrete implementation:

```python
def _predict_improvement(self, transition, candidate, graph, goals):
    # Existing base score
    base_score = self._get_base_score(transition)
    
    # Architectural hint system
    if transition == "add_pd":
        shared_resources = self._find_shared_resources(graph)
        if shared_resources and self._has_rsi_goal(goals):
            base_score += 0.5  # Significant boost
            
    elif transition == "add_request_edge":
        # Check if we recently added a PD (potential mediator)
        recent_pds = self._find_unconnected_pds(graph)
        if recent_pds and self._has_rsi_goal(goals):
            base_score += 0.3
            
    elif transition == "remove_hold_edge":
        # Check if target PD has REQUEST relationship
        if self._has_request_alternative(candidate, graph):
            base_score = 1.0  # Maximum score
    
    # Rest of existing implementation...
    return base_score
```

This would allow primitives to discover mediation while maintaining their autonomous nature.

## Alternative: Accept the Limitation

Another valid approach is to **accept that some patterns require encoding**:

1. Primitives handle emergent, novel solutions
2. Multi-step transitions handle known architectural patterns
3. Document which patterns are discoverable vs. encoded

This maintains system simplicity while being honest about capabilities.

What approach resonates most with your vision for the system?