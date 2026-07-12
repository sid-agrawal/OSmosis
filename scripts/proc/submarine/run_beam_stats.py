"""
Run all 4 paper scenarios with BeamSearchExploration and extract clean stats.
Suppresses verbose output, reports: iter-to-first-solution, total candidates evaluated,
total discarded, solutions found, wall-clock time.
"""
import sys
import os
import time
import io
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# We need to import the module but suppress all its startup prints
import builtins
_real_print = builtins.print

SUPPRESS = True

def silent_print(*args, **kwargs):
    pass

# Patch print before import to suppress module-level prints
builtins.print = silent_print
import isosearch
import scenarios as sc
builtins.print = _real_print

# Patch the module's internal print too
isosearch_module_print = isosearch.__builtins__ if hasattr(isosearch, '__builtins__') else None


def run_scenario(scenario_name, beam_width=12, max_depth=10):
    """Run BeamSearchExploration for a named scenario and collect stats."""
    # Load scenario
    scenario = sc.SCENARIOS.get(scenario_name)
    if scenario is None:
        print(f"  ERROR: scenario '{scenario_name}' not found")
        return None

    # Capture all output during the run
    buf = io.StringIO()
    t0 = time.perf_counter()

    with redirect_stdout(buf), redirect_stderr(buf):
        result = isosearch.BeamSearchExploration(
            scenario,
            beam_width=beam_width,
            max_depth=max_depth
        )

    elapsed = time.perf_counter() - t0
    output = buf.getvalue()

    # Parse output for stats
    # The BeamSearchExploration output contains lines like:
    #   "Iteration N: X candidates evaluated, Y discarded, Z solutions found"
    # and "Solution found at iteration N"
    lines = output.splitlines()

    total_evaluated = 0
    total_discarded = 0
    total_solutions = 0
    first_solution_iter = None

    # Try to extract from the output
    import re
    for line in lines:
        # Match iteration summary lines
        m = re.search(r'[Ii]teration\s+(\d+).*?(\d+)\s+candidates.*?(\d+)\s+discarded', line)
        if m:
            iteration = int(m.group(1))
            evaluated = int(m.group(2))
            discarded = int(m.group(3))
            total_evaluated += evaluated
            total_discarded += discarded

        # Match solution discovery
        m2 = re.search(r'[Ss]olution.*?iter.*?(\d+)', line)
        if m2 and first_solution_iter is None:
            first_solution_iter = int(m2.group(1))

        m3 = re.search(r'(\d+)\s+solution', line)
        if m3:
            total_solutions = max(total_solutions, int(m3.group(1)))

    # Also check result object directly
    solutions = []
    if result is not None:
        if hasattr(result, 'solutions'):
            solutions = result.solutions
        elif isinstance(result, (list, set)):
            solutions = list(result)
        elif hasattr(result, '__iter__'):
            solutions = list(result)

    # Try to get stats from result object
    candidates_evaluated = total_evaluated
    candidates_discarded = total_discarded
    num_solutions = len(solutions) if solutions else total_solutions

    # Check if result has metadata
    if hasattr(result, 'stats'):
        stats = result.stats
        candidates_evaluated = getattr(stats, 'candidates_evaluated', candidates_evaluated)
        candidates_discarded = getattr(stats, 'candidates_discarded', candidates_discarded)
        first_solution_iter = getattr(stats, 'first_solution_iter', first_solution_iter)

    return {
        'scenario': scenario_name,
        'beam_width': beam_width,
        'max_depth': max_depth,
        'candidates_evaluated': candidates_evaluated,
        'candidates_discarded': candidates_discarded,
        'solutions': num_solutions,
        'first_solution_iter': first_solution_iter,
        'elapsed': elapsed,
        'raw_output': output,
        'result': result,
    }


PAPER_SCENARIOS = [
    ('mediation',       'mediator_test_primitive', 12, 10),
    ('privatization',   'reduce_isolation',        12, 10),
    ('increase sharing','basic_sharing_primitive',  12, 10),
    ('privsep',         'privsep',                 12, 30),
]

print("Running all 4 paper scenarios with BeamSearchExploration (beam_width=12)")
print("=" * 70)

all_results = {}
for (label, name, bw, depth) in PAPER_SCENARIOS:
    print(f"\n[{label}] scenario={name}, beam_width={bw}, max_depth={depth}")
    r = run_scenario(name, beam_width=bw, max_depth=depth)
    all_results[label] = r
    if r:
        print(f"  elapsed:            {r['elapsed']:.2f}s")
        print(f"  first_sol_iter:     {r['first_solution_iter']}")
        print(f"  candidates_eval:    {r['candidates_evaluated']}")
        print(f"  candidates_disc:    {r['candidates_discarded']}")
        print(f"  solutions:          {r['solutions']}")
        if r['candidates_evaluated'] == 0:
            print(f"  [raw output snippet]:")
            for line in r['raw_output'].splitlines()[:40]:
                print(f"    {line}")

print("\n" + "=" * 70)
print("SUMMARY TABLE (for paper)")
print(f"{'Case Study':<20} {'Depth':>6} {'1st-iter':>8} {'Eval':>6} {'Disc':>6} {'Sol':>5} {'Time(s)':>8}")
print("-" * 70)
for (label, name, bw, depth) in PAPER_SCENARIOS:
    r = all_results.get(label)
    if r:
        fi = r['first_solution_iter'] if r['first_solution_iter'] is not None else '?'
        print(f"{label:<20} {depth:>6} {str(fi):>8} {r['candidates_evaluated']:>6} {r['candidates_discarded']:>6} {r['solutions']:>5} {r['elapsed']:>8.1f}")
