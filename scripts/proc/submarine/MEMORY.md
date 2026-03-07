# OSmosis / Submarine Memory

## Project Overview
- **Repo**: `/Users/siagraw/Documents/OSmosis-mac/scripts/proc/submarine/`
- **Paper repo**: `/Users/siagraw/Documents/osmosis_papers/plos-2026-osmosis-explore/`
- **Branch**: `cellulos`
- **Goal**: PLOS 2026 paper — "Exploring the Design Space of Isolation Mechanisms" (IsoSearch / OSmosis / Submarine)

## Key Files
- `isosearch.py` — main search engine, `ComputeMetrics()`, beam search loop
- `scenarios.py` — all scenario definitions (`SCENARIOS` dict) + graph builders
- `goal_driven_scoring.py` — scoring function `calculate_goal_driven_score()`
- `generic_model.py` — graph model, `ResourceType` enums
- `graph_transformations.py` — graph primitive operations
- `constraint_validation.py` — constraint violation counting
- Paper revision plan: `/Users/siagraw/Documents/osmosis_papers/plos-2026-osmosis-explore/.claude/revision-plan.md`

## Existing Scenarios
1. `basic_sharing_primitive` — 2 PDs, 1 shared file, goal: RSI=0
2. `mediator_test_primitive` — 2 PDs, indirect access via mediator
3. `reduce_isolation` — maximize RSI (mediated → direct access)
4. `cache_same_core_conflict` — page coloring + CPU migration (dual goals: TransitiveRSI:CACHE_SET + RSI:CPU)
5. `cache_llc_collision` — cross-core LLC isolation via page coloring
6. `crypto_cache_isolation` — TLS key server isolation (implemented, not yet end-to-end tested)

## Current Metrics in ComputeMetrics()
RSI, TransitiveRSI, RSI:CPU, RSI:PHYS_PAGE, RSI:CACHE_SET (etc.), ASR, TCB, FR
**Missing**: IB (Impact Boundary) — needed for C3

## PLOS Revision Action Plan
See `plos_revision_plan.md` for full details. Priority order:

| # | Item | File(s) | Status |
|---|------|---------|--------|
| 1 | C4: Graph size penalty in scoring | `goal_driven_scoring.py` | Pending |
| 2 | C5: 5-PD 3-tier webapp scenario + timing | `scenarios.py`, `isosearch.py` | Pending |
| 3 | M2: Fill Table 1 timing values | paper `eval-tab.tex` | Pending (needs C4+C5) |
| 4 | M1: Verify ±50% weight robustness | new script or `isosearch.py` | Pending |
| 5 | crypto end-to-end test | run `crypto_cache_isolation` | Pending |
| 6 | C3: Add IB metric | `isosearch.py`, `goal_driven_scoring.py` | Pending |
| 7 | C2: OSmosis primer (3 missing invariants) | paper `model.tex` | Pending (pure writing) |
| 8 | I1: LLM constraint generation (or cut) | new script | Pending (decide first) |
