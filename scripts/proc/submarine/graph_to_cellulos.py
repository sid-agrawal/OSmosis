"""
Generalized graph -> CellulOS translator.

Generalizes the GPIISO001 proof of concept (workstream 6, THESIS_STATUS.md):
instead of hand-translating one specific IsoSearch graph into a bespoke CellulOS
test, this walks an arbitrary IsoSearch ModelGraph matching the "mediation
pattern" shape -- N client PDs, each with a REQUEST edge to exactly one mediator
PD, each mediator holding some FILE resources -- and emits the corresponding
CellulOS test function automatically, reusing the same building blocks GPIISO001
did (start_kvstore_server / start_hello_kvstore).

Scope (see THESIS_STATUS.md workstream 6 for the honest limits): this covers the
FILE+REQUEST mediation shape only. CPU pinning and cache-set goals have no
translation path at all (pd_config_t has no CPU-affinity field); those scenarios
are out of scope for this generator, same as they were for the hand-translated
PoC.

Usage:
    python3 graph_to_cellulos.py <scenario_name> [--test-id GPIISO002] [--out FILE]

Given a scenario name, runs beam search, takes the first complete solution
matching the mediation-pattern shape (clients have only a REQUEST edge, no
direct HOLD), and emits a C test function + DEFINE_TEST_OSM line.
"""
import sys
import argparse

sys.path.insert(0, '/home/siagraw/OSmosis-isosearch/scripts/proc/submarine')
import builtins
_real_print = builtins.print
builtins.print = lambda *a, **k: None
import isosearch
import scenarios as sc
builtins.print = _real_print


def classify_topology(graph):
    """Identify mediator PDs (hold FILE resources) and client PDs (REQUEST a
    mediator, hold nothing directly). Returns (mediators: set, client_to_mediator:
    dict) or raises ValueError if the graph doesn't match the mediation-pattern
    shape this generator supports."""
    g = graph.g
    pd_nodes = {n for n, d in g.nodes(data=True) if d.get('type') == 'PD'}

    hold_targets = {}  # pd -> set of directly-held resource node ids
    request_targets = {}  # pd -> requested PD
    for u, v, d in g.edges(data=True):
        if u not in pd_nodes:
            continue
        etype = d.get('type')
        if etype == 'HOLD':
            hold_targets.setdefault(u, set()).add(v)
        elif etype == 'REQUEST':
            if u in request_targets:
                raise ValueError(f"{u} has more than one REQUEST edge -- "
                                 f"generator only supports single-mediator clients")
            request_targets[u] = v

    clients = set(request_targets.keys())
    mediators = {v for v in request_targets.values()}

    # Every client must hold nothing directly (pure mediation, no per-object
    # capability leakage modeled at this level -- see the GPIISO001 PoC's
    # per-object-capability nuance, which this generator does not attempt to
    # reproduce structurally, only the mediation topology itself).
    for c in clients:
        if hold_targets.get(c):
            raise ValueError(f"client {c} directly holds resources {hold_targets[c]} -- "
                             f"generator only supports pure-mediation clients (no direct hold)")

    # Every mediator must hold at least one FILE resource.
    for m in mediators:
        if not hold_targets.get(m):
            raise ValueError(f"mediator {m} holds nothing -- not a valid mediator")

    return mediators, request_targets


def generate_test_c(scenario_name, mediators, client_to_mediator, test_id, func_name):
    """Emit a CellulOS test function realizing the given mediation topology,
    following the exact pattern established by GPIISO001 (kvstore.c)."""
    mediators = sorted(mediators, key=lambda n: int(n.split('_')[1]))
    clients = sorted(client_to_mediator.keys(), key=lambda n: int(n.split('_')[1]))
    mediator_idx = {m: i + 1 for i, m in enumerate(mediators)}

    lines = []
    lines.append(f"int {func_name}(env_t env)")
    lines.append("{")
    lines.append("    int error;")
    lines.append("")
    lines.append(f'    printf("------------------STARTING TEST: %s------------------\\n", __func__);')
    lines.append("")
    lines.append("    error = setup(env);")
    lines.append("    test_assert(error == 0);")
    lines.append("")
    lines.append("    /* IsoSearch design-space sweep: see GPIKV001 for the measurement convention. */")
    lines.append("    ccnt_t sweep_start, sweep_end;")
    lines.append("    sel4bench_init();")
    lines.append("    SEL4BENCH_READ_CCNT(sweep_start);")
    lines.append("")

    lines.append(f"    /* Generated from IsoSearch scenario '{scenario_name}': "
                 f"{len(mediators)} mediator(s), {len(clients)} client(s). */")
    for m in mediators:
        i = mediator_idx[m]
        lines.append(f"    /* Mediator {m} */")
        lines.append(f"    seL4_CPtr kvstore_ep_{i};")
        lines.append(f"    pd_client_context_t kvstore_pd_{i};")
        lines.append(f"    error = start_kvstore_server(&kvstore_ep_{i}, BADGE_SPACE_ID_NULL, &kvstore_pd_{i});")
        lines.append("    test_assert(error == 0);")
        lines.append("")

    for j, c in enumerate(clients, 1):
        m = client_to_mediator[c]
        i = mediator_idx[m]
        lines.append(f"    /* Client {c} -> mediator {m} */")
        lines.append(f"    pd_client_context_t hello_pd_{j};")
        lines.append(f"    error = start_hello_kvstore(SEPARATE_PROC, self_ep, kvstore_ep_{i}, &hello_pd_{j}, BADGE_SPACE_ID_NULL);")
        lines.append("    test_assert(error == 0);")
        lines.append("")

    lines.append("    test_error_eq(remove_RDEs(), 0);")
    lines.append("")
    lines.append(f"    /* Wait for all {len(clients)} client(s)' test results */")
    lines.append("    seL4_MessageInfo_t tag = seL4_MessageInfo_new(0, 0, 0, 0);")
    for j in range(1, len(clients) + 1):
        lines.append("    tag = seL4_Recv(self_ep.raw_endpoint, NULL);")
        lines.append("    error = seL4_MessageInfo_get_label(tag);")
        lines.append("    test_assert(error == 0);")
        lines.append("")

    lines.append("    SEL4BENCH_READ_CCNT(sweep_end);")
    lines.append('    printf("RESULT>%lu\\n", (unsigned long)(sweep_end - sweep_start));')
    lines.append("")
    lines.append("    extract_model(&pd_conn);")
    lines.append("")
    lines.append("    /* Cleanup PDs */")
    for j in range(1, len(clients) + 1):
        lines.append(f"    test_error_eq(maybe_terminate_pd(&hello_pd_{j}), 0);")
    for i in range(1, len(mediators) + 1):
        lines.append(f"    test_error_eq(maybe_terminate_pd(&kvstore_pd_{i}), 0);")
    lines.append("    test_error_eq(maybe_terminate_pd(&fs_pd), 0);")
    lines.append("    test_error_eq(maybe_terminate_pd(&ramdisk_pd), 0);")
    lines.append("")
    lines.append(f'    printf("------------------ENDING: %s------------------\\n", __func__);')
    lines.append("    return sel4test_get_result();")
    lines.append("}")
    lines.append(f'DEFINE_TEST_OSM({test_id}, "Auto-generated from IsoSearch scenario {scenario_name}: '
                 f'{len(clients)} client(s), {len(mediators)} mediator(s)", {func_name}, true)')
    return "\n".join(lines)


def translate_scenario(scenario_name, beam_width=12, max_depth=12):
    """Run beam search, pick the first complete solution matching the
    mediation-pattern shape, and return (mediators, client_to_mediator)."""
    scenario = sc.SCENARIOS[scenario_name]
    result = isosearch.BeamSearchExploration(scenario, beam_width=beam_width, max_depth=max_depth)
    sols = [m for m in result if m.get('is_complete_solution')]
    if not sols:
        raise RuntimeError(f"no complete solutions found for '{scenario_name}'")

    for m in sols:
        try:
            mediators, client_to_mediator = classify_topology(m['graph'])
            return mediators, client_to_mediator, m['iteration']
        except ValueError:
            continue
    raise RuntimeError(f"no solution among {len(sols)} found matches the "
                       f"mediation-pattern shape this generator supports")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_name")
    parser.add_argument("--test-id", default="GPIISO002")
    parser.add_argument("--func-name", default=None)
    parser.add_argument("--beam-width", type=int, default=12)
    parser.add_argument("--max-depth", type=int, default=12)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    func_name = args.func_name or f"test_{args.scenario_name}_generated"

    mediators, client_to_mediator, iteration = translate_scenario(
        args.scenario_name, args.beam_width, args.max_depth)
    _real_print(f"Selected solution at iteration {iteration}: "
               f"{len(mediators)} mediator(s), {len(client_to_mediator)} client(s)")
    for c, m in sorted(client_to_mediator.items()):
        _real_print(f"  {c} -> {m}")

    code = generate_test_c(args.scenario_name, mediators, client_to_mediator,
                           args.test_id, func_name)
    if args.out:
        with open(args.out, "w") as f:
            f.write(code + "\n")
        _real_print(f"\nWritten to {args.out}")
    else:
        _real_print("\n" + code)
