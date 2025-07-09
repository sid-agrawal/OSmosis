# Evaluation: Submarine System for Security Architecture Exploration

## Specifying the Design Space of Isolation Mechanisms

The submarine system models isolation mechanisms through a graph-based representation where protection domains (PDs), resources, and their relationships form the design space. Each graph state represents a potential security architecture with measurable properties. The system supports primitive operations (add/remove nodes and edges) and composite transformations (privatize_resource, add_mediator), enabling exploration from fine-grained graph mutations to high-level architectural patterns. This dual granularity allows discovery of both known patterns (mediation, privilege separation) and emergent architectures not explicitly programmed.

## Specifying Goals and Constraints

Goals and constraints in submarine are expressed through a declarative scenario specification. Goals define optimization targets using security metrics: RSI[PD₁,PD₂]≤0.3 for sharing reduction, TCB[PD]≤0 for trust minimization, and ASR≤1.0 for attack surface control. Constraints encode hard requirements including prohibition constraints (prohibit_direct_hold between PD₁→FILE_1_3), access requirements (PD₁ requires CONFIG file ≥1KB), and existence requirements (specific resources must exist). This separation enables the system to explore architectures that satisfy functional requirements (constraints) while optimizing security properties (goals).

## Suitable Exploration Algorithms

Our evaluation demonstrates that two complementary algorithms effectively explore the design space. Pattern-aware beam search provides guided exploration using hierarchical scoring (3.0 for constraints, 2.5-2.9 for patterns, 0.2-1.5 for infrastructure), maintaining a beam of k=3 promising states while using pattern recognition to identify mediation opportunities and sharing reduction possibilities. True BFS offers exhaustive exploration for completeness analysis, discovering all reachable states within depth bounds. The beam search achieves 67% efficiency improvement by intelligently pruning paths, while BFS provides completeness guarantees for validating that key patterns aren't missed.

## Search Space Pruning Strategies

The system employs multiple pruning strategies to manage exponential growth. Constraint-based pruning immediately eliminates states violating hard requirements, preventing exploration of invalid architectures. Pattern-aware scoring creates implicit pruning by prioritizing promising operations—operations scoring below beam threshold are effectively pruned. Repetition filtering prevents oscillation between equivalent states (e.g., add/remove/add same edge). Dynamic structural analysis further prunes by recognizing futile paths early, such as attempting to connect PDs to non-existent resources. These strategies reduced candidate evaluation from potential thousands to 147-183 candidates in successful scenarios.

## Role of Multi-Step Transitions

Our experiments reveal that multi-step transitions serve different purposes across exploration strategies. For pattern-aware beam search, complex patterns emerge from intelligent sequencing of primitives—mediation discovered through remove_edge→add_pd→add_hold→add_request sequences guided by scoring. Multi-step transitions like "privatize_resource" provide shortcuts for known patterns but aren't strictly necessary. However, for human-guided exploration or when domain knowledge exists, multi-step transitions significantly accelerate discovery by encoding proven architectural transformations. The key insight is that pattern-aware scoring enables primitive-based discovery of patterns traditionally requiring multi-step specifications.

## Case Study Analysis

**Mediation Discovery (mediator_test_indirect)**: Starting with prohibited direct access, the system discovered indirect access through mediation. Constraint violations triggered maximum scoring (3.0) for removal operations. Orphaned resources prompted infrastructure creation (PD₃, score: 1.5). Pattern recognition guided mediator-resource connections (score: 3.0) and REQUEST edge completion (score: 1.8). Result: Complete mediation architecture in 10 iterations analyzing 183 candidates.

**Sharing Reduction (basic_sharing_primitive)**: Beginning with RSI=0.333 from shared FILE_1_3, the system discovered private alternatives. Sharing reduction pattern activated due to RSI goals, creating FILE_1_4 as orphaned resource. Dynamic type inference identified FILE_1_4 as CONFIG type. Private connections scored 2.9 versus 0.1 for shared resources. Result: RSI improved to 0.25 through systematic privatization across 8 iterations analyzing 147 candidates.

These case studies demonstrate that submarine enables systematic exploration of security architectures through declarative specification, intelligent algorithms, and effective pruning strategies.