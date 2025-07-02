# High Sharing Scenario Analysis

## Overview
The High Resource Sharing scenario demonstrates algorithm behavior when faced with complex shared resource patterns that require significant structural changes to meet goals.

## Starting Graph Structure
- **Nodes**: 7 (3 PDs + 1 resource space + 3 file resources)
- **Edges**: 10 
- **Key Pattern**: Heavy file sharing across all PDs
  - FILE_1_1 shared by: PD_1, PD_2, PD_3 (3-way sharing)
  - FILE_1_2 shared by: PD_1, PD_2 (2-way sharing)
  - FILE_1_3 shared by: PD_2, PD_3 (2-way sharing)

## Initial Metrics
- **RSI**: PD_1,PD_2=0.667, PD_1,PD_3=0.333, PD_2,PD_3=0.667
- **ASR**: 2.33 (high attack surface)
- **TCB**: All PDs mutually dependent due to sharing

## Goals
1. Minimize RSI[PD_1,PD_2] to 0.2
2. Minimize ASR to 2.0  
3. Minimize TCB[PD_1] to 1

## Exploration Path Taken
The algorithm consistently selected **primitive: add_pd** transitions across all 5 iterations:
1. **Iteration 1**: Added PD_4 → ASR improved from 2.33 to 1.75
2. **Iteration 2**: Added PD_5 → ASR improved to 1.4
3. **Iteration 3**: Added PD_6 → ASR improved to 1.17
4. **Iteration 4**: Added PD_7 → ASR improved to 1.0
5. **Iteration 5**: Added PD_8 → ASR improved to 0.875

## Final Results
- **RSI**: PD_1,PD_2 remained at 0.667 (goal not met)
- **ASR**: Reduced to 0.875 (goal exceeded: 0.875 < 2.0)
- **TCB**: PD_1 still dependent on [PD_2, PD_3] (goal not met)
- **Mechanisms Found**: 5

## Key Algorithmic Insights Demonstrated

### 1. Greedy Optimization Strategy
The algorithm demonstrated pure greedy selection, consistently choosing `add_pd` because it provided the most immediate ASR improvement (0.300 per iteration).

### 2. Single-Metric Focus
Despite multiple goals, the algorithm focused primarily on ASR optimization, showing how greedy selection can get "trapped" optimizing one metric while ignoring others.

### 3. Structural Limitation Recognition
The algorithm correctly identified that adding isolated PDs improves ASR but doesn't address the core sharing problem between existing PDs.

### 4. Predictable Convergence
Each iteration showed identical predicted improvement (0.300), demonstrating algorithmic consistency in candidate evaluation.

## Paths Discarded and Why
- **No alternatives considered**: Each iteration showed only one candidate, indicating the algorithm's transition space was limited by constraints
- **Missing transitions**: The scenario lacked sharing-reduction transitions (like `privatize_resource` or `add_mediator`) that could address the RSI goals
- **Constraint limitations**: Available transitions couldn't modify the existing sharing relationships that were causing goal violations

## Critical Analysis
This scenario reveals a key limitation: when the available transition set doesn't include operations that can address the primary bottlenecks (shared resources), the algorithm can only optimize secondary metrics. The consistent RSI[PD_1,PD_2]=0.667 across all iterations shows that adding isolated PDs doesn't reduce sharing between existing PDs.

## Algorithmic Behavior Patterns
1. **Monotonic improvement**: ASR steadily decreased with each new PD
2. **Goal prioritization**: ASR goal was achievable and got optimized first
3. **Constraint adherence**: All new PDs remained isolated to avoid violating constraints
4. **Termination condition**: Stopped after 5 iterations despite unmet goals (iteration limit)