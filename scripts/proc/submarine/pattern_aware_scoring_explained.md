# Pattern-Aware Scoring: A Deep Dive

## 1. High-Level Description of score_operation Function

The `score_operation` function in `pattern_aware_scoring.py` is the heart of the submarine system's intelligent exploration. It analyzes the current graph state, recognizes security patterns, and assigns scores to guide the search toward promising transformations.

### Core Philosophy

The scoring system operates on a **hierarchical priority model**:
- **Constraint Compliance** (3.0): Absolute priority for fixing violations
- **Pattern Establishment** (2.5-2.9): Creating key security patterns
- **Pattern Completion** (1.0-1.8): Finishing partially established patterns
- **Infrastructure Building** (0.2-1.5): Creating necessary components

### Conceptual Flow

```
Graph State → Pattern Recognition → Context-Aware Scoring → Prioritized Selection
```

### Pseudocode Overview

```python
def score_operation(operation, candidate, graph, goals, constraints):
    """
    Main scoring function that combines multiple intelligence layers
    """
    # 1. Start with base score from operation type
    base_score = get_base_score(operation.name)  # 0.1 - 1.0
    
    # 2. Analyze current graph for pattern opportunities
    state_analysis = analyze_graph_state(graph)
    # Returns: orphaned_resources, shared_resources, mediation_opportunities, etc.
    
    # 3. Extract operation parameters
    params = extract_parameters(candidate)
    
    # 4. Apply hierarchical scoring layers
    score = apply_pattern_scoring(
        operation, params, base_score, state_analysis, 
        graph, constraints, goals
    )
    
    # 5. Track operation history for sequence detection
    update_operation_history(operation, params)
    
    return score
```

### Detailed Pattern Scoring Logic

```python
def apply_pattern_scoring(operation, params, base_score, state_analysis, 
                         graph, constraints, goals):
    """
    Apply multiple layers of pattern-aware scoring
    """
    score = base_score
    
    # LAYER 1: Constraint Violations (Highest Priority)
    if operation == "remove_hold_edge":
        if is_prohibited_edge(params.from_node, params.to_node, constraints):
            return 3.0  # MAXIMUM PRIORITY - constraint compliance
    
    # LAYER 2: Pattern Recognition
    # 2A. Mediation Pattern
    if state_analysis.has_orphaned_resources and state_analysis.has_access_needs:
        if operation == "add_pd":
            score = 1.5  # Create mediator infrastructure
        
        elif operation == "add_hold_edge":
            if params.to_node in state_analysis.orphaned_resources:
                if is_constraint_mentioned(params.to_node):
                    score = 3.0  # Connect mediator to critical resource
                else:
                    score = 2.5  # Connect mediator to orphaned resource
        
        elif operation == "add_request_edge":
            if mediator_ready_for_requests(graph):
                score = 1.8  # Complete mediation pattern
    
    # 2B. Sharing Reduction Pattern
    if state_analysis.has_shared_resources and has_rsi_goals(goals):
        if operation == "remove_hold_edge":
            if params.to_node in state_analysis.shared_resources:
                score = 2.8  # Remove sharing
        
        elif operation == "add_hold_edge":
            if params.to_node in state_analysis.shared_resources:
                score = base_score * 0.1  # PENALTY for increasing sharing
            elif is_private_alternative(params.from_node, params.to_node):
                score = 2.9  # Private alternative to shared resource
    
    # LAYER 3: Sequence Recognition
    if recent_operations_were("remove_hold_edge", "remove_hold_edge"):
        if operation == "add_pd":
            score += 0.5  # Boost infrastructure after constraint removal
    
    # LAYER 4: Constraint-Driven Adjustments
    if operation == "add_request_edge":
        if helps_access_constraint(params.from_pd, params.to_pd, constraints):
            score += 0.8  # Helps satisfy access requirements
    
    return score
```

## 2. How Parameter Binding Works

Parameter binding is the process of connecting abstract operation templates with concrete graph elements. It's crucial for transforming high-level operations into specific graph modifications.

### The Parameter Binding Flow

```
Operation Template → Candidate Generation → Parameter Extraction → Transformation Application
```

### Step 1: Operation Templates Define Parameters

Each operation in the submarine system defines required parameters:

```python
class AddHoldEdgeTransition:
    def __init__(self):
        self.required_params = ['from_node', 'to_node']
        self.param_types = {
            'from_node': 'PD',
            'to_node': 'RESOURCE'
        }
```

### Step 2: Candidate Generation with find_candidates()

The `find_candidates()` method (in isosearch.py) discovers all valid parameter bindings:

```python
def find_candidates(graph, constraints):
    """
    Find all valid ways to apply this operation to the graph
    """
    candidates = []
    
    # Find all PDs that could be 'from_node'
    pds = get_all_nodes_of_type(graph, 'PD')
    
    # Find all resources that could be 'to_node'
    resources = get_all_nodes_of_type(graph, 'RESOURCE')
    
    # Generate all valid combinations
    for pd in pds:
        for resource in resources:
            # Check if this binding would be valid
            if not already_connected(pd, resource):
                candidate = {
                    'param_values': {
                        'from_node': pd,
                        'to_node': resource
                    },
                    'target_description': f"connect {pd} to {resource}",
                    'constraint_relevance': calculate_relevance(pd, resource, constraints)
                }
                candidates.append(candidate)
    
    return candidates
```

### Step 3: Parameter Extraction in Scoring

The scoring function extracts parameters with backward compatibility:

```python
def extract_parameters(candidate):
    """
    Extract parameters handling both old and new formats
    """
    if isinstance(candidate, dict):
        # New format: parameters in 'param_values'
        params = candidate.get('param_values', {})
        
        # Backward compatibility: also check direct keys
        if not params:
            params = {k: v for k, v in candidate.items() 
                     if k not in ['target_description', 'predicted_improvement']}
    
    # Handle parameter naming conventions
    # Old: 'pd', 'resource'
    # New: 'from_node', 'to_node'
    normalized_params = {}
    normalized_params['from_node'] = params.get('from_node') or params.get('pd')
    normalized_params['to_node'] = params.get('to_node') or params.get('resource')
    
    return normalized_params
```

### Step 4: Transformation Application

When selected, the operation applies the transformation using bound parameters:

```python
def apply(graph, param_values):
    """
    Apply the transformation with concrete parameter values
    """
    from_node = param_values['from_node']
    to_node = param_values['to_node']
    
    # Perform the actual graph modification
    graph.add_edge(from_node, to_node, type='HOLD')
    
    return True  # Success
```

### Complete Example: Mediation Discovery

Let's trace parameter binding through mediation discovery:

```python
# 1. Initial state: FILE_1_3 is orphaned (no holders)

# 2. Candidate generation for add_hold_edge
candidates = [
    {
        'param_values': {'from_node': 'PD_1', 'to_node': 'FILE_1_3'},
        'target_description': 'connect PD_1 to orphaned resource FILE_1_3',
        'constraint_relevance': 0.9  # High - mentioned in constraints
    },
    {
        'param_values': {'from_node': 'PD_3', 'to_node': 'FILE_1_3'},
        'target_description': 'connect PD_3 to orphaned resource FILE_1_3',
        'constraint_relevance': 0.9
    }
]

# 3. Scoring evaluates each candidate
for candidate in candidates:
    params = candidate['param_values']
    
    # PD_1 is original, can't be mediator
    if params['from_node'] == 'PD_1':
        score = 1.5  # Good but not ideal
    
    # PD_3 is new, perfect mediator
    elif params['from_node'] == 'PD_3':
        score = 3.0  # Maximum - mediator to constraint resource

# 4. Selection and application
best_candidate = candidates[1]  # PD_3 → FILE_1_3
apply_transformation(graph, best_candidate['param_values'])
# Result: PD_3 now holds FILE_1_3, establishing mediation
```

### Key Insights on Parameter Binding

1. **Abstraction**: Operations define abstract parameter templates
2. **Discovery**: find_candidates() discovers all valid concrete bindings
3. **Scoring**: Each candidate binding is scored based on its context
4. **Selection**: The highest-scoring binding is selected
5. **Application**: The concrete parameters are used to modify the graph

This separation of concerns allows the system to:
- Define operations generically
- Discover possibilities dynamically
- Score based on context
- Apply transformations systematically