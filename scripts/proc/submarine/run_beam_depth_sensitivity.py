"""
Sensitivity analysis for beam width and depth bound in BeamSearchExploration.

Varies beam_width across {4, 8, 12, 20} and max_depth across {8, 12, 20} (each swept
independently, holding the other at its scenario default) on three representative
scenarios (mediation, ssh_prune, ml_tenant) and reports iterations-to-first-solution,
candidates generated, number of solutions, wall-clock time, and whether the final
solution graph structure changes.
"""
import sys
import os
import time
import io
import re
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import builtins
_real_print = builtins.print
builtins.print = lambda *a, **k: None
import isosearch
import scenarios as sc
builtins.print = _real_print


def parse_beam_output(output, result):
    """Parse verbose beam search output for stats."""
    lines = output.splitlines()

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
        g = mg.g
        pds = [n for n, d in g.nodes(data=True) if d.get('type') == 'PD']
        holds = [(u, v) for u, v, d in g.edges(data=True) if d.get('type') == 'HOLD']
        fps.add((len(pds), len(holds)))
    return frozenset(fps)


def run_one(name, bw, depth):
    scenario = sc.SCENARIOS.get(name)
    buf = io.StringIO()
    t0 = time.perf_counter()
    with redirect_stdout(buf), redirect_stderr(buf):
        result = isosearch.BeamSearchExploration(scenario, beam_width=bw, max_depth=depth)
    elapsed = time.perf_counter() - t0
    if result is None:
        result = []
    stats = parse_beam_output(buf.getvalue(), result)
    fp = solution_fingerprint(result)
    return {**stats, 'elapsed': elapsed, 'fp': fp}


# (label, scenario_name, default beam_width, default max_depth)
SCENARIOS_UNDER_TEST = [
    ('Mediation',        'mediator_test_primitive', 12, 10),
    ('Priv Sep (Prune)', 'ssh_prune',               12, 13),
    ('ML Tenant',        'ml_tenant',               12, 12),
]

BEAM_WIDTHS = [4, 8, 12, 20]
DEPTHS = [8, 12, 20]

_real_print("Sensitivity Analysis: varying beam_width and max_depth")
_real_print(f"Beam widths tested: {BEAM_WIDTHS} (depth held at scenario default)")
_real_print(f"Depths tested: {DEPTHS} (beam_width held at scenario default)")
_real_print("=" * 90)

bw_results = {}
depth_results = {}

for (label, name, default_bw, default_depth) in SCENARIOS_UNDER_TEST:
    if sc.SCENARIOS.get(name) is None:
        _real_print(f"ERROR: scenario '{name}' not found")
        continue

    baseline_fp = None
    for bw in BEAM_WIDTHS:
        r = run_one(name, bw, default_depth)
        if baseline_fp is None:
            baseline_fp = r['fp']
        r['fp_match'] = r['fp'] == baseline_fp
        bw_results[(label, bw)] = r

    baseline_fp = None
    for depth in DEPTHS:
        r = run_one(name, default_bw, depth)
        if baseline_fp is None:
            baseline_fp = r['fp']
        r['fp_match'] = r['fp'] == baseline_fp
        depth_results[(label, depth)] = r

_real_print(f"\n--- Beam width sweep (depth = scenario default) ---")
_real_print(f"{'Scenario':<22} {'BW':>4} {'1st-Sol':>8} {'#Gen':>8} {'#Sol':>5} {'Time(s)':>8} {'Sol same?':>10}")
_real_print("-" * 72)
for (label, name, default_bw, default_depth) in SCENARIOS_UNDER_TEST:
    for bw in BEAM_WIDTHS:
        key = (label, bw)
        if key not in bw_results:
            continue
        s = bw_results[key]
        fi = str(s['first_sol_iter']) if s['first_sol_iter'] is not None else 'none'
        same = 'YES' if s['fp_match'] else 'NO *'
        marker = ' (default)' if bw == default_bw else ''
        _real_print(f"{label:<22} {bw:>4} {fi:>8} {s['total_generated']:>8} {s['solutions']:>5} {s['elapsed']:>8.1f} {same:>10}{marker}")
    _real_print()

_real_print(f"\n--- Depth sweep (beam_width = scenario default) ---")
_real_print(f"{'Scenario':<22} {'Depth':>5} {'1st-Sol':>8} {'#Gen':>8} {'#Sol':>5} {'Time(s)':>8} {'Sol same?':>10}")
_real_print("-" * 72)
for (label, name, default_bw, default_depth) in SCENARIOS_UNDER_TEST:
    for depth in DEPTHS:
        key = (label, depth)
        if key not in depth_results:
            continue
        s = depth_results[key]
        fi = str(s['first_sol_iter']) if s['first_sol_iter'] is not None else 'none'
        same = 'YES' if s['fp_match'] else 'NO *'
        marker = ' (default)' if depth == default_depth else ''
        _real_print(f"{label:<22} {depth:>5} {fi:>8} {s['total_generated']:>8} {s['solutions']:>5} {s['elapsed']:>8.1f} {same:>10}{marker}")
    _real_print()

_real_print("\nNotes:")
_real_print("  Sol same? = YES if solution fingerprint (PD count, hold-edge count) matches the")
_real_print("  first value tested in that sweep (baseline).")
_real_print("  * = solution structure differs from baseline")
