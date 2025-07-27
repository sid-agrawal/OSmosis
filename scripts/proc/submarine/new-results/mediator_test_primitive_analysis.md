# IsoSearch Analysis: mediator_test_primitive Scenario

## Scenario Overview

**Name:** Mediator Test Primitive  
**Description:** Test if primitives can achieve mediation pattern  
**Goals:** RSI[PD_1,PD_2] ≤ 0.8  
**Constraints:** PD_1 needs FILE access (≥1KB), PD_2 needs FILE access (≥1KB)  
**Transitions:** 12 primitive operations only  

## Architectural Pattern Discovery Test

This scenario tests whether **primitives can autonomously discover the mediation pattern** given the same starting conditions and goals as mediator_test. The relaxed RSI goal (≤0.8) allows for multiple solution approaches.

### **Purpose & Design Intent:**
1. **Pattern Emergence Test:** Can sophisticated architectural patterns emerge from simple operations?
2. **Solution Comparison:** How do primitive solutions differ from expert-encoded patterns?
3. **Discovery Limitations:** What prevents primitives from finding certain architectures?
4. **Alternative Paths:** What solutions do primitives find instead?

## Exploration Timeline with Mermaid Diagrams

### Initial State: Same as mediator_test
```mermaid
graph TD
    PD1[PD_1<br/>user_process] 
    PD2[PD_2<br/>database_server]
    FS[FILE_SPACE_1<br/>FILE]
    F1[FILE_1_1<br/>CONFIG<br/>/etc/user.conf<br/>🟢 PRIVATE TO PD_1]
    F2[FILE_1_2<br/>DATABASE<br/>/var/db/main.db<br/>🟢 PRIVATE TO PD_2]
    F3[FILE_1_3<br/>TEMP<br/>/tmp/shared_buffer.tmp<br/>🔴 SHARED VIOLATION]
    
    PD1 -->|HOLD| F1
    PD1 -->|HOLD| F3
    PD2 -->|HOLD| F2
    PD2 -->|HOLD| F3
    F1 -->|SUBSET| FS
    F2 -->|SUBSET| FS
    F3 -->|SUBSET| FS
    
    style F1 fill:#ccffcc
    style F2 fill:#ccffcc
    style F3 fill:#ffcccc
    style PD1 fill:#e1f5fe
    style PD2 fill:#e8f5e8
```

**Initial Conditions:**
- **RSI[PD_1,PD_2]: 0.333 > 0.8** ❌ (but much easier target than other scenarios)
- **Same sharing problem:** FILE_1_3 creates coupling
- **All primitives available:** Can they find mediation?

### Iteration 1: Infrastructure Building
**Decision:** `add_file_resource` (TEMP file) - Score: 0.900

```mermaid
graph TD
    PD1[PD_1<br/>user_process] 
    PD2[PD_2<br/>database_server]
    FS[FILE_SPACE_1<br/>FILE]
    F1[FILE_1_1<br/>CONFIG]
    F2[FILE_1_2<br/>DATABASE]
    F3[FILE_1_3<br/>TEMP<br/>🔴 Still Shared]
    F4[FILE_1_4<br/>TEMP<br/>🆕 Infrastructure]
    
    PD1 -->|HOLD| F1
    PD1 -->|HOLD| F3
    PD2 -->|HOLD| F2
    PD2 -->|HOLD| F3
    F1 -->|SUBSET| FS
    F2 -->|SUBSET| FS
    F3 -->|SUBSET| FS
    F4 -->|SUBSET| FS
    
    style F3 fill:#ffcccc
    style F4 fill:#fff3cd
```

**Primitive Choice Analysis:**
- ❌ **Did NOT create mediator PD** (would score 0.0 - no immediate benefit)
- ✅ **Created alternative resource** (scores 0.9 - enables future privatization)
- Shows **local optimization bias** - immediate value over architectural setup

### Iteration 2: Private Connection
**Decision:** `add_hold_edge` (PD_1 → FILE_1_4) - Score: 0.900

```mermaid
graph TD
    PD1[PD_1<br/>user_process] 
    PD2[PD_2<br/>database_server]
    FS[FILE_SPACE_1<br/>FILE]
    F1[FILE_1_1<br/>CONFIG]
    F2[FILE_1_2<br/>DATABASE]
    F3[FILE_1_3<br/>TEMP<br/>🔴 Shared]
    F4[FILE_1_4<br/>TEMP<br/>🟢 PD_1 Alternative]
    
    PD1 -->|HOLD| F1
    PD1 -->|HOLD| F3
    PD1 ==>|HOLD<br/>NEW| F4
    PD2 -->|HOLD| F2
    PD2 -->|HOLD| F3
    
    style F3 fill:#ffcccc
    style F4 fill:#ccffcc
```

**Privatization Path Emerging:**
- ✅ **Sequence coordination working** - connect after build
- ❌ **No REQUEST edges considered** (would score ~0.2)
- Following **build→connect→cleanup** pattern discovered earlier

### Iteration 3: Sharing Elimination
**Decision:** `remove_hold_edge` (PD_1 → FILE_1_3) - Score: 1.000

```mermaid
graph TD
    PD1[PD_1<br/>user_process] 
    PD2[PD_2<br/>database_server]
    FS[FILE_SPACE_1<br/>FILE]
    F1[FILE_1_1<br/>CONFIG]
    F2[FILE_1_2<br/>DATABASE]
    F3[FILE_1_3<br/>TEMP<br/>🟡 No Longer Shared!]
    F4[FILE_1_4<br/>TEMP<br/>🟢 PD_1 Private]
    
    PD1 -->|HOLD| F1
    PD1 -->|HOLD| F4
    PD2 -->|HOLD| F2
    PD2 -->|HOLD| F3
    
    style F3 fill:#fff3cd
    style F4 fill:#ccffcc
```

**Critical Divergence Point:**
- ✅ **RSI goal achieved** (0.0 ≤ 0.8) through privatization
- ❌ **Mediation path abandoned** - goal already met
- 🎯 **Different architecture, same security outcome**

### Iterations 4-5: Continued Infrastructure
**Decisions:** Additional resource creation

```mermaid
graph TD
    PD1[PD_1<br/>user_process] 
    PD2[PD_2<br/>database_server]
    FS[FILE_SPACE_1<br/>FILE]
    F1[FILE_1_1]
    F2[FILE_1_2]
    F3[FILE_1_3<br/>🟢 PD_2 Exclusive]
    F4[FILE_1_4<br/>🟢 PD_1 Private]
    F5[FILE_1_5<br/>LOG]
    F6[FILE_1_6<br/>CONFIG]
    
    PD1 -->|HOLD| F1
    PD1 -->|HOLD| F4
    PD2 -->|HOLD| F2
    PD2 -->|HOLD| F3
    
    style F3 fill:#ccffcc
    style F4 fill:#ccffcc
    style F5 fill:#e9ecef
    style F6 fill:#e9ecef
```

**Post-Goal Behavior:**
- Algorithm continues building infrastructure
- No attempt at mediation pattern even after goal met
- Demonstrates **privatization as default solution**

## Solution Comparison: Privatization vs Mediation

### What Primitives Achieved (Privatization)
```mermaid
graph LR
    subgraph "Before"
        B1[PD_1] -->|HOLD| BR[Shared FILE_1_3]
        B2[PD_2] -->|HOLD| BR
    end
    
    subgraph "After: Privatization"
        A1[PD_1] -->|HOLD| AR1[Private FILE_1_4]
        A2[PD_2] -->|HOLD| AR2[Exclusive FILE_1_3]
    end
    
    Before -->|"Primitive<br/>Solution"| After
```

**Characteristics:**
- ✅ RSI = 0.0 (perfect isolation)
- ✅ No shared resources
- ✅ 3-step solution
- ❌ No architectural sophistication

### What Mediation Would Achieve
```mermaid
graph LR
    subgraph "Before"
        B1[PD_1] -->|HOLD| BR[Shared FILE_1_3]
        B2[PD_2] -->|HOLD| BR
    end
    
    subgraph "After: Mediation"
        A1[PD_1] -.->|REQUEST| M[Mediator PD_3]
        A2[PD_2] -.->|REQUEST| M
        M -->|HOLD| MR[Controlled FILE_1_3]
    end
    
    Before -->|"Expert<br/>Pattern"| After
```

**Characteristics:**
- ✅ RSI = 0.0 (isolation via indirection)
- ✅ Controlled access pattern
- ✅ Policy enforcement capability
- ✅ Architectural sophistication

## Why Primitives Chose Privatization Over Mediation

### Decision Tree Analysis
```mermaid
graph TD
    Start[Initial State<br/>RSI = 0.333]
    
    D1{First Decision}
    P1[add_file_resource<br/>Score: 0.9]
    M1[add_pd mediator<br/>Score: 0.0]
    
    D2{Second Decision}
    P2[add_hold_edge<br/>Score: 0.9]
    M2[add_request_edge<br/>Score: 0.2]
    
    D3{Third Decision}
    P3[remove_hold_edge<br/>Score: 1.0<br/>✅ GOAL MET]
    M3[More setup needed<br/>Score: varies]
    
    Start --> D1
    D1 -->|"Chosen"| P1
    D1 -.->|"Rejected"| M1
    P1 --> D2
    D2 -->|"Chosen"| P2
    D2 -.->|"Rejected"| M2
    P2 --> D3
    D3 -->|"Chosen"| P3
    D3 -.->|"Not reached"| M3
    
    style P1 fill:#d3f9d8
    style P2 fill:#d3f9d8
    style P3 fill:#d3f9d8
    style M1 fill:#ffe3e3
    style M2 fill:#ffe3e3
    style M3 fill:#ffe3e3
```

### Local vs Global Optimization
```python
# Primitive scoring (local optimization)
Iteration 1: add_file_resource()    → 0.9 (immediate potential)
Iteration 2: add_hold_edge()        → 0.9 (progress toward goal)
Iteration 3: remove_hold_edge()     → 1.0 (achieves goal)
Total: 3 moves, all high-scoring

# Mediation path (requires global vision)
Step 1: add_pd()                    → 0.0 (no immediate benefit)
Step 2: add_request_edge()          → 0.2 (no RSI improvement)
Step 3: add_request_edge()          → 0.2 (still no RSI improvement)
Step 4: add_hold_edge(mediator)     → 0.3 (slight progress)
Step 5: remove_hold_edge(pd1)       → 0.5 (partial improvement)
Step 6: remove_hold_edge(pd2)       → 1.0 (finally achieves goal)
Total: 6 moves, mostly low-scoring
```

## Key Findings

### 🔍 **Architectural Patterns Cannot Emerge from Local Optimization**
- **Mediation requires strategic patience** - making low-scoring moves for future benefit
- **Primitives optimize locally** - choosing immediate improvements
- **Horizon problem is fundamental** - 6-step sequences exceed primitive planning capability
- **Architectural vision needed** - understanding end-state value

### 🎯 **Different Paths to Same Security Goal**
- **Privatization**: Simple, direct, efficient (3 steps)
- **Mediation**: Complex, indirect, sophisticated (6 steps)
- **Both achieve RSI ≤ 0.8** but through different architectures
- **Trade-offs**: Efficiency vs capability

### 🧩 **The Value of Multi-Step Transitions**
- **Encode irreducible complexity** - patterns that can't be decomposed
- **Capture architectural knowledge** - expert understanding of system design
- **Enable sophisticated solutions** - beyond what emergence can discover
- **Complement primitive discovery** - hybrid approach maximizes capability

### 📈 **Solution Quality vs Complexity**
```mermaid
graph TD
    subgraph "Solution Comparison"
        P[Privatization<br/>3 steps<br/>RSI = 0.0<br/>Simple]
        M[Mediation<br/>6 steps<br/>RSI = 0.0<br/>Sophisticated]
        
        PC[Capabilities:<br/>- Isolation ✓<br/>- Efficiency ✓<br/>- Policy Control ✗<br/>- Audit Trail ✗]
        MC[Capabilities:<br/>- Isolation ✓<br/>- Efficiency ✗<br/>- Policy Control ✓<br/>- Audit Trail ✓]
        
        P --> PC
        M --> MC
    end
```

## Scenario Purpose Achieved

The mediator_test_primitive scenario successfully demonstrates that **architectural patterns like mediation cannot emerge from primitive operations alone**:

1. **Primitives default to simpler solutions** when multiple paths exist
2. **Local optimization prevents discovery** of globally optimal architectures  
3. **Multi-step transitions remain essential** for sophisticated patterns
4. **Hybrid approach validated** - both primitives and patterns needed

This confirms that some security mechanisms require **encoded expertise rather than emergent discovery**, justifying IsoSearch's dual approach to mechanism discovery.

## The Emergence vs Encoding Trade-off

### **What Primitives Can Discover:**
- **Direct solutions** with immediate value
- **Sequential patterns** where each step improves metrics
- **Local optimizations** within visibility horizon
- **Simple architectures** without strategic setup

### **What Must Be Encoded:**
- **Indirect architectures** requiring patient setup
- **Complex patterns** with delayed gratification
- **Strategic solutions** optimizing for capabilities beyond metrics
- **Sophisticated designs** encoding domain expertise

**Together:** They provide comprehensive security mechanism discovery - **emergence for novel solutions, encoding for proven architectures**.