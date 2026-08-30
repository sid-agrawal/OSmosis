"""Build the PAGE_QUOTA_SPACE_181 cohort subgraph from the real Linux extraction."""
import sys, os
sys.path.insert(0, os.environ.get("ISOSEARCH_DIR",
    os.path.expanduser("~/OSmosis-isosearch/scripts/proc/submarine")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generic_model import ModelGraph
from load_real import load

CSV = "/tmp/linux_user.csv"
SPACE = "PAGE_QUOTA_SPACE_181"

def build_scoped(csv=CSV, space=SPACE, drop_pid1=True):
    mg, _ = load(csv)
    g = mg.g
    ntype = {n: d.get('type') for n, d in g.nodes(data=True)}
    data = {n: d.get('data') for n, d in g.nodes(data=True)}
    name = {n: data[n] for n, t in ntype.items() if t == 'PD'}
    cohort = frozenset(u for u, v, d in g.edges(data=True)
                       if d.get('type') == 'HOLD' and v == space and u in name
                       and not (drop_pid1 and name[u] == 'systemd'))
    held = set()
    for u, v, d in g.edges(data=True):
        if d.get('type') == 'HOLD' and u in cohort:
            held.add(v)
    vmrs = frozenset(n for n in held if data.get(n) == 'VMR')
    mos = set()
    for u, v, d in g.edges(data=True):
        if d.get('type') == 'MAP' and u in vmrs:
            mos.add(v)
    keep = set(cohort) | held | mos
    sub = ModelGraph()
    sub.g = g.subgraph(keep).copy()
    targets = sorted(p for p in cohort if name[p] == 'claude')
    return sub, targets, cohort, name

if __name__ == "__main__":
    sub, targets, cohort, name = build_scoped()
    print(f"scoped: nodes={sub.g.number_of_nodes()} edges={sub.g.number_of_edges()}")
    print(f"cohort={len(cohort)} targets={[(t, name[t]) for t in targets]}")
