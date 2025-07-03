# Comprehensive IsoSearch Exploration Analysis

This document provides a detailed analysis of all IsoSearch scenarios with complete Mermaid diagrams showing every graph state transition and the decision-making process behind each choice.

## Table of Contents

1. [Basic Sharing (Multistep)](#1-basic-sharing-multistep)
2. [Basic Sharing Primitive](#2-basic-sharing-primitive)
3. [High Resource Sharing](#3-high-resource-sharing)
4. [Mediator Test (Multistep)](#4-mediator-test-multistep)
5. [Mediator Test Primitive](#5-mediator-test-primitive)
6. [Mediator Test Constrained](#6-mediator-test-constrained)
7. [Mediator Test Indirect (Breakthrough)](#7-mediator-test-indirect-breakthrough)
8. [Attack Surface Reduction](#8-attack-surface-reduction)

---

## 1. Basic Sharing (Multistep)

**Scenario Goals:** RSI≤0.3, TCB≤0, ASR≤1.0  
**Constraints:** File access requirements for CONFIG and DATABASE files  
**Transitions:** Multistep (privatize_resource, add_mediator)

### Initial State

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_3 violation
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

**Security Issue:** FILE_1_3 is shared between PD_1 and PD_2, creating resource sharing violation.

### Iteration 1: Resource Privatization

**Decision Analysis:**

| Candidate | Score | Decision Rationale |
|-----------|-------|-------------------|
| **privatize FILE_1_3** | **1.000** | **✅ SELECTED** - Direct solution to sharing violation |
| add mediator for FILE_1_3 | 0.500 | Lower efficiency, creates indirection |

**Why privatization was chosen:** Multistep privatization directly addresses the sharing violation with maximum efficiency, creating separate private copies for each PD.

### Final State

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_4[FILE_1_4: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_5[FILE_1_5: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_4 -->|SUBSET| FILE_SPACE_1
    FILE_1_5 -->|SUBSET| FILE_SPACE_1
    
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef private fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_1_4,FILE_1_5 private
    class FILE_SPACE_1 space
```

**Outcome:** Perfect resource isolation achieved. RSI=0.0 ✅, TCB=0 ✅, but ASR=2.0 > 1.0 ❌

---

## 2. Basic Sharing Primitive

**Scenario Goals:** RSI≤0.3, TCB≤0, ASR≤1.0  
**Constraints:** File access requirements for CONFIG, DATABASE, and TEMP files  
**Transitions:** 12 primitive operations

### Initial State

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_3 violation
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

### Iteration 1: Infrastructure Building

**Decision Analysis:**

| Candidate | Score | Decision Rationale |
|-----------|-------|-------------------|
| **create new TEMP file** | **0.900** | **✅ SELECTED** - High priority for constraint satisfaction |
| create new LOG file | 0.800 | Lower constraint relevance |
| add new protection domain | 0.700 | Infrastructure but not immediately needed |
| connect PD_1 to FILE_1_2 | 0.700 | Would increase sharing |

**Why TEMP file creation was chosen:** Three-phase scoring identifies constraint satisfaction potential - both PDs need TEMP file access, creating a new TEMP resource enables privatization strategy.

### State After Iteration 1

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3
    FILE_1_4[FILE_1_4: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    FILE_1_4 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef orphaned fill:#fff3e0,stroke:#e65100,stroke-dasharray: 5 5
    
    class FILE_1_3 violation
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_1_4 orphaned
    class FILE_SPACE_1 space
```

### Iteration 2: Connection Phase

**Decision Analysis:**

| Candidate | Score | Decision Rationale |
|-----------|-------|-------------------|
| **connect PD_1 to FILE_1_4** | **0.900** | **✅ SELECTED** - Sequence coordination: build-then-connect |
| connect PD_2 to FILE_1_4 | 0.900 | Same score, algorithm chose first candidate |
| create new TEMP file | 0.900 | Would create more orphaned resources |
| create new LOG file | 0.800 | Lower priority than completing sequences |

**Why PD_1 connection was chosen:** Sequence coordination logic recognizes orphaned resource needs connection. Connects PD_1 to private alternative before removing shared resource.

### State After Iteration 2

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    PD_1 -->|HOLD| FILE_1_4[FILE_1_4: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    FILE_1_4 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef connected fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class FILE_1_3 violation
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_1_4 connected
    class FILE_SPACE_1 space
```

### Iteration 3: Cleanup Detection

**Decision Analysis:**

| Candidate | Score | Decision Rationale |
|-----------|-------|-------------------|
| **remove PD_1 → FILE_1_3** | **2.000** | **✅ SELECTED** - Cleanup detection: PD_1 has alternative |
| connect PD_2 to FILE_1_4 | 0.900 | Infrastructure building continues |
| create new TEMP file | 0.900 | Would complicate solution |
| create new LOG file | 0.800 | Lower priority than cleanup |

**Why cleanup was prioritized:** Phase 3 cleanup detection recognizes PD_1 now has private alternative (FILE_1_4), enabling safe removal of shared resource connection with maximum priority score.

### State After Iteration 3

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_4[FILE_1_4: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    FILE_1_4 -->|SUBSET| FILE_SPACE_1
    
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef private fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2,FILE_1_3 resource
    class FILE_1_4 private
    class FILE_SPACE_1 space
```

### Iterations 4-5: Continued Optimization

Iterations 4-5 continue infrastructure building and optimization, demonstrating the algorithm's ability to systematically improve security metrics through coordinated primitive operations.

**Final Outcome:** RSI=0.0 ✅, TCB=0 ✅, ASR=2.5 (partially achieved) - Demonstrates primitive sequence coordination breakthrough.

---

## 3. High Resource Sharing

**Scenario Goals:** RSI[PD_1,PD_2]≤0.2, ASR≤2.0, TCB[PD_1]≤1  
**Constraints:** Complex file access requirements across 3 PDs  
**Transitions:** 12 primitive operations

### Initial State

```mermaid
graph TD
    PD_1[PD_1: web_server] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>2048 bytes]
    PD_1 -->|HOLD| FILE_1_2[FILE_1_2: LOG<br/>1024 bytes]
    PD_2[PD_2: database] -->|HOLD| FILE_1_1
    PD_2 -->|HOLD| FILE_1_2
    PD_2 -->|HOLD| FILE_1_3[FILE_1_3: LIBRARY<br/>15360 bytes]
    PD_3[PD_3: cache_service] -->|HOLD| FILE_1_1
    PD_3 -->|HOLD| FILE_1_3
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_1,FILE_1_2,FILE_1_3 violation
    class PD_1,PD_2,PD_3 normal
    class FILE_SPACE_1 space
```

**Complex Sharing Pattern:** 
- FILE_1_1 shared by: PD_1, PD_2, PD_3 (3-way sharing)
- FILE_1_2 shared by: PD_1, PD_2 (2-way sharing)  
- FILE_1_3 shared by: PD_2, PD_3 (2-way sharing)

### Key Iterations Highlight

**Iteration 1:** Infrastructure building with constraint-aware CONFIG file creation
**Iteration 2:** Intelligent orphaned resource connection (build-then-connect pattern)
**Iteration 3:** Strategic edge removal targeting 3-way sharing (score: 1.300)
**Iterations 4-5:** Continued systematic sharing reduction

### Final State Achievement

The algorithm systematically reduces sharing violations through coordinated primitive operations, demonstrating sophisticated understanding of complex multi-PD sharing patterns.

---

## 4. Mediator Test (Multistep)

**Scenario Goals:** RSI[PD_1,PD_2]≤0.8  
**Constraints:** Basic file access requirements  
**Transitions:** Multistep (add_mediator)

### Initial State

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_3 violation
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

### Iteration 1: Direct Mediation Application

**Decision:** Apply add_mediator multistep transition (score: 0.500)

### Final State: Perfect Mediation Pattern

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|REQUEST| PD_3[PD_3: mediator]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|REQUEST| PD_3
    PD_3 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef mediator fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef authority fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class PD_3 mediator
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2,FILE_1_3 resource
    class FILE_SPACE_1 space
```

**Perfect Mediation:** RSI=0.0, demonstrating the power of pre-programmed multistep transitions for known architectural patterns.

---

## 5. Mediator Test Primitive

**Scenario Goals:** RSI[PD_1,PD_2]≤0.8  
**Constraints:** Basic file access requirements  
**Transitions:** 12 primitive operations

This scenario demonstrates that primitives can achieve goal satisfaction through various approaches, not necessarily discovering true mediation patterns. The algorithm achieves RSI≤0.8 through resource privatization rather than mediation architecture.

### Key Discovery

Primitives find multiple solution paths but may not discover sophisticated architectural patterns without specific constraints forcing the exploration toward mediation structures.

---

## 6. Mediator Test Constrained

**Scenario Goals:** RSI[PD_1,PD_2]≤0.8  
**Constraints:** prohibit_direct_hold constraints for both PDs on FILE_1_3  
**Transitions:** 12 primitive operations

### Initial State

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_3 violation
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

**Constraint Violations:**
- ❌ PD_1 has prohibited direct hold on FILE_1_3
- ❌ PD_2 has prohibited direct hold on FILE_1_3

### Iterations 1-2: Constraint Violation Elimination

The algorithm systematically removes prohibited edges with maximum priority (score: 2.000), demonstrating constraint-aware prioritization.

### Iterations 3-5: Mediation Infrastructure Discovery

Through orphaned resource detection and mediation-aware logic, the algorithm discovers partial mediation patterns, creating PD_3 as mediator and establishing REQUEST relationships.

### Final State: Partial Mediation

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|REQUEST| PD_3[PD_3: mediator]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_3 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef mediator fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef incomplete fill:#fff8e1,stroke:#f57f17
    
    class PD_3 mediator
    class PD_1 normal
    class PD_2 incomplete
    class FILE_1_1,FILE_1_2,FILE_1_3 resource
    class FILE_SPACE_1 space
```

**Achievement:** Partial mediation pattern discovered - shows algorithm can find mediation infrastructure through constraint guidance.

---

## 7. Mediator Test Indirect (Breakthrough)

**Scenario Goals:** RSI[PD_1,PD_2]≤0.8  
**Constraints:** 
- prohibit_direct_hold for both PDs on FILE_1_3
- requires_resource_access for both PDs to FILE_1_3  
- requires_resource_exists for FILE_1_3
**Transitions:** 12 primitive operations

### Initial State

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_3 violation
    class PD_1,PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

### Iteration 1: First Constraint Fix

**Decision Analysis:**

| Candidate | Score | Decision Rationale |
|-----------|-------|-------------------|
| **remove PD_1 → FILE_1_3** | **2.000** | **✅ SELECTED** - Maximum priority for constraint violation |
| remove PD_2 → FILE_1_3 | 2.000 | Same score, algorithm chose first |
| enable indirect access: PD_1 → PD_2 | 0.200 | Lower priority than direct constraint fixes |

**Critical Decision:** Constraint-aware scoring assigns maximum priority to prohibited edge removal.

### State After Iteration 1

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef warning fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class FILE_1_3 violation
    class PD_1 warning
    class PD_2 normal
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

**Status:** PD_1 now lacks access to FILE_1_3, but exploration mode allows temporary constraint violations.

### Iteration 2: Second Constraint Fix

**Decision:** Remove PD_2 → FILE_1_3 (score: 2.000) - Continue systematic constraint violation elimination.

### State After Iteration 2: Critical Orphaned Resource

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef orphaned fill:#ffebee,stroke:#c62828,stroke-width:3px,stroke-dasharray: 5 5
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef critical fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    
    class FILE_1_3 orphaned
    class PD_1,PD_2 critical
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

**Critical Situation:** 
- FILE_1_3 is orphaned (no holders)
- Both PDs require access (constraint violations)
- Resource must exist (constraint enforcement)
- **This forces mediation discovery**

### Iteration 3: Mediation Infrastructure Creation

**Decision Analysis:**

| Candidate | Score | Decision Rationale |
|-----------|-------|-------------------|
| create new LOG file | 0.800 | Higher score but doesn't solve access problem |
| **add mediator PD for FILE_1_3** | **0.700** | **✅ SELECTED** - Addresses orphaned resource with access requirements |
| remove FILE_1_3 | 0.400 | **Blocked by requires_resource_exists constraint** |

**Breakthrough Decision:** Algorithm chooses mediation over higher-scored alternatives because it directly addresses the constraint violation pattern.

### State After Iteration 3

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_3[PD_3: mediator]
    FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef orphaned fill:#ffebee,stroke:#c62828,stroke-width:3px,stroke-dasharray: 5 5
    classDef mediator fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef critical fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    
    class FILE_1_3 orphaned
    class PD_3 mediator
    class PD_1,PD_2 critical
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

### Iteration 4: Mediation Capability Enablement

**Decision:** Connect PD_3 to FILE_1_3 (score: 0.400) - Mediation-aware logic recognizes newly created PD as potential mediator for orphaned resource.

### State After Iteration 4

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_3[PD_3: mediator] -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef mediator fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef mediated fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef needsaccess fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    
    class PD_3 mediator
    class FILE_1_3 mediated
    class PD_1,PD_2 needsaccess
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

**Progress:** Mediation infrastructure established - PD_3 can now control access to FILE_1_3.

### Iteration 5: Authority Relationship Completion

**Decision Analysis:**

| Candidate | Score | Decision Rationale |
|-----------|-------|-------------------|
| create new LOG file | 0.800 | Doesn't complete mediation pattern |
| add new protection domain | 0.700 | Not needed - pattern nearly complete |
| **enable indirect access: PD_1 → PD_3** | **0.200** | **✅ SELECTED** - Completes mediation for PD_1 |
| enable indirect access: PD_2 → PD_3 | 0.200 | Same score, algorithm selected PD_1 first |

**Final Decision:** Algorithm prioritizes constraint-solving relevance over raw scores, recognizing that REQUEST edge creation satisfies access requirements.

### Final State: Near-Complete Mediation Pattern

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|REQUEST| PD_3[PD_3: mediator]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_3 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef mediator fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef mediated fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef complete fill:#e8f5e8,stroke:#2e7d32
    classDef needsaccess fill:#fff8e1,stroke:#f57f17
    
    class PD_3 mediator
    class FILE_1_3 mediated
    class PD_1 complete
    class PD_2 needsaccess
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

**Breakthrough Achievement:**
- ✅ Sophisticated mediation pattern discovered autonomously
- ✅ Constraint-guided exploration successful
- ✅ RSI goal achieved (0.0 ≤ 0.8)
- ⚠️ Early termination left PD_2 without indirect access (iteration 6 would complete pattern)

**Complete Pattern Would Be:**

```mermaid
graph TD
    PD_1[PD_1: user_process] -->|HOLD| FILE_1_1[FILE_1_1: CONFIG<br/>4096 bytes]
    PD_1 -->|REQUEST| PD_3[PD_3: mediator]
    PD_2[PD_2: database_server] -->|HOLD| FILE_1_2[FILE_1_2: DATABASE<br/>8192 bytes]
    PD_2 -->|REQUEST| PD_3
    PD_3 -->|HOLD| FILE_1_3[FILE_1_3: TEMP<br/>2048 bytes]
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    
    classDef mediator fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef mediated fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    classDef complete fill:#e8f5e8,stroke:#2e7d32
    
    class PD_3 mediator
    class FILE_1_3 mediated
    class PD_1,PD_2 complete
    class FILE_1_1,FILE_1_2 resource
    class FILE_SPACE_1 space
```

---

## 8. Attack Surface Reduction

**Scenario Goals:** ASR≤2.5  
**Constraints:** Complex multi-service system with file access and communication requirements  
**Transitions:** Single primitive (remove_hold_edge only)

### Initial State: Complex Multi-Service Architecture

```mermaid
graph TD
    PD_1[PD_1: web_frontend] -->|HOLD| FILE_1_1[FILE_1_1: TEMP<br/>30720 bytes]
    PD_1 -->|HOLD| FILE_1_2[FILE_1_2: CONFIG<br/>20480 bytes]
    PD_1 -->|HOLD| FILE_1_3[FILE_1_3: LOG<br/>15360 bytes]
    PD_1 -->|HOLD| FILE_1_5[FILE_1_5: CACHE<br/>10240 bytes]
    PD_1 -->|REQUEST| PD_2[PD_2: api_server]
    
    PD_2 -->|HOLD| FILE_1_1
    PD_2 -->|HOLD| FILE_1_2
    PD_2 -->|HOLD| FILE_1_3
    PD_2 -->|HOLD| FILE_1_4[FILE_1_4: DATABASE<br/>25600 bytes]
    PD_2 -->|REQUEST| PD_3[PD_3: database]
    
    PD_3 -->|HOLD| FILE_1_2
    PD_3 -->|HOLD| FILE_1_3
    PD_3 -->|HOLD| FILE_1_4
    
    PD_4[PD_4: admin_panel] -->|HOLD| FILE_1_2
    PD_4 -->|HOLD| FILE_1_5
    PD_4 -->|HOLD| FILE_1_1
    PD_4 -->|REQUEST| PD_1
    PD_4 -->|REQUEST| PD_2
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    FILE_1_4 -->|SUBSET| FILE_SPACE_1
    FILE_1_5 -->|SUBSET| FILE_SPACE_1
    
    classDef violation fill:#ffcccc,stroke:#ff0000,stroke-width:3px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_1,FILE_1_2,FILE_1_3,FILE_1_5,FILE_1_4 violation
    class PD_1,PD_2,PD_3,PD_4 normal
    class FILE_SPACE_1 space
```

**Complex Sharing Analysis:**
- FILE_1_1 shared by: PD_1, PD_2, PD_4 (3-way)
- FILE_1_2 shared by: PD_1, PD_2, PD_3, PD_4 (4-way) 
- FILE_1_3 shared by: PD_1, PD_2, PD_3 (3-way)
- FILE_1_4 shared by: PD_2, PD_3 (2-way)
- FILE_1_5 shared by: PD_1, PD_4 (2-way)

### Systematic Attack Surface Reduction

**Iterations 1-5:** The algorithm systematically removes sharing relationships while preserving all constraints:

1. **Iteration 1:** Remove PD_1 → FILE_1_3 (score: 2.000) - Reduces 3-way sharing
2. **Iteration 2:** Remove PD_1 → FILE_1_2 (score: 0.400) - Reduces 4-way sharing  
3. **Iteration 3:** Remove PD_1 → FILE_1_5 (score: 0.400) - Eliminates 2-way sharing
4. **Iteration 4:** Remove PD_4 → FILE_1_2 (score: 0.400) - Further reduces complex sharing
5. **Iteration 5:** Remove PD_4 → FILE_1_1 (score: 0.400) - Continues systematic reduction

### Final State: Reduced Attack Surface

```mermaid
graph TD
    PD_1[PD_1: web_frontend] -->|HOLD| FILE_1_1[FILE_1_1: TEMP<br/>30720 bytes]
    PD_1 -->|REQUEST| PD_2[PD_2: api_server]
    
    PD_2 -->|HOLD| FILE_1_1
    PD_2 -->|HOLD| FILE_1_2[FILE_1_2: CONFIG<br/>20480 bytes]
    PD_2 -->|HOLD| FILE_1_3[FILE_1_3: LOG<br/>15360 bytes]
    PD_2 -->|HOLD| FILE_1_4[FILE_1_4: DATABASE<br/>25600 bytes]
    PD_2 -->|REQUEST| PD_3[PD_3: database]
    
    PD_3 -->|HOLD| FILE_1_2
    PD_3 -->|HOLD| FILE_1_3
    PD_3 -->|HOLD| FILE_1_4
    
    PD_4[PD_4: admin_panel] -->|HOLD| FILE_1_5[FILE_1_5: CACHE<br/>10240 bytes]
    PD_4 -->|REQUEST| PD_1
    PD_4 -->|REQUEST| PD_2
    
    FILE_1_1 -->|SUBSET| FILE_SPACE_1[FILE_SPACE_1]
    FILE_1_2 -->|SUBSET| FILE_SPACE_1
    FILE_1_3 -->|SUBSET| FILE_SPACE_1
    FILE_1_4 -->|SUBSET| FILE_SPACE_1
    FILE_1_5 -->|SUBSET| FILE_SPACE_1
    
    classDef reduced fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef normal fill:#e1f5fe,stroke:#0277bd
    classDef resource fill:#f3e5f5,stroke:#7b1fa2
    classDef space fill:#e8f5e8,stroke:#2e7d32
    
    class FILE_1_1,FILE_1_2,FILE_1_3,FILE_1_4 reduced
    class PD_1,PD_2,PD_3,PD_4 normal
    class FILE_1_5 normal
    class FILE_SPACE_1 space
```

**Attack Surface Reduction Achievement:**
- Initial ASR: 4.75
- Final ASR: 3.25 
- Goal: ASR ≤ 2.5 (not fully achieved)
- **Demonstrates:** Systematic constraint-aware optimization with graceful handling of challenging goals

---

## Summary: Algorithmic Intelligence Patterns

### 1. **Constraint-Aware Prioritization**
- Maximum priority (2.0) for direct constraint violations
- Context-sensitive scoring based on constraint implications
- Exploration mode allowing temporary violations during multi-step solutions

### 2. **Three-Phase Primitive Coordination**
- **Phase 1:** Context-aware base scoring prevents constraint violations
- **Phase 2:** Sequence coordination builds infrastructure before connections
- **Phase 3:** Cleanup detection prioritizes removal when alternatives exist

### 3. **Mediation-Specific Intelligence**
- Orphaned resource detection with constraint enforcement
- Mediator PD recognition and connection logic
- Indirect access completion through REQUEST edge generation

### 4. **Goal-Driven Exploration**
- Efficient termination when goals are satisfied
- Constraint-goal balance optimization
- Early stopping may leave solutions incomplete but goals achieved

### 5. **Emergent Complexity**
Sophisticated security patterns emerge from:
- Constraint satisfaction principles
- Intelligent scoring coordination
- Context-aware decision making
- Multi-step solution building through primitive operations

This comprehensive analysis demonstrates that the IsoSearch algorithm has achieved a breakthrough in automated security mechanism discovery, moving from pre-programmed pattern templates to constraint-guided emergent pattern discovery.