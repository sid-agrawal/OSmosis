"""IsoSearch on the real Linux graph, with progress streamed to disk.

The earlier runner buffered the search's stdout in memory, so a run killed at its time
limit left no record of how far it got. This one filters the search's output line by
line and writes the interesting lines through immediately, so a partial run is still
evidence.
"""
import sys, os, re, time, io, json
sys.path.insert(0, "/home/siagraw/OSmosis-isosearch/scripts/proc/submarine")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--beam", type=int, default=12)
ap.add_argument("--depth", type=int, default=10)
ap.add_argument("--target", type=int, default=10)
a = ap.parse_args()

class Tee(io.TextIOBase):
    """Pass through only progress-bearing lines, unbuffered."""
    KEEP = re.compile(r"Beam Search Iteration|SOLUTION FOUND|Total candidates generated|best-state metrics|"
                      r"Selected \d+ diverse|converged|plateau|Final beam")
    def __init__(self, out):
        self.out = out; self.buf = ""
    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if self.KEEP.search(line):
                self.out.write(f"[{time.strftime('%H:%M:%S')}] {line.strip()}\n")
                self.out.flush()
        return len(s)

import builtins; _p = builtins.print
import isosearch
from scenarios import Scenario, Goal, Constraint, PRIMITIVES, goal_scope
from privspace import PrivatizeSpace
from scoped import build_scoped

sub, targets, cohort, name = build_scoped()
claude = targets[0]
# One goal per resource-space type, rather than one goal over their union. The union is
# dominated by whichever namespace is most widely shared, so privatizing any single one
# leaves it unchanged and the search sees no progress; scored per type, each
# privatization satisfies its own goal.
_types = sorted({sub.g.nodes[v].get("data")
                 for u, v, d in sub.g.out_edges(claude, data=True)
                 if d.get("type") == "HOLD"
                 and sub.g.nodes.get(v, {}).get("type") == "RESOURCE_SPACE"})
goals = [Goal(f"TCB:SPACE:{st}", 0, "minimize", claude) for st in _types]
priv = [v for u, v, d in sub.g.edges(data=True)
        if d.get("type") == "HOLD" and u == claude
        and sub.g.nodes.get(v, {}).get("type") == "RESOURCE"]
cons = [Constraint("requires_resource_exists", None, r, properties={"mandatory": True})
        for r in priv[:5]]
# The process must remain a member of a namespace of every type it started in.
# Without this, an isolation goal is satisfiable by holding no namespace at all, which
# scores perfectly and describes a process that cannot run.
_space_types = sorted({sub.g.nodes[v].get("data")
                       for u, v, d in sub.g.out_edges(claude, data=True)
                       if d.get("type") == "HOLD"
                       and sub.g.nodes.get(v, {}).get("type") == "RESOURCE_SPACE"})
cons += [Constraint("requires_resource_space_type", claude, st, properties={"min_count": 1})
         for st in _space_types]
scope = goal_scope(sub, cons, goals)
before = isosearch._fast_tcb_spaces(sub, claude)
isosearch.set_goal_baselines(sub, goals)

_p(f"graph        : {sub.g.number_of_nodes():,} nodes / {sub.g.number_of_edges():,} edges")
_p(f"target PD    : {claude} ({name[claude]})")
_p(f"goals        : {len(goals)}, one per space type {_types}")
_p(f"constraints  : {len(cons)}")
_p(f"binding scope: {len(scope):,} nodes")
_p(f"config       : beam_width={a.beam}, depth={a.depth}")
_p(f"started      : {time.strftime('%Y-%m-%d %H:%M:%S')}\n", flush=True)

class _ScenarioWithExtra(Scenario):
    """Scenario.get_allowed_transitions resolves names against the global PRIMITIVES,
    so a transition defined for a single scenario is silently dropped. Append it here."""
    def get_allowed_transitions(self):
        return super().get_allowed_transitions() + [PrivatizeSpace()]


scen = _ScenarioWithExtra(name="Isolate a shell session on a real Linux system",
                description="minimize resource-space sharing for one PD",
                goals=goals, constraints=cons,
                allowed_primitives=PRIMITIVES,
                allowed_multistep=[],
                graph_builder=lambda: sub)

t0 = time.perf_counter()
tee = Tee(sys.stdout)
old = sys.stdout
try:
    sys.stdout = tee
    res = isosearch.BeamSearchExploration(scen, beam_width=a.beam, max_depth=a.depth,
                                          seed=20260827)
finally:
    sys.stdout = old
el = time.perf_counter() - t0
_p(f"\ncompleted in {el:,.1f}s ({el/3600:.2f} h)")
_p(f"solutions: {len(res) if res else 0}")
if res:
    best = min((r for r in res if isinstance(r, dict) and 'graph' in r),
               key=lambda r: isosearch._fast_tcb_spaces(r['graph'], claude), default=None)
    if best:
        _p(f"best TCB:SPACE: {isosearch._fast_tcb_spaces(best['graph'], claude)} (from {before})")
        _p(f"path: {' -> '.join(best.get('beam_path', [])[:8])}")
