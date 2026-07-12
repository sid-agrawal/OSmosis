"""
Run all 7 paper scenarios with BeamSearchExploration and extract clean stats.
Uses direct result inspection + regex on verbose output.
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

    # Total candidates generated per iteration (sum = total added to next_beam)
    per_iter_candidates = []
    for line in lines:
        m = re.search(r'Total candidates generated:\s*(\d+)', line)
        if m:
            per_iter_candidates.append(int(m.group(1)))

    total_added_to_beam = sum(per_iter_candidates)

    # Total generated (all_candidates before dedup/selection) = sum of "Generated N candidate(s)"
    per_state_generated = []
    for line in lines:
        m = re.search(r'Generated\s+(\d+)\s+candidate', line)
        if m:
            per_state_generated.append(int(m.group(1)))
    total_generated = sum(per_state_generated)

    # Selected into beam per iteration: "Selected N diverse states from M candidates"
    selected_into_beam = []
    next_beam_sizes = []
    for line in lines:
        m = re.search(r'Selected\s+(\d+)\s+diverse states from\s+(\d+)\s+candidates', line)
        if m:
            selected_into_beam.append(int(m.group(1)))
            next_beam_sizes.append(int(m.group(2)))

    total_discarded_from_beam = sum(m - s for m, s in zip(next_beam_sizes, selected_into_beam))

    # Solutions from result object
    complete_solutions = [m for m in result if m.get('is_complete_solution', False)]
    num_solutions = len(complete_solutions)

    # First solution iteration
    if complete_solutions:
        first_sol_iter = min(m['iteration'] for m in complete_solutions)
    else:
        first_sol_iter = None

    return {
        'total_generated': total_generated,         # all candidates scored
        'total_added_to_beam': total_added_to_beam, # candidates put in next_beam
        'total_discarded': total_discarded_from_beam,  # from beam selection pruning
        'solutions': num_solutions,
        'first_sol_iter': first_sol_iter,
    }


PAPER_SCENARIOS = [
    ('Mediation',        'mediator_test_primitive', 12, 10),
    ('Privatization',    'basic_sharing_primitive', 12, 10),   # minimize RSI
    ('Increase Sharing', 'reduce_isolation',        12, 10),   # maximize RSI
    ('ML Tenant',        'ml_tenant',               12, 12),   # RSI vs memory tradeoff
    ('DB Trust Tiers',   'db_trust',                12, 25),   # Pattern B: +1 step for add_request_edge
]


_real_print("Running all 5 paper scenarios with BeamSearchExploration (beam_width=12)")
_real_print("=" * 70)

results_table = []
for (label, name, bw, depth) in PAPER_SCENARIOS:
    _real_print(f"\n[{label}] {name}, beam_width={bw}, max_depth={depth} ...", end='', flush=True)
    scenario = sc.SCENARIOS.get(name)
    if scenario is None:
        _real_print(f" ERROR: not found")
        continue

    buf = io.StringIO()
    t0 = time.perf_counter()
    with redirect_stdout(buf), redirect_stderr(buf):
        result = isosearch.BeamSearchExploration(scenario, beam_width=bw, max_depth=depth)
    elapsed = time.perf_counter() - t0
    output = buf.getvalue()

    if result is None:
        result = []

    stats = parse_beam_output(output, result)
    stats['label'] = label
    stats['elapsed'] = elapsed
    stats['depth'] = depth
    results_table.append(stats)

    _real_print(f" done ({elapsed:.1f}s, {stats['solutions']} solutions)")

_real_print("\n" + "=" * 70)
_real_print("BEAM SEARCH RESULTS (beam_width=12)")
_real_print(f"{'Case Study':<20} {'Depth':>5} {'1st-Sol':>8} {'#Generated':>12} {'#AddedBeam':>12} {'#DiscBeam':>10} {'#Sol':>5} {'Time(s)':>8}")
_real_print("-" * 85)
for s in results_table:
    fi = str(s['first_sol_iter']) if s['first_sol_iter'] else '?'
    _real_print(f"{s['label']:<20} {s['depth']:>5} {fi:>8} {s['total_generated']:>12} {s['total_added_to_beam']:>12} {s['total_discarded']:>10} {s['solutions']:>5} {s['elapsed']:>8.1f}")

_real_print("\nNotes:")
_real_print("  #Generated = total candidates scored across all beam states all iterations")
_real_print("  #AddedBeam = candidates that made it into next_beam (after dedup)")
_real_print("  #DiscBeam  = candidates pruned by beam selection (next_beam -> current_beam)")
_real_print("  For paper: #Eval ≈ #Generated, #Disc ≈ #Generated - #AddedBeam + #DiscBeam")
