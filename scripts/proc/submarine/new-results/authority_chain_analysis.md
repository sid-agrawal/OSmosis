# Authority Chain Scenario Analysis

## Overview
The Authority Chain scenario tests fault radius (FR) optimization in hierarchical authority structures, demonstrating how the algorithm handles infinite fault radius constraints.

## Starting Graph Structure
- **Nodes**: 8 (4 PDs + 1 resource space + 3 file resources)
- **Edges**: 9
- **Key Pattern**: Linear authority chain
  - PD_1 → PD_2 → PD_3 → PD_4 (REQUEST chain)
  - Each PD holds one unique file resource

## Initial Metrics
- **RSI**: All pairs = 0.0 (no resource sharing)
- **ASR**: 1.5 (already near goal of 1.5)
- **TCB**: Linear dependencies: PD_1→[PD_2], PD_2→[PD_3], PD_3→[PD_4]
- **FR**: PD_1,PD_4 = ∞ (no communication path), others finite

## Goals
1. Minimize FR[PD_1,PD_4] to 3
2. Minimize TCB[PD_1] to 2
3. Minimize ASR to 1.5

## Exploration Path Taken
Similar to high_sharing, consistent **primitive: add_pd** selection:
1. **Iteration 1**: Added PD_5 → ASR: 1.5 → 1.2
2. **Iteration 2**: Added PD_6 → ASR: 1.2 → 1.0  
3. **Iteration 3**: Added PD_7 → ASR: 1.0 → 0.857
4. **Iteration 4**: Added PD_8 → ASR: 0.857 → 0.75
5. **Iteration 5**: Added PD_9 → ASR: 0.75 → 0.667

## Final Results
- **FR[PD_1,PD_4]**: Remained ∞ (goal not met)
- **TCB[PD_1]**: Remained [PD_2] (goal met: 1 ≤ 2)
- **ASR**: Reduced to 0.667 (goal exceeded)
- **Mechanisms Found**: 5

## Key Algorithmic Insights Demonstrated

### 1. Infinite Metric Handling
The algorithm correctly handled infinite fault radius values without crashing, but couldn't find transitions to address the infinite FR[PD_1,PD_4].

### 2. Alternative Consideration
Unlike high_sharing, this scenario showed **discarded alternatives**:
- Each iteration considered 3 candidates total
- Consistently discarded: "remove PD_2→FILE_1_2 HOLD edge" and "remove PD_3→FILE_1_3 HOLD edge"
- Both discarded options had same predicted improvement (0.300) as selected option

### 3. Conservative Selection Strategy
Despite equivalent predicted improvements, the algorithm preferred `add_pd` over `remove_hold_edge`, suggesting a bias toward additive rather than subtractive modifications.

### 4. Structural Invariant Preservation
The core authority chain PD_1→PD_2→PD_3→PD_4 remained unchanged, preserving the constraint-required communication paths.

## Paths Discarded and Why

### Consistently Discarded Options
- **remove PD_2→FILE_1_2 HOLD edge**: Would eliminate PD_2's resource access
- **remove PD_3→FILE_1_3 HOLD edge**: Would eliminate PD_3's resource access

### Rationale for Discarding
While these had equal predicted improvement (0.300), the algorithm likely discarded them because:
1. **Constraint risk**: Removing file access could violate requirements
2. **Conservative preference**: Adding resources safer than removing them
3. **Tie-breaking strategy**: When improvements are equal, prefer additive operations

## Critical Analysis

### Fundamental Problem
The infinite FR[PD_1,PD_4] stems from the lack of direct or indirect communication path. The available transitions couldn't establish such a path because:
- `add_request_edge` was available but never selected
- Algorithm didn't recognize that adding PD_1→PD_4 or intermediate connections could resolve the infinite FR

### Missing Strategy
The algorithm needed to consider adding REQUEST edges to create alternative communication paths, but the candidate generation didn't prioritize this high-impact but structurally complex solution.

## Algorithmic Behavior Patterns
1. **Metric tunneling**: Focused on easily optimizable ASR while ignoring harder FR problem
2. **Risk aversion**: Preferred safe additive operations over potentially disruptive removals
3. **Alternative awareness**: Showed sophisticated candidate comparison (unlike high_sharing)
4. **Systematic exploration**: Consistent evaluation methodology across iterations
5. **Constraint preservation**: Maintained required communication structure throughout