"""
Sensitivity analysis for beam width and depth bound in BeamSearchExploration.

Varies beam_width across {4, 8, 12, 20} (plus 24 for ml_tenant_hw_isolation, its actual
working point) and max_depth across {8, 12, 20} (each swept independently, holding the
other at its scenario default) on five representative scenarios (mediation, db_trust,
ml_tenant, crypto_cache_isolation, ml_tenant_hw_isolation) and reports
iterations-to-first-solution, candidates generated, number of solutions, wall-clock time,
and whether the final solution graph structure changes.

Additionally runs a joint beam_width x depth grid for ml_tenant_hw_isolation alone -- the
one scenario in the thesis where beam-search convergence is known to be fragile (an
earlier 9-goal version never converged; the shipped 4-goal version needed beam_width=24).
This maps the empirical convergence boundary instead of relying on a single data point.
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
# Labels match the case-study names in tab:case-study-summary / content/exploring.tex.
SCENARIOS_UNDER_TEST = [
    ('Mediation',                          'mediator_test_primitive', 12, 10),
    ('Policy-Driven Privilege Separation', 'db_trust',                12, 25),
    ('Budget-Constrained Tenant Isolation','ml_tenant',               12, 12),
    ('CPU Isolation',                      'crypto_cache_isolation',  12, 12),
    ('Multi-Tenant ML Platform',           'ml_tenant_hw_isolation',  24, 24),
]

BEAM_WIDTHS = [4, 8, 12, 20]
DEPTHS = [8, 12, 20]

# ml_tenant_hw_isolation's actual working point (24) is above every value in the default
# grid above; test it there too so the independent sweep doesn't misrepresent it as
# never converging.
EXTRA_BEAM_WIDTHS = {'Multi-Tenant ML Platform': [4, 8, 12, 20, 24]}
EXTRA_DEPTHS = {
    'Multi-Tenant ML Platform': [8, 12, 20, 24],
    'Policy-Driven Privilege Separation': [8, 12, 20, 25],  # 25 is this scenario's own default
}

# Joint beam_width x depth grid, for ml_tenant_hw_isolation only -- maps the convergence
# boundary instead of relying on the single (24, 24) data point already known to work.
JOINT_GRID_SCENARIO = ('Multi-Tenant ML Platform', 'ml_tenant_hw_isolation')
JOINT_BEAM_WIDTHS = [8, 12, 16, 20, 24]
JOINT_DEPTHS = [8, 12, 16, 20, 24]

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

    bws = EXTRA_BEAM_WIDTHS.get(label, BEAM_WIDTHS)
    depths = EXTRA_DEPTHS.get(label, DEPTHS)

    baseline_fp = None
    for bw in bws:
        r = run_one(name, bw, default_depth)
        if baseline_fp is None:
            baseline_fp = r['fp']
        r['fp_match'] = r['fp'] == baseline_fp
        bw_results[(label, bw)] = r

    baseline_fp = None
    for depth in depths:
        r = run_one(name, default_bw, depth)
        if baseline_fp is None:
            baseline_fp = r['fp']
        r['fp_match'] = r['fp'] == baseline_fp
        depth_results[(label, depth)] = r

_real_print(f"\n--- Beam width sweep (depth = scenario default) ---")
_real_print(f"{'Scenario':<22} {'BW':>4} {'1st-Sol':>8} {'#Gen':>8} {'#Sol':>5} {'Time(s)':>8} {'Sol same?':>10}")
_real_print("-" * 72)
for (label, name, default_bw, default_depth) in SCENARIOS_UNDER_TEST:
    for bw in EXTRA_BEAM_WIDTHS.get(label, BEAM_WIDTHS):
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
    for depth in EXTRA_DEPTHS.get(label, DEPTHS):
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

# --- Joint beam_width x depth grid for ml_tenant_hw_isolation -------------------------
_real_print("\n" + "=" * 90)
_real_print(f"Joint beam_width x depth grid: {JOINT_GRID_SCENARIO[0]} ({JOINT_GRID_SCENARIO[1]})")
_real_print(f"beam_width x depth in {JOINT_BEAM_WIDTHS} x {JOINT_DEPTHS}")
_real_print("=" * 90)

joint_label, joint_name = JOINT_GRID_SCENARIO
joint_results = {}
for bw in JOINT_BEAM_WIDTHS:
    for depth in JOINT_DEPTHS:
        joint_results[(bw, depth)] = run_one(joint_name, bw, depth)

_real_print(f"\n{'BW \\\\ Depth':>12}" + "".join(f"{d:>10}" for d in JOINT_DEPTHS))
for bw in JOINT_BEAM_WIDTHS:
    row = f"{bw:>12}"
    for depth in JOINT_DEPTHS:
        r = joint_results[(bw, depth)]
        cell = f"{r['solutions']}sol/{r['first_sol_iter']}it" if r['solutions'] > 0 else "0 (none)"
        row += f"{cell:>10}"
    _real_print(row)

_real_print(f"\n{'Detail (bw, depth) -> #sol, 1st-iter, #gen, time(s)':<55}")
for bw in JOINT_BEAM_WIDTHS:
    for depth in JOINT_DEPTHS:
        r = joint_results[(bw, depth)]
        fi = str(r['first_sol_iter']) if r['first_sol_iter'] is not None else 'none'
        _real_print(f"  (bw={bw:>2}, depth={depth:>2}) -> #sol={r['solutions']:>3}, "
                     f"1st-iter={fi:>4}, #gen={r['total_generated']:>6}, time={r['elapsed']:>6.1f}s")

_real_print("\nNotes:")
_real_print("  Cell shows '<#sol>sol/<iter>it' if converged, '0 (none)' if no solution found")
_real_print("  within that (beam_width, depth) budget.")
