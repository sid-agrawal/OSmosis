# Related Work: Design Space Exploration of OS Abstractions and Architectures

This document surveys related work from major operating systems conferences that focus on design space exploration of OS abstractions and architectures, similar to the submarine system's approach to security architecture discovery.

## 1. Hyperkernel: Push-Button Verification of an OS Kernel (SOSP 2017)

**Authors**: Luke Nelson, Helgi Sigurbjarnarson, Kaiyuan Zhang, Dylan Johnson, James Bornholt, Emina Torlak, Xi Wang

**Key Contributions**:
- **Design Space Exploration**: Uses symbolic execution and SMT solvers to explore all possible execution paths in kernel code
- **Automated Verification**: Push-button verification of functional correctness for an OS kernel
- **Finite Interface Design**: Designs kernel interfaces to be finite, enabling exhaustive exploration

**Relation to Submarine**:
- Both systems explore design spaces exhaustively (Hyperkernel for correctness, submarine for security architectures)
- Both use constraint-based reasoning (SMT solvers vs. constraint-driven scoring)
- Hyperkernel's finite interface principle parallels submarine's bounded primitive operations
- Key difference: Hyperkernel verifies existing designs while submarine synthesizes new architectures

**Design Space Approach**:
```
Kernel Interface → Symbolic Execution → SMT Solver → Verification/Counterexample
```

## 2. Redleaf: Isolation and Communication in a Safe Operating System (OSDI 2020)

**Authors**: Vikram Narayanan, Tianjiao Huang, David Detweiler, Dan Appel, Zhaofeng Li, Gerd Zellweger, Anton Burtsev

**Key Contributions**:
- **Abstraction Exploration**: Explores design space of isolation mechanisms beyond traditional process boundaries
- **Domain-Based Isolation**: Introduces heap isolation domains as a new OS abstraction
- **Zero-Copy Communication**: Explores various communication patterns between isolated domains

**Relation to Submarine**:
- Both explore alternative isolation architectures (Redleaf's domains vs. submarine's protection domains)
- Both discover communication patterns (Redleaf's RRef vs. submarine's REQUEST edges)
- Both aim to find optimal trade-offs between isolation and performance
- Redleaf manually designs patterns that submarine could potentially discover automatically

**Design Patterns Discovered**:
- Ownership transfer patterns for zero-copy communication
- Mediator patterns for cross-domain calls (similar to submarine's mediation discovery)
- Shared memory abstractions with fine-grained permissions

## 3. Nickel: A Framework for Design and Verification of Information Flow Control Systems (OSDI 2018)

**Authors**: Helgi Sigurbjarnarson, Luke Nelson, Bruno Castro-Karney, James Bornholt, Emina Torlak, Xi Wang

**Key Contributions**:
- **Policy Space Exploration**: Automatically explores space of information flow control policies
- **Constraint-Based Synthesis**: Uses solver-aided programming to synthesize security monitors
- **Pattern Library**: Provides reusable patterns for information flow control

**Relation to Submarine**:
- Both use constraint-based approaches for security architecture discovery
- Nickel's policy synthesis parallels submarine's pattern-aware scoring
- Both systems recognize and instantiate security patterns
- Nickel focuses on information flow while submarine addresses broader isolation patterns

**Exploration Methodology**:
```python
Policy Specification → Constraint Generation → 
    SMT-based Synthesis → Security Monitor
```

## 4. FlexOS: Making OS Isolation Flexible (ASPLOS 2022)

**Authors**: Hugo Lefeuvre, Vlad-Andrei Bădoiu, Stefan Teodorescu, Pierre Olivier, Tiberiu Dăianu, Costin Raiciu, Felipe Huici

**Key Contributions**:
- **Systematic Design Space Exploration**: Explores the full design space of isolation mechanisms from shared memory to hardware virtualization
- **Isolation Flexibility**: Demonstrates how to make isolation decisions at deployment time rather than design time
- **Performance-Security Trade-off Analysis**: Systematically evaluates the trade-offs between different isolation mechanisms
- **Compartmentalization Patterns**: Identifies and analyzes various compartmentalization strategies

**Relation to Submarine**:
- **Most Direct Parallel**: FlexOS explicitly explores design spaces of isolation mechanisms, directly paralleling submarine's security architecture exploration
- **Constraint-Driven Decisions**: Both systems make architectural decisions based on requirements (FlexOS uses performance/security requirements, submarine uses goals/constraints)
- **Pattern Library Approach**: FlexOS identifies isolation patterns that submarine could discover automatically
- **Multi-Objective Optimization**: Both balance multiple objectives (performance vs. security in FlexOS, RSI vs. TCB vs. ASR in submarine)

**Design Space Methodology**:
```
Application Requirements → Isolation Strategy Selection → 
    Compartmentalization Deployment → Performance/Security Analysis
```

**Isolation Patterns Explored**:
- **Shared Memory**: Direct sharing with no isolation (similar to submarine's shared resources)
- **Process Isolation**: Traditional process boundaries
- **Lightweight Contexts**: User-level threading with protection
- **Hardware Virtualization**: Strong isolation with VMs
- **Hybrid Approaches**: Mixing isolation levels within applications

**Key Insight for Submarine**: FlexOS demonstrates that isolation decisions should be made based on specific requirements rather than one-size-fits-all approaches - exactly what submarine's pattern-aware scoring enables through dynamic adaptation.

## 5. Theseus: A State Spill-Free Operating System (PLOS 2021)

**Authors**: Kevin Boos, Namitha Liyanage, Ramla Ijaz, Lin Zhong

**Key Contributions**:
- **Architectural Exploration**: Explores design space of OS architectures without state spill
- **Component Isolation**: Every component is isolated with runtime composability
- **Live Evolution**: Explores patterns for runtime system evolution

**Relation to Submarine**:
- Both explore component isolation patterns and their trade-offs
- Theseus's intralingual design explores similar mediation patterns
- Both systems discover architectures that balance isolation with functionality
- Theseus implements patterns that submarine could discover through exploration

**Design Principles Explored**:
- Cell-based architecture (similar to submarine's PD-based graphs)
- Capability-based resource access (analogous to submarine's HOLD edges)
- Runtime reconfiguration patterns

## Common Themes and Submarine's Unique Contributions

### Shared Approaches:
1. **Constraint-Based Reasoning**: All systems use constraints to guide exploration
2. **Pattern Recognition**: Identifying reusable architectural patterns
3. **Trade-off Analysis**: Balancing security/isolation with performance/functionality
4. **Abstraction Design**: Exploring alternative OS abstractions

### Submarine's Unique Aspects:
1. **Multi-Pattern Discovery**: Simultaneously discovers multiple security patterns (mediation, sharing reduction)
2. **Beam Search Exploration**: Uses AI-inspired search rather than exhaustive verification
3. **Dynamic Scoring**: Pattern-aware scoring adapts to graph context
4. **Emergent Architectures**: Patterns emerge from primitives rather than being pre-specified

### Research Gap Addressed:
While prior work focuses on either:
- **Verification** of specific designs (Hyperkernel, Nickel)
- **Manual exploration** of design alternatives (Redleaf, Theseus)

Submarine provides **automated discovery** of security architectures through intelligent search, filling the gap between manual design and automated verification.

## 6. Intra-Unikernel Isolation with Intel Memory Protection Keys (EuroSys 2020)

**Authors**: Mincheol Sung, Pierre Olivier, Stefan Lankes, Binoy Ravindran

**Key Contributions**:
- **Fine-Grained Isolation Exploration**: Explores design space of intra-address-space isolation using Intel MPK
- **Compartmentalization Strategies**: Systematic exploration of different compartmentalization approaches within unikernels
- **Performance-Isolation Trade-offs**: Quantifies trade-offs between isolation granularity and performance overhead

**Relation to Submarine**:
- Explores similar isolation granularity questions that FlexOS addresses
- Demonstrates how hardware features can enable new points in the isolation design space
- Shows systematic exploration of compartmentalization strategies (what submarine could automate)

## 7. Hodor: Intra-Process Isolation for High-Throughput Data Plane Libraries (USENIX ATC 2019)

**Authors**: Lluís Vilanova, Lina Maudlej, Swapnil Haria, Adwait Jog, Aleksandar Milenković, Hubertus Franke

**Key Contributions**:
- **Library Isolation Design Space**: Explores isolation mechanisms for data plane libraries
- **Micro-Compartmentalization**: Fine-grained isolation strategies within processes
- **Systematic Performance Analysis**: Evaluates different isolation approaches across workloads

**Relation to Submarine**:
- Similar to FlexOS but focused on library-level compartmentalization
- Demonstrates systematic exploration of micro-isolation patterns
- Shows how requirements drive isolation strategy selection

## 8. Lightweight Kernel Isolation with Virtualization and VM Functions (VEE 2020)

**Authors**: Vikram Narayanan, Abhiram Balasubramanian, Charlie Jacobsen, Sarah Spall, Scott Bauer, Michael Quigley, Aftab Hussain, Abdullah Younis, Junjie Shen, Moinak Bhattacharyya, Anton Burtsev

**Key Contributions**:
- **Kernel Isolation Exploration**: Systematically explores isolation mechanisms within OS kernels
- **VM Function Integration**: Novel approach to kernel compartmentalization using hardware virtualization
- **Design Pattern Analysis**: Identifies patterns for isolating kernel components

**Relation to Submarine**:
- Explores kernel-level isolation patterns (complementary to submarine's user-space focus)
- Demonstrates systematic exploration of virtualization-based isolation
- Shows how hardware features enable new architectural patterns

## 9. Enclave-based Selective Memory Protection for Userspace (USENIX Security 2021)

**Authors**: Felicitas Hetzelt, Robert Buhren, Jean-Pierre Seifert

**Key Contributions**:
- **Memory Protection Design Space**: Explores selective memory protection mechanisms using Intel SGX
- **Application-Level Compartmentalization**: Systematic approach to protecting sensitive data in applications
- **Threat Model Adaptation**: Shows how different threat models lead to different isolation strategies

**Relation to Submarine**:
- Similar to FlexOS approach but focused on memory protection rather than full isolation
- Demonstrates requirement-driven design space exploration
- Shows systematic analysis of protection mechanisms

## Enhanced Analysis: FlexOS-Inspired Insights

### Key Patterns from FlexOS and Related Work:

1. **Systematic Design Space Exploration**: All systems methodically explore isolation/protection design spaces
2. **Requirement-Driven Selection**: Architectural decisions based on specific performance/security requirements
3. **Multi-Level Isolation**: Recognition that different components need different isolation levels
4. **Hardware-Software Co-design**: Leveraging hardware features for new architectural possibilities

### Submarine's Position in This Landscape:

**Unique Contributions**:
- **Automated Discovery**: While FlexOS and others manually explore design spaces, submarine automates discovery
- **Pattern Emergence**: Patterns emerge from primitive operations rather than being pre-catalogued
- **Dynamic Adaptation**: Real-time adaptation to graph context vs. deployment-time decisions
- **Multi-Pattern Synthesis**: Simultaneous discovery of multiple interacting patterns

**Research Gap Filled**:
FlexOS and related work demonstrate the **need** for flexible, requirement-driven isolation strategies. Submarine provides the **automation** to discover these strategies without manual design space exploration.

### FlexOS-Submarine Integration Opportunities:

1. **Pattern Library Extension**: Incorporate FlexOS's isolation patterns as templates
2. **Requirement Translation**: Map FlexOS-style requirements to submarine constraints
3. **Performance-Security Models**: Integrate FlexOS's trade-off models into submarine scoring
4. **Hardware-Aware Patterns**: Extend submarine to discover hardware-assisted isolation patterns

## Future Directions

Combining submarine's approach with insights from FlexOS and related isolation work suggests:

1. **Automated FlexOS**: Use submarine to automatically discover the isolation strategies that FlexOS manually catalogs
2. **Hardware-Aware Discovery**: Extend submarine to consider hardware isolation features (MPK, SGX, etc.)
3. **Multi-Level Synthesis**: Discover architectures spanning multiple isolation levels
4. **Performance-Security Co-optimization**: Integrate performance models into pattern-aware scoring
5. **Cross-Layer Patterns**: Discover patterns that span user-space, kernel, and hardware levels

This positions submarine as the "automated exploration engine" for the design spaces that FlexOS and related work have identified as critical for modern system security.