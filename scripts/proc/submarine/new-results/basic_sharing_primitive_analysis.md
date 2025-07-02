# Basic Sharing Primitive Scenario - Exploration Analysis

## Scenario Overview
**Name**: Basic Resource Sharing (Primitive Only)  
**Description**: Same simplified scenario as basic_sharing (1 private file + 1 shared file per PD) but using only primitive transitions  
**Goal**: Demonstrate primitive-only approach limitations and contrast with multi-step effectiveness  

## Goals and Constraints

### Goals (3):
1. **RSI[PD_1,PD_2] ≤ 0.3** - Minimize resource sharing between user process and database server
2. **TCB[PD_1] ≤ 0** - Eliminate trusted computing base dependencies for user process
3. **ASR ≤ 1.0** - Reduce attack surface ratio

### Constraints (2):
1. **PD_1**: Must have access to FILE resources with `file_type: CONFIG, min_size_kb: 1`
2. **PD_2**: Must have access to FILE resources with `file_type: DATABASE, min_size_kb: 1`

## Starting Graph Structure

**Nodes**: 5 total (2 PDs, 1 FILE_SPACE, 2 private FILE resources + 1 shared FILE resource)  
**Edges**: 6 total (4 HOLD edges, 3 SUBSET edges)

### Protection Domains:
- **PD_1** (user_process): Accesses FILE_1_1, FILE_1_3
- **PD_2** (database_server): Accesses FILE_1_2, FILE_1_3

### File Resources:
- **FILE_1_1**: `/etc/user.conf` (CONFIG, 4KB) - Private to PD_1
- **FILE_1_2**: `/var/db/main.db` (DATABASE, 8KB) - Private to PD_2
- **FILE_1_3**: `/tmp/shared_buffer.tmp` (TEMP, 2KB) - **SHARED by PD_1 and PD_2**

### Initial Metrics:
- **RSI[PD_1,PD_2]**: 0.333 (1 shared resource out of 3 total resources)
- **ASR**: 4.0 (attack surface spread across 2 PDs)
- **TCB[PD_1]**: [PD_2] (depends on PD_2 due to shared resource)
- **TCB[PD_2]**: [PD_1] (depends on PD_1 due to shared resource)

## Exploration Path

### Available Primitive Transitions (9):
1. **add_pd**: Create new Protection Domain
2. **remove_pd**: Remove existing Protection Domain
3. **add_hold_edge**: Create PD → Resource relationship
4. **remove_hold_edge**: Remove PD → Resource relationship
5. **add_request_edge**: Create PD → PD authority relationship
6. **remove_request_edge**: Remove PD → PD authority relationship
7. **clone_file_resource**: Create private copy of existing FILE resource
8. **replace_hold_edge**: Atomically replace HOLD edge target resource
9. **create_private_copy**: Create private FILE copy for specific PD

### All Iterations (1-5): Repetitive PD Addition

**Selected Transition**: `add_pd` (consistently chosen across all iterations)  
**Predicted Improvement**: 0.300 (constant for all iterations)  
**Competing Candidates**: None (no alternatives considered)

#### Iteration 1: Add PD_3
**Action**: Created empty PD_3 with no resource connections  
**Metrics**: RSI[PD_1,PD_2] = 0.333 (unchanged), ASR = 2.67 (improved: 4.0→2.67), TCB[PD_1] = [PD_2] (unchanged)  
**Progress**: ASR improvement only, core sharing problem unaddressed

#### Iteration 2: Add PD_4  
**Action**: Created empty PD_4 with no resource connections  
**Metrics**: RSI[PD_1,PD_2] = 0.333 (unchanged), ASR = 2.0 (improved: 2.67→2.0), TCB[PD_1] = [PD_2] (unchanged)  
**Progress**: Continued ASR improvement, sharing violation persists

#### Iteration 3: Add PD_5
**Action**: Created empty PD_5 with no resource connections  
**Metrics**: RSI[PD_1,PD_2] = 0.333 (unchanged), ASR = 1.6 (improved: 2.0→1.6), TCB[PD_1] = [PD_2] (unchanged)  
**Progress**: Approaching ASR goal (1.6 → 1.0), primary isolation problem unresolved

#### Iteration 4: Add PD_6
**Action**: Created empty PD_6 with no resource connections  
**Metrics**: RSI[PD_1,PD_2] = 0.333 (unchanged), ASR = 1.33 (improved: 1.6→1.33), TCB[PD_1] = [PD_2] (unchanged)  
**Progress**: Near ASR goal, resource sharing unchanged

#### Iteration 5: Add PD_7
**Action**: Created empty PD_7 with no resource connections  
**Metrics**: RSI[PD_1,PD_2] = 0.333 (unchanged), ASR = 1.14 (improved: 1.33→1.14), TCB[PD_1] = [PD_2] (unchanged)  
**Progress**: Close to ASR goal (1.14 vs 1.0 target), core problem unaddressed

## Final Graph Structure

**Nodes**: 10 total (7 PDs, 1 FILE_SPACE, 3 FILE resources)  
**Edges**: 6 total (4 HOLD edges, 3 SUBSET edges - no new edges added)

### Protection Domains:
- **PD_1** (user_process): Accesses FILE_1_1, FILE_1_3 (**unchanged**)
- **PD_2** (database_server): Accesses FILE_1_2, FILE_1_3 (**unchanged**)
- **PD_3, PD_4, PD_5, PD_6, PD_7**: Empty domains with no resource connections

### Key Observations:
- **Shared resource persists**: FILE_1_3 still shared between PD_1 and PD_2
- **No structural changes**: Original security violation unchanged
- **Resource bloat**: Added 5 empty PDs with no functional purpose

## Paths Taken vs. Discarded

### Paths Taken:
1. **All Iterations (1-5)**: `add_pd` primitive
   - **Rationale**: Only available candidate (other primitives not triggered)
   - **Outcome**: Progressive ASR improvement but core problem unresolved

### Paths Discarded:
**None** - No alternatives were generated or considered in any iteration

### Critical Missing Paths:
1. **remove_hold_edge**: Could disconnect shared resource access
2. **clone_file_resource**: Could create private copies
3. **create_private_copy**: Could address sharing directly
4. **replace_hold_edge**: Could redirect to private resources

**Why Missing**: Primitive candidate generation lacks constraint-violation analysis that would identify sharing-resolution opportunities

## Algorithm Capabilities Demonstrated

### 1. **Primitive Limitation Exposure**
- **Capability**: Shows inadequacy of basic primitives for complex problems
- **Evidence**: 5 iterations failed to address core sharing violation
- **Implication**: Need for enhanced primitive generation or multi-step approaches

### 2. **Partial Progress Achievement**
- **Capability**: Makes incremental improvements where possible
- **Evidence**: ASR improved from 4.0 to 1.14 (approaching goal of 1.0)
- **Implication**: Algorithm can optimize secondary metrics while primary problems persist

### 3. **Consistent Strategy Execution**
- **Capability**: Maintains coherent approach across iterations
- **Evidence**: Exclusively selected `add_pd` when available
- **Implication**: Deterministic behavior in limited candidate environments

### 4. **Constraint Preservation Under Limitations**
- **Capability**: Respects functional requirements even when ineffective
- **Evidence**: Maintained FILE access requirements despite making no progress on isolation
- **Implication**: Safety prioritized over goal achievement

### 5. **Termination Due to Iteration Limit**
- **Capability**: Bounds exploration when progress is minimal
- **Evidence**: Stopped after 5 iterations despite goals not achieved
- **Implication**: Prevents infinite loops in ineffective exploration

## Comparison with Multi-Step Approach

### Multi-Step (basic_sharing) Results:
- **Iterations**: 1 (vs 5 for primitive)
- **RSI Achievement**: 0.000 (vs 0.333 for primitive)
- **TCB Achievement**: [] (vs [PD_2] for primitive)
- **Core Problem**: ✅ Solved (vs ❌ Unsolved for primitive)

### Primitive-Only Results:
- **Iterations**: 5 (vs 1 for multi-step)
- **RSI Achievement**: 0.333 (unchanged)
- **TCB Achievement**: [PD_2] (unchanged)  
- **Core Problem**: ❌ Unsolved (vs ✅ Solved for multi-step)

### Efficiency Comparison:
- **Multi-step**: 100% goal achievement rate (2/3 goals) in 1 iteration
- **Primitive**: 0% goal achievement rate (0/3 goals) in 5 iterations
- **Resource utilization**: Multi-step more efficient (1 transformation vs 5)

## Security Analysis

### Failed Security Properties:
1. **Persistent Resource Sharing**: FILE_1_3 remains shared between PDs
2. **Trust Dependencies**: TCB[PD_1] still includes PD_2
3. **Constraint Isolation**: No progress on primary isolation goals

### Achieved Security Properties:
1. **Attack Surface Reduction**: ASR improved significantly (4.0→1.14)
2. **System Expansion**: Additional isolation boundaries created (5 new PDs)

### Security Anti-Pattern Demonstrated:
**Security Theater**: Creating appearance of improvement (more PDs) without addressing fundamental vulnerabilities (shared resources).

## Algorithm Insight: Primitive Insufficiency

### Root Cause Analysis:
1. **Limited Candidate Generation**: Basic primitives don't analyze constraint violations
2. **No Semantic Coordination**: Individual primitives lack problem-solving context
3. **Reactive vs Proactive**: Primitives respond to available transitions, not problem requirements

### Enhancement Opportunities:
1. **Constraint-Guided Primitives**: Generate file cloning when sharing detected
2. **Problem-Aware Transitions**: Trigger resource privatization primitives automatically
3. **Semantic Primitive Chaining**: Coordinate multiple primitives for complex operations

## Visualization Artifacts

1. **Timeline Visualization**: `isosearch_viz_basic_sharing_primitive_20250702_085625.html`
   - Shows repetitive PD addition across 5 iterations
   - Illustrates lack of progress on primary security goals

2. **Decision Tree Visualization**: `isosearch_tree_basic_sharing_primitive_20250702_085625.html`  
   - Displays uniform decision pattern (all `add_pd`)
   - Shows absence of candidate competition and alternative evaluation

## Key Insights

1. **Multi-Step Superiority**: Demonstrates clear advantage of semantic, problem-aware transformations
2. **Primitive Coordination Need**: Individual primitives require orchestration for complex security patterns
3. **Candidate Generation Importance**: Success depends on generating relevant transformation options
4. **Problem-Solution Gap**: General-purpose primitives may miss domain-specific security requirements
5. **Efficiency vs Coverage Trade-off**: Multi-step approaches achieve better results with fewer operations

This scenario validates the necessity of enhanced transformation design beyond basic primitives for effective automated security mechanism discovery.