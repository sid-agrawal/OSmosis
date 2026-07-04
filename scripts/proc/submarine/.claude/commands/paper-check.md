# Paper ↔ Code Cross-Check

Cross-check that the submarine code is consistent with the PLOS 2026 paper. Covers:
- Eval table stats (all 5 scenarios)
- Missing paper sections
- Algorithm listing accuracy
- Case study count consistency across all tex files

## Instructions

Working directory: `/Users/siagraw/Documents/OSmosis-mac/scripts/proc/submarine`
Paper directory: `/Users/siagraw/Documents/osmosis_papers/plos-2026-osmosis-explore/content`

### Step 1: Run authoritative stats

```bash
source .venv/bin/activate && python3 run_beam_stats2.py
```

Record the output table. These are the ground-truth numbers.

### Step 2: Check eval-tab.tex stats

Read `eval-tab.tex`. For each row, compare #Iter, #Eval, #Disc, #Sol, and Time against the fresh run output. Also check that every scenario in `PAPER_SCENARIOS` (from `run_beam_stats2.py`) has a corresponding row, and that no removed scenarios (ssh_prune, ssh_assign, ssh_discover) appear. Flag mismatches and stale rows.

### Step 3: Check case study sections

Read `case_study.tex`. For each non-Mediation scenario key in `PAPER_SCENARIOS`, verify there is a `\label{sec:eval::<scenario_key>}` in the file. The Mediation scenario lives in `sec:exploration::example` — exclude it. Flag any scenario missing a subsection. Also verify no SSH section labels (`sec:eval::ssh_prune`, `sec:eval::ssh_assign`, `sec:eval::ssh_discover`) remain.

### Step 4: Check case study count consistency

Search for the strings "eight", "seven", "six" (as case-study counts) across all tex files in the content directory. Flag any that were not updated to "five". Also check `ds_exploration.tex` for correct count references.

### Step 5: Check algorithm listing

Read `algo.tex`. Check two things:
1. In `lst:algo_scoring`: does the comment describe constraint_score as `(0..len(consts))`? If so, flag it — the actual code uses `5.0 if valid else max(0.0, 5.0 - len(violations))`, capped at 5 regardless of constraint count.
2. In `lst:exploration_algo`: does the beam selection step mention diversity-aware selection? If not, flag it — the code uses `_select_diverse_beam_states_enhanced()`.

### Step 6: Present structured report

Output a report with four sections:

```
=== STATS MISMATCHES ===
For each scenario: ✅ if all numbers match, ⚠️ with details if any differ.

=== MISSING / STALE PAPER SECTIONS ===
For each PAPER_SCENARIOS entry: ✅ if section exists, ⚠️ MISSING if not.
SSH sections removed: ✅ if absent, ⚠️ if still present.

=== COUNT CONSISTENCY ===
For each file with a case-study count: ✅ says "five" / ⚠️ still says old number.

=== ALGORITHM LISTING ISSUES ===
constraint_score comment: ✅ accurate / ⚠️ misleading
diversity enforcement: ✅ mentioned / ⚠️ not mentioned
```

### Step 7: Apply fixes

For each issue found, apply the minimal targeted edit. After all fixes, run:
```bash
cd /Users/siagraw/Documents/osmosis_papers/plos-2026-osmosis-explore && make draft
```
and confirm a clean build with no undefined references.
