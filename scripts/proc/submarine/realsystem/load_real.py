"""Load a Lintool-extracted CSV into the graph shape IsoSearch consumes."""
import sys, os, csv, time
sys.path.insert(0, os.environ.get("ISOSEARCH_DIR",
    os.path.expanduser("~/OSmosis-isosearch/scripts/proc/submarine")))
from generic_model import ModelGraph

csv.field_size_limit(10**9)

def load(path, keep_types=None, max_resources=None):
    """keep_types: restrict RESOURCE nodes to these type strings (e.g. {'FILE'}).
    max_resources: cap resources kept, for a downsampled graph."""
    mg = ModelGraph(); g = mg.g
    kept, skipped = set(), 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            nt = row["NODE_TYPE"]
            if not nt:
                continue
            nid, data = row["NODE_ID"], row["DATA"]
            if nt == "RESOURCE":
                if keep_types is not None and data not in keep_types:
                    skipped += 1; continue
                if max_resources is not None and len(kept) >= max_resources:
                    skipped += 1; continue
                kept.add(nid)
            g.add_node(nid, type=nt, data=data)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            et = row["EDGE_TYPE"]
            if not et:
                continue
            a, b = row["EDGE_FROM"], row["EDGE_TO"]
            if a in g and b in g:
                g.add_edge(a, b, type=et)
    return mg, skipped

if __name__ == "__main__":
    path = sys.argv[1]
    kt = None if len(sys.argv) < 3 or sys.argv[2] == "all" else set(sys.argv[2].split(","))
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else None
    t0 = time.perf_counter()
    mg, skipped = load(path, kt, cap)
    g = mg.g
    el = time.perf_counter() - t0
    from collections import Counter
    nk = Counter(d.get("type") for _, d in g.nodes(data=True))
    ek = Counter(d.get("type") for _, _, d in g.edges(data=True))
    print(f"loaded in {el:.1f}s   nodes={g.number_of_nodes()}  edges={g.number_of_edges()}")
    print(f"  node types: {dict(nk)}")
    print(f"  edge types: {dict(ek)}")
    print(f"  resources skipped by filter: {skipped}")
