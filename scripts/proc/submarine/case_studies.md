# IsoSearch Case Studies for Workshop Paper

This document contains the detailed case studies demonstrating IsoSearch's automated security mechanism discovery capabilities.

## Case Study 1: Automated Resource Isolation in Shared-Memory Systems

### Problem Context
Modern operating systems frequently employ shared memory regions between protection domains to enable efficient inter-process communication. However, this sharing creates security vulnerabilities where compromised processes can access data from other domains, violating the principle of least privilege. Manual identification and resolution of such sharing patterns is time-consuming and error-prone in complex systems.

### IsoSearch Application
We applied IsoSearch to a representative shared-memory scenario featuring two protection domains (a user process and database server) with overlapping resource access. The initial configuration contained:
- **7 memory resources**: 6 private VMR resources (3 per PD) and 1 shared buffer
- **Security violation**: VMR_1_7 (20-page heap buffer) shared between both domains
- **Functional constraints**: Each PD requires minimum heap access for operation

### Exploration Results
IsoSearch automatically discovered and evaluated two potential security mechanisms:

1. **Resource Privatization** (selected): Split shared buffer into separate private copies
2. **Mediator Insertion** (considered): Insert authority-based access control

The algorithm selected privatization based on superior Resource Sharing Index (RSI) improvement prediction (1.000 vs 0.500). After applying the transformation:

- **RSI improvement**: 0.143 → 0.000 (complete isolation achieved)
- **Security gain**: Eliminated direct memory sharing vulnerability
- **Functional preservation**: Both domains retained required heap capacity through private allocations

### Scenario Configuration
```
Scenario: basic_sharing
Goals: RSI[PD_1,PD_2] ≤ 0.3, TCB[PD_1] ≤ 0, ASR ≤ 1.0
Constraints: requires_vmr_access(PD_1, HEAP, 3 pages), requires_vmr_access(PD_2, HEAP, 3 pages)
Transitions: privatize_resource, add_mediator
```

### Key Insights
This case study demonstrates IsoSearch's ability to automatically detect sharing vulnerabilities and apply principled transformations that optimize security metrics while preserving functional requirements. The constraint-based validation ensured that the heap access requirements for both domains remained satisfied throughout the transformation.

---

## Case Study 2: Authority-Based Mediation in Multi-Service Architecture  

### Problem Context
In microservice architectures, services often require direct access to shared resources, creating complex trust relationships and expanding attack surfaces. When multiple services can directly access the same memory regions, a compromise in any service can lead to system-wide data breaches. Traditional manual security hardening requires extensive analysis to identify safe mediation points.

### IsoSearch Application
We configured a scenario specifically to test authority-based mediation as an alternative to resource privatization. The setup involved:
- **Initial sharing**: Two protection domains sharing a 20-page communication buffer
- **Goal**: Reduce direct sharing through mediation (RSI target: 0.8)
- **Constraints**: Preserve memory access capabilities for both services

### Exploration Results
IsoSearch automatically applied the **Add Mediator** transformation, which:

1. **Created mediator PD**: New protection domain (PD_3) with exclusive resource access
2. **Established authority chains**: Both original domains now request access through PD_3
3. **Eliminated direct sharing**: RSI reduced from 0.143 to 0.000

**Security Architecture Changes**:
- **Before**: `PD_1 ←→ VMR_1_7 ←→ PD_2` (direct sharing)
- **After**: `PD_1 → PD_3 ← PD_2` with `PD_3 → VMR_1_7` (mediated access)

### Security Impact
The mediation mechanism achieved multiple security improvements:
- **Eliminated direct sharing**: No memory regions accessible by multiple domains
- **Reduced attack surface**: Compromise of PD_1 or PD_2 cannot directly access shared data
- **Established audit point**: All resource access flows through the mediator PD
- **Fault radius containment**: FR metric shows maximum 2-hop communication paths

### Scenario Configuration
```
Scenario: mediator_test
Goals: RSI[PD_1,PD_2] ≤ 0.8
Constraints: requires_vmr_access(PD_1, any, 1 page), requires_vmr_access(PD_2, any, 1 page)
Transitions: add_mediator
```

### Key Insights
This case study illustrates IsoSearch's capability to automatically discover and implement authority-based security patterns. The algorithm recognized that mediation was sufficient to meet the RSI goal (0.8) while creating a more defensible architecture through centralized resource control. The resulting design follows security engineering best practices for privilege separation and audit trail establishment.

---

## Comparative Analysis

Both case studies demonstrate IsoSearch's dual capability for **reactive** security hardening (Case Study 1: eliminating existing vulnerabilities) and **proactive** security architecture design (Case Study 2: establishing defensive patterns). The system's constraint-aware exploration ensures that functional requirements are preserved while systematically improving security posture through principled graph transformations.

### Quantitative Results Summary

| Case Study | Initial RSI | Final RSI | Mechanism | Iterations | Success |
|------------|-------------|-----------|-----------|------------|---------|
| 1: Resource Isolation | 0.143 | 0.000 | privatize_resource | 1 | ✅ |
| 2: Authority Mediation | 0.143 | 0.000 | add_mediator | 1 | ✅ |

### Architectural Patterns Discovered

1. **Isolation Pattern**: Direct sharing → Private resource copies
2. **Mediation Pattern**: Direct sharing → Authority-controlled access

Both patterns achieved complete sharing elimination (RSI = 0.000) while preserving functional requirements through different architectural approaches.