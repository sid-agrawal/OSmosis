# Cache Partitioning Scenario Plan

## Overview

Design a scenario that models CPU cache partitioning to discover configurations where PDs running on separate cores naturally end up using different cache sets - preventing cache side-channel attacks.

## Background: Cache Side-Channel Problem

When multiple protection domains share cache sets, they can infer information about each other's memory access patterns (Prime+Probe, Flush+Reload attacks). The goal is to explore graph transformations that lead to cache isolation.

## Design Decisions (from discussion)

| Question | Decision |
|----------|----------|
| Cache level | **L3/LLC** (shared across all cores) |
| Cache set mapping | **Modulo-based**: `cache_set = phys_page_id % num_cache_sets` |
| Initial states | **Two scenarios**: same-core conflict + cross-core LLC collision |
| Goal metric | **Zero overlap** in cache sets between PD pairs |
| Constraints | TBD |
| Transformations | Use existing primitives |

---

## Model Design

### Resource Spaces

```
CPU_SPACE_1          - Collection of CPU cores
CACHE_SET_SPACE_1    - Collection of L3 cache sets
PHYS_PAGE_SPACE_1    - Physical memory pages
```

### Resources

```
CPU_1, CPU_2, ...           - Individual cores
CACHE_SET_1, CACHE_SET_2... - L3 cache sets (e.g., 4 sets for simplicity)
PHYS_PAGE_1, PHYS_PAGE_2... - Physical memory pages
```

### Edge Semantics

| Edge Type | From → To | Meaning |
|-----------|-----------|---------|
| HOLD | PD → CPU | PD is scheduled/pinned to this core |
| HOLD | PD → PHYS_PAGE | PD uses this physical memory |
| MAP | PHYS_PAGE → CACHE_SET | Physical address determines cache set (modulo mapping) |

### Cache Set Mapping Formula

For simplicity, with 4 cache sets:
```
PHYS_PAGE_1 → CACHE_SET_1  (1 % 4 = 1)
PHYS_PAGE_2 → CACHE_SET_2  (2 % 4 = 2)
PHYS_PAGE_3 → CACHE_SET_3  (3 % 4 = 3)
PHYS_PAGE_4 → CACHE_SET_0  (4 % 4 = 0)
PHYS_PAGE_5 → CACHE_SET_1  (5 % 4 = 1)  <- collides with PHYS_PAGE_1
...
```

---

## Scenario A: Same-Core Cache Conflict

### Initial State
```
PD_1 ──HOLD──> CPU_1
PD_2 ──HOLD──> CPU_1          (same core!)

PD_1 ──HOLD──> PHYS_PAGE_1 ──MAP──> CACHE_SET_1
PD_2 ──HOLD──> PHYS_PAGE_5 ──MAP──> CACHE_SET_1   (collision!)
```

### Problem
Both PDs on same core, both using cache set 1 → side-channel risk.

### Desired Outcome
Search discovers: move PD_2 to CPU_2, or remap PHYS_PAGE_5 to a page using different cache set.

---

## Scenario B: Cross-Core LLC Collision

### Initial State
```
PD_1 ──HOLD──> CPU_1
PD_2 ──HOLD──> CPU_2          (different cores)

PD_1 ──HOLD──> PHYS_PAGE_1 ──MAP──> CACHE_SET_1
PD_2 ──HOLD──> PHYS_PAGE_5 ──MAP──> CACHE_SET_1   (LLC collision!)
```

### Problem
Different cores, but L3 is shared, both using same cache set → LLC side-channel.

### Desired Outcome
Search discovers: remap one PD's physical page to avoid cache set collision (page coloring).

---

## Metric: Transitive RSI

Rather than creating a new metric, we extend RSI to follow MAP edges transitively.

### Standard RSI (existing)
```
RSI[PD_i, PD_j] = |DirectResources(PD_i) ∩ DirectResources(PD_j)| / |DirectResources(PD_i) ∪ DirectResources(PD_j)|
```
Where `DirectResources(PD)` = resources directly held via HOLD edges.

### Transitive RSI (new mode)
```
TransitiveRSI[PD_i, PD_j] = |EffectiveResources(PD_i) ∩ EffectiveResources(PD_j)| / |EffectiveResources(PD_i) ∪ EffectiveResources(PD_j)|
```
Where `EffectiveResources(PD)` = resources reached by following HOLD → MAP chains.

### Example for Cache Scenario
```
PD_1 ──HOLD──> PHYS_PAGE_1 ──MAP──> CACHE_SET_1
PD_2 ──HOLD──> PHYS_PAGE_5 ──MAP──> CACHE_SET_1

DirectResources(PD_1) = {PHYS_PAGE_1}
DirectResources(PD_2) = {PHYS_PAGE_5}
RSI = 0 / 2 = 0.0  (no direct sharing)

EffectiveResources(PD_1) = {CACHE_SET_1}  (via MAP)
EffectiveResources(PD_2) = {CACHE_SET_1}  (via MAP)
TransitiveRSI = 1 / 1 = 1.0  (complete cache set collision!)
```

**Goal:** Minimize TransitiveRSI to 0.0 (zero cache set overlap).

### Benefits of this approach
1. Reuses existing RSI formula and infrastructure
2. Generalizes to other transitive relationships (not just caches)
3. More realistic - captures indirect/effective sharing

---

## Existing Primitives Analysis

| Primitive | Applicable? | Use Case |
|-----------|-------------|----------|
| `add_pd` | Maybe | Add mediator PD? |
| `remove_pd` | Maybe | Remove unnecessary PD? |
| `add_hold_edge` | **Yes** | Assign PD to different CPU, or different PHYS_PAGE |
| `remove_hold_edge` | **Yes** | Remove PD from CPU, or remove PHYS_PAGE usage |
| `add_request_edge` | Maybe | Indirect access through mediator? |
| `remove_request_edge` | Maybe | - |
| `add_resource_space` | Maybe | - |
| `remove_resource_space` | Maybe | - |
| `add_subset_edge` | Maybe | - |
| `remove_subset_edge` | Maybe | - |

### Missing Primitives (may need to add)

| Primitive | Purpose |
|-----------|---------|
| `add_map_edge` | Create mapping from PHYS_PAGE to CACHE_SET |
| `remove_map_edge` | Remove mapping (for remapping) |

**Question:** Should MAP edges be fixed (determined by modulo) or mutable?

---

## Design Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MAP edge mutability | **Fixed** (Option A) | Realistic - hardware determines phys→cache mapping |
| Metric | **Transitive RSI** | Reuses RSI formula, follows MAP edges |
| Transformation approach | Change HOLD edges | Page coloring = change which PHYS_PAGE PD uses |

## Final Design Parameters

| Parameter | Value |
|-----------|-------|
| Cache sets | 4 (CACHE_SET_0 through CACHE_SET_3) |
| Physical pages | 8 (2 per cache set) |
| CPUs | 2 (CPU_1, CPU_2) |
| PDs | 2 (PD_1, PD_2) |

### Constraints

| Constraint | Description |
|------------|-------------|
| `requires_physical_page` | Each PD must HOLD at least 1 physical page |
| `requires_cpu` | Each PD must HOLD at least 1 CPU (scheduled somewhere) |
| `pages_substitutable` | Any physical page can substitute for another (no specific page requirements) |

### Scenario Names
- `cache_same_core_conflict` - Both PDs on same CPU, cache set collision
- `cache_llc_collision` - PDs on different CPUs, but LLC cache set collision

---

## TODO List

### Model Extensions
- [x] Add ResourceType enums: `CPU`, `CACHE_SET`, `PHYS_PAGE`
- [x] Update `generic_model.py` with new resource types (add_cpu_node, add_cache_set_node, add_phys_page_node)
- [x] Update `graph_transformations.py` with wrapper methods
- [x] Extend `_calculate_rsi_per_pd_pair` to support `follow_map_edges` parameter
- [x] Add `TransitiveRSI` metric to `ComputeMetrics`

### Primitive Extensions
- [x] Extend `add_hold_edge` candidate finding to work with CPU and PHYS_PAGE resources
- [x] Update `_find_add_hold_edge_candidates` in scenarios.py to find CPU/PHYS_PAGE candidates
- [x] Add `_calculate_transitive_rsi_improvement` helper for scoring PHYS_PAGE candidates
- [x] Update `_apply_primitive` for add_hold_edge to handle different resource types
- [x] `remove_hold_edge` already works generically (no changes needed)
- [x] (No need for add_map_edge - MAP edges are fixed)

### Scenario Implementation
- [x] Create graph builder for `cache_same_core_conflict`
  - [x] Create CPU_SPACE with 2 CPUs (CPU_1, CPU_2)
  - [x] Create CACHE_SET_SPACE with 4 cache sets
  - [x] Create PHYS_PAGE_SPACE with 8 pages
  - [x] Add fixed MAP edges (page_id % 4 → cache set)
  - [x] Initial state: both PDs on CPU_1, both using pages that map to CACHE_SET_1
- [x] Create graph builder for `cache_llc_collision`
  - [x] Same resource setup as above
  - [x] Initial state: PD_1 on CPU_1, PD_2 on CPU_2, but both using pages mapping to CACHE_SET_1
- [x] Define Goal: TransitiveRSI[PD_1, PD_2] → 0.0 (minimize)
- [x] Define constraints:
  - [x] `requires_resource_type` for PHYS_PAGE (min 1) for PD_1 and PD_2
  - [x] `requires_resource_type` for CPU (min 1) for PD_1 and PD_2
- [x] Add scenarios to `scenarios.py`

### Metric Implementation
- [x] Add `follow_map_edges` parameter to RSI calculation
- [x] Implement transitive resource collection (follow MAP edges)
- [x] Test with simple graph to verify calculation

### Testing
- [x] Test scenario A (`cache_same_core_conflict`) loads correctly
- [x] Test scenario B (`cache_llc_collision`) loads correctly
- [x] Validate TransitiveRSI metric calculation:
  - `cache_same_core_conflict`: TransitiveRSI = 1.0 → 0.33 (page coloring) → 0.0 (+ CPU migration)
  - `cache_llc_collision`: TransitiveRSI = 0.33 → 0.0 (page coloring only)
- [x] Run full isosearch - search runs and explores candidates correctly
  - Note: `requires_resource_type` constraint validation not implemented (future work)

### Remaining Work (optional)
- [ ] Implement `requires_resource_type` constraint validation in constraint_validation.py
- [ ] Add more comprehensive scoring for TransitiveRSI goal optimization

---

## Notes

### How the Search Would Work (Example)

**Scenario A: Same-core conflict**

Initial state:
```
PD_1 ──HOLD──> CPU_1
PD_2 ──HOLD──> CPU_1
PD_1 ──HOLD──> PHYS_PAGE_1 ──MAP──> CACHE_SET_1
PD_2 ──HOLD──> PHYS_PAGE_5 ──MAP──> CACHE_SET_1
TransitiveRSI = 1.0 (both use CACHE_SET_1)
```

Available physical pages (pre-created with fixed MAP edges):
```
PHYS_PAGE_1 ──MAP──> CACHE_SET_1
PHYS_PAGE_2 ──MAP──> CACHE_SET_2
PHYS_PAGE_3 ──MAP──> CACHE_SET_3
PHYS_PAGE_4 ──MAP──> CACHE_SET_0
PHYS_PAGE_5 ──MAP──> CACHE_SET_1
PHYS_PAGE_6 ──MAP──> CACHE_SET_2
PHYS_PAGE_7 ──MAP──> CACHE_SET_3
PHYS_PAGE_8 ──MAP──> CACHE_SET_0
```

Search explores:
1. `remove_hold_edge(PD_2, PHYS_PAGE_5)` - disconnect from colliding page
2. `add_hold_edge(PD_2, PHYS_PAGE_2)` - connect to page in different cache set

Final state:
```
PD_1 ──HOLD──> PHYS_PAGE_1 ──MAP──> CACHE_SET_1
PD_2 ──HOLD──> PHYS_PAGE_2 ──MAP──> CACHE_SET_2
TransitiveRSI = 0.0 (no cache set overlap!)
```

This is essentially **page coloring** discovered automatically!

### Discussion Log
- Decided on L3 cache model
- Using modulo-based mapping (page_id % num_sets)
- Two scenarios: same-core + cross-core
- Reusing RSI with transitive mode instead of new CSI metric
- Fixed MAP edges, mutable HOLD edges (Option A)
- Confirmed: 4 cache sets, 8 physical pages, 2 CPUs
- Constraints: must have physical page, must have CPU, pages are substitutable
- Scenario names: `cache_same_core_conflict`, `cache_llc_collision`

