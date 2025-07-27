# Primitive vs Multi-Step Transition Comparison

This document compares the exploration outcomes between using multi-step transitions vs primitive-only transitions for the same security scenario.

## Scenarios Compared

### 1. **basic_sharing** (Multi-Step Transitions)
- **Allowed Transitions**: `privatize_resource`, `add_mediator` (multi-step only)
- **Goals**: RSI[PD_1,PD_2] ≤ 0.3, TCB[PD_1] ≤ 0, ASR ≤ 1.0
- **Constraints**: Both PDs require HEAP access (min 3 pages)

### 2. **basic_sharing_primitive** (Primitive-Only Transitions)  
- **Allowed Transitions**: 6 primitive operations (add_pd, remove_pd, add_hold_edge, remove_hold_edge, add_request_edge, remove_request_edge)
- **Goals**: Identical to basic_sharing
- **Constraints**: Identical to basic_sharing

## Exploration Results

| Scenario | Iterations | Mechanisms Found | Final RSI | Final TCB[PD_1] | Final ASR | Goals Met |
|----------|------------|------------------|-----------|-----------------|-----------|-----------|
| **basic_sharing** | 1 | 1 | 0.000 | 0 | 4.0 | RSI ✅, TCB ✅, ASR ❌ |
| **basic_sharing_primitive** | 5 | 5 | 0.143 | 1 | 1.14 | RSI ✅, TCB ❌, ASR ❌ |

## Key Findings

### 1. **Effectiveness Comparison**

**Multi-Step (basic_sharing)**:
- ✅ **Solved core sharing problem**: Eliminated VMR_1_7 sharing (RSI: 0.143 → 0.000)
- ✅ **Achieved isolation**: TCB[PD_1] reduced to 0 (no dependencies)
- ✅ **Single focused transformation**: Applied `privatize_resource` directly addressing the sharing violation
- ❌ **ASR goal not met**: ASR remained at 4.0 > 1.0 target

**Primitive-Only (basic_sharing_primitive)**:
- ❌ **Failed to solve sharing**: VMR_1_7 still shared by PD_1, PD_2 (RSI unchanged at 0.143)
- ❌ **No isolation achieved**: TCB[PD_1] = 1 (still depends on PD_2)
- ✅ **ASR improvement**: ASR improved from 4.0 → 1.14 (approaching goal)
- ❓ **Ineffective strategy**: Only applied `add_pd` operations, creating 5 new empty PDs

### 2. **Strategic Differences**

**Multi-Step Strategy**:
```
Initial: PD_1 ←→ VMR_1_7 ←→ PD_2 (shared resource)
Final:   PD_1 → VMR_1_8, PD_2 → VMR_1_9 (private copies)
```

**Primitive Strategy**:
```
Initial: PD_1 ←→ VMR_1_7 ←→ PD_2 (shared resource)
Final:   PD_1 ←→ VMR_1_7 ←→ PD_2 + PD_3, PD_4, PD_5, PD_6, PD_7 (unchanged sharing + empty PDs)
```

### 3. **Limitations of Primitive-Only Approach**

1. **Missing Coordination**: Primitive operations lack the coordination needed for complex transformations
   - Removing shared HOLD edges without creating replacements would violate constraints
   - Adding new VMR resources requires multiple coordinated primitive steps
   - Constraint validation prevents incomplete transformations

2. **Greedy Selection Issues**: Primitive selection algorithm chose suboptimal transformations
   - `add_pd` scored highest (0.300) among available primitives
   - More impactful primitives like `remove_hold_edge` were not selected due to constraint violations
   - No mechanism to combine primitives into meaningful transformation sequences

3. **Constraint Enforcement**: Functional constraints prevented effective primitive application
   - Cannot remove PD_1 → VMR_1_7 edge without ensuring HEAP access requirement is met
   - Cannot add replacement resources without complex multi-step coordination

## Analysis and Implications

### **Multi-Step Transitions Are Essential**

The comparison clearly demonstrates that **multi-step transitions are necessary** for meaningful security transformations:

1. **Semantic Completeness**: Multi-step transitions encapsulate the full semantics of security patterns (privatization, mediation)
2. **Constraint Preservation**: Coordinated primitive sequences ensure functional requirements are maintained throughout transformation
3. **Direct Problem Solving**: Multi-step transitions directly address security violations rather than making tangential improvements

### **Primitive Limitations**

Primitive-only exploration suffers from fundamental limitations:

1. **No Strategic Coherence**: Individual primitives cannot express complex security transformations
2. **Constraint Deadlock**: Functional constraints prevent many primitive operations that would be safe in coordination
3. **Exploration Inefficiency**: Primitive selection leads to irrelevant transformations (adding empty PDs)

### **Architectural Insights**

This comparison validates the two-level transition architecture:

- **Primitive Level**: Provides building blocks for graph manipulation
- **Semantic Level**: Combines primitives into meaningful security transformations
- **Exploration Algorithm**: Benefits from semantic-level transformations that directly target security goals

## Conclusion

The primitive-only approach **cannot achieve the same outcomes** as multi-step transitions for complex security transformations. While primitives are essential building blocks, they require semantic-level coordination to address real security challenges effectively.

**Key Takeaway**: Multi-step transitions are not just a convenience—they are **architecturally necessary** for automated security mechanism discovery in complex systems.