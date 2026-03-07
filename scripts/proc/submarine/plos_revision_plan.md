# PLOS 2026 Revision — Submarine Repo Action Plan

Generated from: `/Users/siagraw/Documents/osmosis_papers/plos-2026-osmosis-explore/.claude/revision-plan.md`

## Priority 1 — C4: Graph Size Penalty

**Problem**: Search produces solutions with superfluous PDs/edges.
**Paper item**: C4 (`ds_exploration.tex`, `case_study.tex`)
**File**: `goal_driven_scoring.py` → `calculate_goal_driven_score()`

Steps:
1. Add size penalty term:
   ```python
   size_penalty = WEIGHT_SIZE * max(0, len(new_graph.g.nodes) - len(current_graph.g.nodes))
   score -= size_penalty
   ```
2. Tune `WEIGHT_SIZE` (start ~5.0)
3. Re-run: `basic_sharing_primitive`, `mediator_test_primitive`, `reduce_isolation`, `crypto_cache_isolation`
4. Verify: no superfluous PD_3, no spurious request edge in solutions
5. Record results + timing for Table 1

---

## Priority 2 — C5: 5-PD Scalability Scenario + Timing

**Paper item**: C5 (`case_study.tex`, `eval-tab.tex`)
**Files**: `scenarios.py`, `isosearch.py`

Steps:
1. Write `build_3tier_webapp_graph()` in `scenarios.py`:
   - 5 PDs: `PD_frontend`, `PD_api`, `PD_db`, `PD_auth`, `PD_cache`
   - Resources: session tokens, DB records, cache entries
   - G_0: fully-shared baseline
   - Goal: minimize RSI across all PD pairs for sensitive resource types
2. Add `"3tier_webapp"` to `SCENARIOS` dict
3. Add timing instrumentation to beam search loop in `isosearch.py`:
   - `time.time()` before/after iteration loop
   - Record: iterations, candidates evaluated/discarded, wall-clock time
4. Run; verify it rediscovers: DB accessible only via API server
5. Record results for Table 1

---

## Priority 3 — M2: Fill Table 1 Timing Values

**Paper item**: M2 (`eval-tab.tex`)
- After C4 + C5 produce timing data, fill `\todo{run}` cells in `eval-tab.tex`

---

## Priority 4 — M1: Verify Weight Robustness

**Paper item**: M1 (claim in `ds_exploration.tex`)
**File**: new script (e.g., `weight_sensitivity.py`) or inline in `isosearch.py`

Steps:
1. Run 3 original scenarios with ±50% perturbation of each scoring weight
2. Compare solution structure (same isolation pattern?)
3. Confirm or update the claim in the paper

---

## Priority 5 — crypto_cache_isolation End-to-End

**From last session**: scenario implemented but not tested end-to-end.
Run `crypto_cache_isolation` and verify both solutions discovered:
- Page coloring (Intel CAT) — TransitiveRSI:CACHE_SET → 0
- CPU pinning (isolcpus) — RSI:CPU → 0

Can be folded into Priority 1 re-runs.

---

## Priority 6 — C3: IB (Impact Boundary) Metric

**Paper item**: C3 + C2 (`ds_defining.tex`, `model.tex`)
**Files**: `isosearch.py`, `goal_driven_scoring.py`

Definition: IB(PD_x) = set of PDs that PD_x can affect (dual of TCB).
Implementation: for each PD, find which other PDs have this PD in their TCB.

Steps:
1. Add `_calculate_ib(graph, pd_nodes)` to `isosearch.py`
2. Add `'IB'` to `ComputeMetrics()` return dict
3. Add IB handling to `calculate_goal_driven_score()` in `goal_driven_scoring.py`
4. Add IB handling to `check_goals_satisfied()` and `GoalsMet()` in `isosearch.py`
5. Paper work: add IB to `ds_defining.tex` + `model.tex` primer

---

## Priority 7 — C2: OSmosis Primer (pure paper writing)

**Paper item**: C2 (`model.tex`)
No Python needed. Add 3 missing model invariants from published model paper:
- "Resource space nodes must be reachable from a PD via a hold edge"
- "Hold edges originate at a PD node"
- "Map edges exist only between two resource nodes or two resource space nodes"

---

## Priority 8 — I1: LLM Constraint Generation

**Paper item**: I1 (`conclusion.tex`)
**Decision needed**: run the experiment or cut the claim?

If running:
- Write thin Python wrapper calling Claude API
- Feed scenario description → generate constraints as `reachable`/`exists` predicates
- Test on 5 scenarios, report pass rate

---

## Execution Order
```
C4 (size penalty + re-runs incl. crypto)
  → C5 (5-PD scenario + timing)
    → M2 (fill table)
    → M1 (weight check)
      → C3 (IB metric)
        → C2 (paper primer writing)
        → I1 (LLM experiment or cut)
```
