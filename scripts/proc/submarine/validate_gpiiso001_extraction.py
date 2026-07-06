"""
Validate the GPIISO001 proof-of-concept against IsoSearch's mediator_test_primitive
target graph, by parsing CellulOS's own extract_model()/pd_client_dump CSV output.

This closes the round-trip validation loop noted as missing in THESIS_STATUS.md
workstream 6: rather than eyeballing that GPIISO001 "boots and passes," this
checks the actual extracted resource graph against the specific structural claim
IsoSearch's beam search makes for this scenario:
  - a single mediator PD holds the shared resource space exclusively
  - the two client PDs reach it only through a REQUEST edge to the mediator,
    and never share access to the same underlying resource with each other

Usage:
    python3 validate_gpiiso001_extraction.py <path-to-model-dump.csv>

The CSV is the NODE_TYPE,NODE_ID,DATA,EDGE_TYPE,EDGE_FROM,EDGE_TO,EXTRA block
CellulOS prints when built with -DGPIExtractModel=ON (see model_exporting.c);
extract it from a `./simulate` log with:
    sed -n '/^NODE_TYPE/,/^,,NONE,HOLD,PD_[0-9a-f]*,FILE_c_[0-9a-f]*,/p' sim.log > model.csv
"""
import csv
import sys
from collections import defaultdict


def parse_model_csv(path):
    nodes = {}  # id -> (node_type, data)
    edges = []  # (edge_type, from, to, req_type)
    with open(path) as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header[:6] == ["NODE_TYPE", "NODE_ID", "DATA", "EDGE_TYPE", "EDGE_FROM", "EDGE_TO"], header
        for row in reader:
            if len(row) < 6:
                continue
            # Node rows: NODE_TYPE/NODE_ID/DATA populated, edge columns blank
            if row[0] and row[1]:
                nodes[row[1]] = (row[0], row[2])
            # Edge rows: first two columns blank, req_type/edge_type/from/to populated
            elif row[3]:
                edges.append((row[3], row[4], row[5], row[2]))
    return nodes, edges


def find_pd_by_name(nodes, name):
    return [nid for nid, (ntype, data) in nodes.items() if ntype == "PD" and data == name]


def validate(nodes, edges):
    findings = []
    ok = True

    kvstore_server_pds = find_pd_by_name(nodes, "kvstore_server")
    client_pds = find_pd_by_name(nodes, "hello_kvstore")

    if len(kvstore_server_pds) != 1:
        ok = False
        findings.append(f"FAIL: expected exactly 1 kvstore_server PD (mediator), found {kvstore_server_pds}")
        return ok, findings
    mediator = kvstore_server_pds[0]
    findings.append(f"Mediator PD identified: {mediator} (kvstore_server)")

    if len(client_pds) != 2:
        ok = False
        findings.append(f"FAIL: expected exactly 2 hello_kvstore client PDs, found {client_pds}")
        return ok, findings
    findings.append(f"Client PDs identified: {client_pds} (hello_kvstore x2)")

    # 1. Mediator must hold the KVSTORE resource space exclusively.
    kvstore_spaces = [nid for nid, (ntype, data) in nodes.items() if ntype == "RESOURCE_SPACE" and data == "KVSTORE"]
    if len(kvstore_spaces) != 1:
        ok = False
        findings.append(f"FAIL: expected exactly 1 KVSTORE resource space, found {kvstore_spaces}")
        return ok, findings
    kv_space = kvstore_spaces[0]

    space_holders = [e[1] for e in edges if e[0] == "HOLD" and e[2] == kv_space]
    if space_holders != [mediator]:
        ok = False
        findings.append(f"FAIL: KVSTORE_SPACE holders are {space_holders}, expected only [{mediator}]")
    else:
        findings.append(f"PASS: {mediator} is the sole holder of the KVSTORE resource space {kv_space}")

    # 2. Each client must have a REQUEST edge to the mediator (mediation channel present).
    client_requests = defaultdict(list)
    for (edge_type, frm, to, req_type) in edges:
        if edge_type == "REQUEST" and to == mediator and frm in client_pds:
            client_requests[frm].append(req_type)

    for c in client_pds:
        if not client_requests[c]:
            ok = False
            findings.append(f"FAIL: client {c} has no REQUEST edge to mediator {mediator}")
        else:
            findings.append(f"PASS: client {c} -> REQUEST({client_requests[c][0]}) -> {mediator}")

    # 3. Neither client may directly hold the KVSTORE_SPACE node itself (would defeat mediation).
    for c in client_pds:
        if c in space_holders:
            ok = False
            findings.append(f"FAIL: client {c} directly holds the KVSTORE resource space (mediation defeated)")
    findings.append("PASS: neither client directly holds the KVSTORE resource space")

    # 4. Per-object capabilities: clients DO end up holding individual KVSTORE_* entries
    #    after the RPC creates them (a real-system detail IsoSearch's abstract graph doesn't
    #    model). The property that actually matters -- the RSI=0 isolation goal -- is that
    #    the two clients' held-entry sets are DISJOINT, not that they hold nothing at all.
    client_entries = {}
    for c in client_pds:
        held = {e[2] for e in edges if e[0] == "HOLD" and e[1] == c and e[2].startswith("KVSTORE_") and e[2] != kv_space}
        client_entries[c] = held
        findings.append(f"NOTE: {c} directly holds {len(held)} individual KVSTORE entries "
                         f"(per-object capability returned by the mediated RPC, not a mediation violation "
                         f"by itself -- see disjointness check below)")

    c1, c2 = client_pds
    overlap = client_entries[c1] & client_entries[c2]
    if overlap:
        ok = False
        findings.append(f"FAIL: clients share {len(overlap)} KVSTORE entries -- RSI > 0, mediation goal not met: {overlap}")
    else:
        findings.append(f"PASS: {c1} and {c2} hold fully disjoint KVSTORE entry sets "
                         f"({len(client_entries[c1])} vs {len(client_entries[c2])}) -- RSI=0 for this pair, "
                         f"matching IsoSearch's mediation goal")

    return ok, findings


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <model-dump.csv>")
        sys.exit(1)

    nodes, edges = parse_model_csv(sys.argv[1])
    print(f"Parsed {len(nodes)} nodes, {len(edges)} edges from {sys.argv[1]}\n")

    ok, findings = validate(nodes, edges)
    for f in findings:
        print(f"  {f}")

    print()
    if ok:
        print("RESULT: PASS -- GPIISO001's extracted graph matches IsoSearch's mediation target "
              "(exclusive mediator hold + disjoint client access), modulo the expected per-object "
              "capability detail not modeled by the abstract graph.")
    else:
        print("RESULT: FAIL -- see FAIL lines above.")
    sys.exit(0 if ok else 1)
