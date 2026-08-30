"""R102's scenario: 'A linux box has 100s of PDs, where we could have a scenario
where we want to move some of them into a container or alike to provide additional
isolation *to every other PD* how well does that scale?'

Encoding. G0 is a Linux-box-shaped graph: N PDs all holding one shared FILE (the
resource a container boundary would cut), plus a spare FILE available so a private
alternative exists. The target set T = {PD_1, PD_2} is the pair to 'move into a
container'. Goals: RSI(t, o) = 0 for every t in T and every o not in T, so the goal
count grows as |T| * (N - |T|). Constraint: every PD must retain access to a TEMP
file, so the search cannot 'isolate' by deleting everything.

This differs from the earlier padding experiments in the way that matters: there the
added PDs were irrelevant to the goal, here EVERY added PD is named by a goal, which
is what Reto actually asked about.
"""
import sys, os
sys.path.insert(0, os.environ.get("ISOSEARCH_DIR",
    os.path.expanduser("~/OSmosis-isosearch/scripts/proc/submarine")))
from generic_model import ModelGraph, ResourceType, Permission, FileType
from scenarios import (NodeTransformations, EdgeTransformations, Scenario,
                       Goal, Constraint, PRIMITIVES)

TARGETS = (1, 2)   # the PDs to containerize


def build(n_pds):
    g = ModelGraph()
    ids = [NodeTransformations.add_pd_node(g, f"PD_{i}") for i in range(1, n_pds + 1)]
    sp = NodeTransformations.add_resource_space(g, ResourceType.FILE)
    shared = NodeTransformations.add_file_resource(g, sp, FileType.TEMP, "/tmp/shared.tmp", 2048)
    # a spare, initially unheld, so a private alternative exists
    NodeTransformations.add_file_resource(g, sp, FileType.TEMP, "/tmp/spare.tmp", 1024)
    for pid in ids:
        EdgeTransformations.add_hold_edge(g, {Permission.R, Permission.W}, pid,
                                          ResourceType.FILE, sp, shared)
    return g


def scenario(n_pds):
    others = [i for i in range(1, n_pds + 1) if i not in TARGETS]
    goals = [Goal("RSI", 0.0, "minimize", f"PD_{t},PD_{o}")
             for t in TARGETS for o in others]
    cons = [Constraint("requires_resource_exists", None, "FILE_1_1",
                       properties={"mandatory": True})]
    cons += [Constraint("requires_file_access", i, "FILE",
                        properties={"file_type": "TEMP", "min_size_kb": 1})
             for i in range(1, n_pds + 1)]
    return Scenario(
        name=f"Containerize {len(TARGETS)} of {n_pds} PDs",
        description=f"Isolate PD_{TARGETS[0]},PD_{TARGETS[1]} from the other {len(others)} PDs",
        goals=goals, constraints=cons,
        allowed_primitives=PRIMITIVES, allowed_multistep=[],
        graph_builder=lambda: build(n_pds))


if __name__ == "__main__":
    for n in (4, 6, 10):
        s = scenario(n); g = s.build_graph().g
        print(f"N={n:3d}  nodes={g.number_of_nodes():4d} edges={g.number_of_edges():4d} "
              f"goals={len(s.goals):3d} constraints={len(s.constraints):3d}  "
              f"alpha_needed>{10*len(s.goals)}")
