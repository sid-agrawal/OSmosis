"""
Sensitivity sweeps for the thesis, emitting the four columns Aastha Mehta asked for
(AM052): configuration, solutions, steps to first solution, and time to first solution.

Supersedes run_sensitivity.py and run_beam_depth_sensitivity.py for table generation.
Three things differ from those scripts:

  1. Time to FIRST solution, not total run time. Timestamps are taken by watching the
     engine's per-iteration marker (isosearch.py: "Beam Search Iteration n/N") from a
     stdout wrapper, so isosearch.py itself is untouched and no case-study re-run is
     owed. Granularity is one iteration; both bounds are recorded.

  2. Results are written to JSON. The numbers in the thesis were transcribed from a
     terminal and never persisted, which is how the Budget-Constrained Tenant Isolation
     step count came to disagree between tab:case-study-summary (8) and
     content/exploring.tex (6 implied) for the same beam width of 12.

  3. The solution fingerprint uses the edge attribute the model actually writes.
     generic_model.py:348 writes type=<EdgeType>.name, so hold edges match
     type == 'HOLD'. run_sensitivity.py tested edge_type == 'Hold', which never matched,
     so its "structure is identical" check compared PD counts alone.

Runs are reproducible: isosearch.py seeds its RNG at import (DEFAULT_SEED).
"""
import io
import json
import os
import re
import sys
import time
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import builtins
_real_print = builtins.print
builtins.print = lambda *a, **k: None
import isosearch
import scenarios as sc
builtins.print = _real_print

ITER_RE = re.compile(r'Beam Search Iteration (\d+)/')
GEN_RE = re.compile(r'Generated\s+(\d+)\s+candidate')


class StampingBuffer(io.StringIO):
    """Captures engine output and timestamps each iteration boundary."""

    def __init__(self):
        super().__init__()
        self.iter_starts = {}

    def write(self, s):
        m = ITER_RE.search(s)
        if m:
            self.iter_starts.setdefault(int(m.group(1)), time.perf_counter())
        return super().write(s)


def fingerprint(result):
    """(PD count, hold-edge count) per complete solution. Sorted for JSON stability."""
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
    return sorted(fps)


def run_one(name, bw, depth, cw=None):
    scenario = sc.SCENARIOS.get(name)
    if scenario is None:
        return {'error': f"scenario '{name}' not found"}

    kwargs = {'beam_width': bw, 'max_depth': depth}
    if cw is not None:
        kwargs['constraint_weight'] = cw

    buf = StampingBuffer()
    t0 = time.perf_counter()
    with redirect_stdout(buf), redirect_stderr(buf):
        result = isosearch.BeamSearchExploration(scenario, **kwargs)
    elapsed = time.perf_counter() - t0
    if result is None:
        result = []

    out = buf.getvalue()
    solutions = [m for m in result if m.get('is_complete_solution', False)]
    first_iter = min((m['iteration'] for m in solutions), default=None)

    # The solution appears during iteration `first_iter`, so the start of that iteration
    # lower-bounds the time and the start of the next upper-bounds it. When the solution
    # lands in the final iteration there is no next marker; the run's end bounds it.
    t_lo = t_hi = None
    if first_iter is not None:
        s_lo = buf.iter_starts.get(first_iter)
        s_hi = buf.iter_starts.get(first_iter + 1)
        if s_lo is not None:
            t_lo = s_lo - t0
        t_hi = (s_hi - t0) if s_hi is not None else elapsed

    return {
        'beam_width': bw,
        'max_depth': depth,
        'constraint_weight': cw,
        'candidates_generated': sum(int(m) for m in GEN_RE.findall(out)),
        'solutions': len(solutions),
        'first_solution_iteration': first_iter,
        'time_to_first_solution': t_hi,
        'time_to_first_solution_lower': t_lo,
        'total_elapsed': elapsed,
        'fingerprint': fingerprint(result),
    }


# (label, scenario, default beam_width, default max_depth); labels match the thesis.
SCENARIOS = [
    ('Mediation',                           'mediator_test_primitive', 12, 10),
    ('Policy-Driven Privilege Separation',  'db_trust',                12, 25),
    ('Budget-Constrained Tenant Isolation', 'ml_tenant',               12, 12),
    ('CPU Isolation',                       'crypto_cache_isolation',  12, 12),
    ('Multi-Tenant ML Platform',            'ml_tenant_hw_isolation',  24, 24),
]

WEIGHT_SCENARIOS = ['Mediation', 'Policy-Driven Privilege Separation',
                    'Budget-Constrained Tenant Isolation', 'CPU Isolation',
                    'Multi-Tenant ML Platform']
CONSTRAINT_WEIGHTS = [10, 20, 50, 60]

BEAM_WIDTHS = [4, 8, 12, 20]
DEPTHS = [8, 12, 20]
EXTRA_BEAM_WIDTHS = {'Multi-Tenant ML Platform': [4, 8, 12, 20, 24]}
EXTRA_DEPTHS = {
    'Multi-Tenant ML Platform': [8, 12, 20, 24],
    'Policy-Driven Privilege Separation': [8, 12, 20, 25],
}

JOINT_SCENARIO = ('Multi-Tenant ML Platform', 'ml_tenant_hw_isolation')
JOINT_BEAM_WIDTHS = [8, 12, 16, 20, 24]
JOINT_DEPTHS = [8, 12, 16, 20, 24]

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sweep_results.json')
BY_LABEL = {lbl: (nm, bw, d) for lbl, nm, bw, d in SCENARIOS}

results = {'weights': {}, 'beam_width': {}, 'depth': {}, 'joint': {},
           'meta': {'seed': isosearch.DEFAULT_SEED,
                    'generated': time.strftime('%Y-%m-%d %H:%M:%S')}}
total = (len(WEIGHT_SCENARIOS) * len(CONSTRAINT_WEIGHTS)
         + sum(len(EXTRA_BEAM_WIDTHS.get(l, BEAM_WIDTHS)) for l, *_ in SCENARIOS)
         + sum(len(EXTRA_DEPTHS.get(l, DEPTHS)) for l, *_ in SCENARIOS)
         + len(JOINT_BEAM_WIDTHS) * len(JOINT_DEPTHS))
done = 0


def emit(sweep, label, key, rec):
    global done
    done += 1
    results[sweep].setdefault(label, {})[str(key)] = rec
    _real_print(f"[{done:>3}/{total}] {sweep:<11} {label:<38} {key!s:<10} "
                f"1st={rec.get('first_solution_iteration')} "
                f"sol={rec.get('solutions')} "
                f"t1st={rec.get('time_to_first_solution')} "
                f"tot={rec.get('total_elapsed', 0):.1f}s", flush=True)
    with open(OUT, 'w') as f:
        json.dump(results, f, indent=2)


_real_print(f"Running {total} configurations; results stream to {OUT}", flush=True)

for label in WEIGHT_SCENARIOS:
    name, bw, depth = BY_LABEL[label]
    for cw in CONSTRAINT_WEIGHTS:
        emit('weights', label, cw, run_one(name, bw, depth, cw=cw))

for label, name, def_bw, def_depth in SCENARIOS:
    for bw in EXTRA_BEAM_WIDTHS.get(label, BEAM_WIDTHS):
        emit('beam_width', label, bw, run_one(name, bw, def_depth))

for label, name, def_bw, def_depth in SCENARIOS:
    for depth in EXTRA_DEPTHS.get(label, DEPTHS):
        emit('depth', label, depth, run_one(name, def_bw, depth))

joint_label, joint_name = JOINT_SCENARIO
for bw in JOINT_BEAM_WIDTHS:
    for depth in JOINT_DEPTHS:
        emit('joint', joint_label, f"{bw}x{depth}", run_one(joint_name, bw, depth))

_real_print(f"\nDone. {done} configurations written to {OUT}")
