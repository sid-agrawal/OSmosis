"""A scenario-local transition: swap a shared resource-space for a private one.

Removing a hold-edge to a namespace models a PD giving up that namespace, which is not
what containerization does: a process always has an IPC namespace, it just stops sharing
the one everyone else uses. The faithful move is remove-then-add, and the transition set
in scenarios.py cannot express it (add_resource_space creates only FILE spaces, and
add_hold_edge connects PDs to resources, never to spaces).

This lives outside PRIMITIVES so the case studies are unaffected: it is added only to the
scenario that needs it.
"""
import sys, os
sys.path.insert(0, os.environ.get("ISOSEARCH_DIR",
    os.path.expanduser("~/OSmosis-isosearch/scripts/proc/submarine")))
from scenarios import Transition, goal_scope


class PrivatizeSpace(Transition):
    """For a PD holding a shared resource-space, replace it with a private one."""

    def __init__(self):
        super().__init__(name="privatize_space",
                         description="Swap a shared resource-space for a private one",
                         transition_type="primitive")
        self._counter = 0

    def find_candidates(self, graph, constraints, goals=None):
        scope = goal_scope(graph, constraints, goals)
        g = graph.g
        out = []
        pds = [n for n, d in g.nodes(data=True) if d.get('type') == 'PD'
               and (scope is None or n in scope)]
        for pd in pds:
            for _, sp, d in g.out_edges(pd, data=True):
                if d.get('type') != 'HOLD':
                    continue
                if g.nodes.get(sp, {}).get('type') != 'RESOURCE_SPACE':
                    continue
                # only worth doing if somebody else holds it
                others = sum(1 for u, _, dd in g.in_edges(sp, data=True)
                             if dd.get('type') == 'HOLD' and u != pd
                             and g.nodes.get(u, {}).get('type') == 'PD')
                if others == 0:
                    continue
                out.append({
                    'param_values': {'pd': pd, 'space': sp},
                    'target_description': f"give {pd} a private {g.nodes[sp].get('data')} space",
                    'constraint_relevance': 0.9,
                    'addresses_violation': False,
                })
        return out

    def apply(self, graph, param_values):
        g = graph.g
        pd = param_values.get('pd')
        sp = param_values.get('space')
        if pd is None or sp is None or pd not in g or sp not in g:
            return False
        stype = g.nodes[sp].get('data')
        self._counter += 1
        new_sp = f"{stype}_SPACE_private_{pd.split('_')[-1]}_{self._counter}"
        if g.has_edge(pd, sp):
            keys = list(g[pd][sp].keys())
            for k in keys:
                if g[pd][sp][k].get('type') == 'HOLD':
                    g.remove_edge(pd, sp, key=k)
                    break
        g.add_node(new_sp, type='RESOURCE_SPACE', data=stype)
        g.add_edge(pd, new_sp, type='HOLD')
        return True
