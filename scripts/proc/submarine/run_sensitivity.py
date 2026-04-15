"""
Sensitivity analysis for scoring weights in BeamSearchExploration.

Varies constraint_weight across {5, 10, 20, 50} on three representative scenarios
(mediation, ssh_prune, ml_tenant) and reports iterations-to-first-solution and
whether the final solution graph structure changes.
"""
import sys
import time
import io
import re
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, '/Users/siagraw/Documents/OSmosis-mac/scripts/proc/submarine')

import builtins
_real_print = builtins.print
builtins.print = lambda *a, **k: None
import isosearch
import scenarios as sc
builtins.print = _real_print


def parse_beam_output(output, result):
    """Parse verbose beam search output for stats."""
    lines = output.splitlines()

    per_iter_candidates = []
    for line in lines:
        m = re.search(r'Total candidates generated:\s*(\d+)', line)
        if m:
            per_iter_candidates.append(int(m.group(1)))

    per_state_generated = []
    for line in lines:
        m = re.search(r'Generated\s+(\d+)\s+candidate', line)
        if m:
            per_state_generated.append(int(m.group(1)))

    complete_solutions = [m for m in result if m.get('is_complete_solution', False)]
    num_solutions = len(complete_solutions)

    if complete_solutions:
        first_sol_iter = min(m['iteration'] for m in complete_solutions)
    else:
        first_sol_iter = None

    return {
        'total_generated': sum(per_state_generated),
        'solutions': num_solutions,
        'first_sol_iter': first_sol_iter,
    }


def solution_fingerprint(result):
    """Return a frozenset of (pd_count, hold_edge_count) tuples from complete solutions."""
    fps = set()
    for m in result:
        if not m.get('is_complete_solution', False):
            continue
        mg = m.get('graph')
        if mg is None:
            continue
        g = mg.g  # underlying networkx graph
        pds = [n for n, d in g.nodes(data=True) if d.get('type') == 'PD']
        holds = [(u, v) for u, v, d in g.edges(data=True) if d.get('edge_type') == 'Hold']
        fps.add((len(pds), len(holds)))
    return frozenset(fps)


# Scenarios: (label, scenario_name, beam_width, depth)
SENSITIVITY_SCENARIOS = [
    ('Mediation',        'mediator_test_primitive', 12, 10),
    ('Priv Sep (Prune)', 'ssh_prune',               12, 13),
    ('ML Tenant',        'ml_tenant',               12, 12),
]

CONSTRAINT_WEIGHTS = [5, 10, 20, 50]

_real_print("Sensitivity Analysis: varying constraint_weight")
_real_print(f"Scenarios: Mediation, Priv Sep (Prune), ML Tenant")
_real_print(f"Weights tested: {CONSTRAINT_WEIGHTS}")
_real_print("=" * 90)

# Collect results keyed by (scenario, weight)
all_results = {}

for (label, name, bw, depth) in SENSITIVITY_SCENARIOS:
    scenario = sc.SCENARIOS.get(name)
    if scenario is None:
        _real_print(f"ERROR: scenario '{name}' not found")
        continue

    baseline_fp = None
    for cw in CONSTRAINT_WEIGHTS:
        buf = io.StringIO()
        t0 = time.perf_counter()
        with redirect_stdout(buf), redirect_stderr(buf):
            result = isosearch.BeamSearchExploration(
                scenario, beam_width=bw, max_depth=depth, constraint_weight=cw
            )
        elapsed = time.perf_counter() - t0
        if result is None:
            result = []
        stats = parse_beam_output(buf.getvalue(), result)
        fp = solution_fingerprint(result)
        if baseline_fp is None:
            baseline_fp = fp
        all_results[(label, cw)] = {**stats, 'elapsed': elapsed, 'fp': fp, 'fp_match': fp == baseline_fp}

_real_print(f"\n{'Scenario':<22} {'CW':>4} {'1st-Sol':>8} {'#Gen':>8} {'#Sol':>5} {'Time(s)':>8} {'Sol same?':>10}")
_real_print("-" * 72)

for (label, name, bw, depth) in SENSITIVITY_SCENARIOS:
    for cw in CONSTRAINT_WEIGHTS:
        key = (label, cw)
        if key not in all_results:
            continue
        s = all_results[key]
        fi = str(s['first_sol_iter']) if s['first_sol_iter'] is not None else 'none'
        same = 'YES' if s['fp_match'] else 'NO *'
        marker = ' (baseline)' if cw == 20 else ''
        _real_print(f"{label:<22} {cw:>4} {fi:>8} {s['total_generated']:>8} {s['solutions']:>5} {s['elapsed']:>8.1f} {same:>10}{marker}")
    _real_print()

_real_print("\nNotes:")
_real_print("  CW = constraint_weight (default = 20)")
_real_print("  1st-Sol = iteration number of first complete solution")
_real_print("  Sol same? = YES if solution fingerprint (PD count, hold-edge count) matches baseline (CW=20)")
_real_print("  * = solution structure differs from baseline")
