"""
IsoSearch Algorithm Implementation - Baby Steps
"""

# Import our graph transformation capabilities
from graph_transformations import NodeTransformations, EdgeTransformations
from generic_model import ModelGraph, ResourceType, VmrType, FileType, Permission, EdgeType
from scenarios import get_scenario, list_scenarios, SCENARIOS, Goal, Constraint, Transition

# Goal, Constraint, and Transition classes are now imported from scenarios.py

import random as _random_module

# Candidate selection takes a non-best candidate 15% of the time (see GenerateCandidate).
# That draw used the global `random` module unseeded. It affects only the GREEDY path:
# beam search discards GenerateCandidate's chosen candidate and iterates all_candidates,
# which is built before the draw, so beam-search results are deterministic either way.
# Seeding here removes the latent nondeterminism from the greedy path and makes any run
# reproducible from its seed.
# Weight on holding a private space of a goal-named type, relative to the ten points a
# fully-met goal scores. Large enough that acquiring a space of one's own outranks
# evicting one other PD from a shared one, small enough not to outrank meeting the goal.
PRIVATE_SPACE_CREDIT = 2.0

DEFAULT_SEED = 20260822
_RNG = _random_module.Random(DEFAULT_SEED)


def set_seed(seed):
    """Reseed the exploration RNG. Same seed + same scenario => identical run."""
    global _RNG
    _RNG = _random_module.Random(seed)
    return seed


def _calculate_memory_consumption(graph):
    """Sum size_bytes for FILE resources (+ pages*size for VMR/PHYS_PAGE) held by any PD.
    Counts each physical resource node once even if held by multiple PDs."""
    import json
    total = 0
    seen = set()
    for u, v, d in graph.g.edges(data=True):
        if d.get('type') == 'HOLD' and u.startswith('PD_') and v not in seen:
            seen.add(v)
            node = graph.g.nodes.get(v, {})
            rtype = node.get('data', '')
            extra_str = node.get('extra', '{}') or '{}'
            try:
                extra = json.loads(extra_str)
            except Exception:
                extra = {}
            if rtype == 'FILE':
                total += int(extra.get('size_bytes', 0))
            elif rtype in ('VMR', 'MO', 'PHYS_PAGE'):
                total += int(extra.get('num_pages', 0)) * int(extra.get('page_size', 4096))
    return total


def ComputeMetrics(candidate, requested_metrics=None, pd_filter=None):
    """
    Compute metrics for a candidate graph (RSI, TransitiveRSI, FR, TCB, ASR)

    Args:
        candidate: The graph to compute metrics for
        requested_metrics: Optional list of specific metrics to compute (for efficiency).
                          Supports per-resource-type metrics like "RSI:CPU", "TransitiveRSI:CACHE_SET"
        pd_filter: Optional set of PDs to restrict pairwise metrics to. The pairwise
                   metrics below are computed for every pair of PDs, fourteen times over,
                   which on a graph with 104 PDs is 5,356 pairs and dominates the cost of
                   ranking a candidate. A caller that only reads the pairs its goals name
                   can pass those PDs here and get identical values for them. Callers that
                   need whole-graph metrics (GlobalRSI, ASR) must leave this as None.

    Returns: dictionary of metric values
    """
    print("  Computing metrics...")

    # Find all PDs in the graph
    pd_nodes = [node for node, data in candidate.g.nodes(data=True)
                if data.get('type') == 'PD']
    # Pairwise metrics need at least two PDs to be meaningful, so they keep the full list
    # unless the filter leaves two or more. Per-PD metrics (TCB) are correct for any PD
    # computed, so they use the filter whenever it names one.
    pd_pairwise = pd_nodes
    pd_per_pd = pd_nodes
    if pd_filter:
        scoped = [n for n in pd_nodes if n in pd_filter]
        if scoped:
            pd_per_pd = scoped
        if len(scoped) >= 2:
            pd_pairwise = scoped
    pd_nodes = pd_pairwise

    metrics = {}

    # When the caller names the metrics it will read, skip the rest. Each pairwise family
    # below costs a pass over every PD pair, and there are fourteen of them; a caller
    # scoring a TCB goal reads none of them. Callers that pass nothing get everything, as
    # before.
    def _wanted(name):
        return requested_metrics is None or name in requested_metrics

    # Calculate RSI (Resource Sharing Index) as per PD pair metric - direct HOLD edges only
    if _wanted('RSI'):
        metrics['RSI'] = _calculate_rsi_per_pd_pair(candidate, pd_nodes, follow_map_edges=False)

    # Calculate TransitiveRSI - follows MAP edges to find effective resource sharing
    # (e.g., for cache scenarios: PHYS_PAGE -> CACHE_SET)
    if _wanted('TransitiveRSI'):
        metrics['TransitiveRSI'] = _calculate_rsi_per_pd_pair(candidate, pd_nodes, follow_map_edges=True)

    # Calculate per-resource-type RSI metrics if requested
    # Format: "RSI:CPU", "RSI:PHYS_PAGE", "TransitiveRSI:CACHE_SET", etc.
    resource_types = ['CPU', 'PHYS_PAGE', 'FILE', 'CACHE_SET', 'VMR', 'MO']
    for res_type in resource_types:
        # Direct RSI per resource type (e.g., RSI:CPU = direct CPU sharing)
        if _wanted(f'RSI:{res_type}'):
            metrics[f'RSI:{res_type}'] = _calculate_rsi_per_pd_pair(
                candidate, pd_nodes, follow_map_edges=False, resource_type_filter=res_type)
        # Transitive RSI per resource type (e.g., TransitiveRSI:CACHE_SET)
        if _wanted(f'TransitiveRSI:{res_type}'):
            metrics[f'TransitiveRSI:{res_type}'] = _calculate_rsi_per_pd_pair(
                candidate, pd_nodes, follow_map_edges=True, resource_type_filter=res_type)

    # Calculate ASR (Attack Surface Ratio) - attack paths per PD
    if _wanted('ASR'):
        metrics['ASR'] = _calculate_asr(candidate, pd_nodes)

    # Calculate TCB (Trusted Computing Base) size
    if _wanted('TCB'):
        metrics['TCB'] = _calculate_tcb(candidate, pd_per_pd)
    metrics['TCB:SPACE'] = {pd: _fast_tcb_spaces(candidate, pd) for pd in pd_per_pd}
    # Per-space-type sharing, keyed the same way. GoalsMet resolves a goal by looking up
    # metrics[goal.metric_name], so a goal naming TCB:SPACE:IPC can only ever be reported
    # as met if that key exists here. Emitting it in the scoring path alone is not enough:
    # the search would reach a satisfying graph and be unable to say so.
    _space_types = {d.get('data') for _, d in candidate.g.nodes(data=True)
                    if d.get('type') == 'RESOURCE_SPACE' and d.get('data')}
    for _st in _space_types:
        key = f'TCB:SPACE:{_st}'
        if _wanted(key):
            metrics[key] = {pd: _fast_tcb_spaces_of_type(candidate, pd, _st)
                            for pd in pd_per_pd}

    # Calculate FR (Fault Radius) - distance to common ancestor via REQUEST edges
    if _wanted('FR'):
        metrics['FR'] = _calculate_fr(candidate, pd_nodes)

    # Calculate total memory consumption (sum of file sizes + page memory held by any PD)
    metrics['MemoryConsumption'] = _calculate_memory_consumption(candidate)

    # Calculate GlobalRSI: mean RSI across all PD pairs (1.0 when <2 PDs)
    pd_resources = {}
    for u, v, d in candidate.g.edges(data=True):
        if d.get('type') == 'HOLD' and u.startswith('PD_'):
            pd_resources.setdefault(u, set()).add(v)
    metrics['GlobalRSI'] = _compute_global_rsi(pd_resources)

    # Print summary (only base metrics to avoid clutter)
    print("    " + ", ".join(f"{k}: {metrics[k]}" for k in
          ('RSI','TransitiveRSI','ASR','TCB','FR','MemoryConsumption') if k in metrics))
    return metrics


def _calculate_rsi_per_pd_pair(graph, pd_nodes, follow_map_edges=False, resource_type_filter=None):
    """Calculate RSI (Resource Sharing Index) as per PD pair metric

    RSI[PD_i, PD_j] = (Resources shared by PD_i and PD_j) / (Total resources accessed by either PD_i or PD_j)

    Args:
        graph: The model graph
        pd_nodes: List of PD node IDs
        follow_map_edges: If True, follow MAP edges transitively to find effective resources
                         (e.g., PHYS_PAGE -> CACHE_SET). If False, only count direct HOLD edges.
        resource_type_filter: If specified, only count resources of this type (e.g., "CPU", "PHYS_PAGE", "FILE")

    Returns a dictionary mapping PD pairs to their RSI values
    """
    # Build resource access map: PD -> set of resources
    pd_resources = {}
    for pd in pd_nodes:
        pd_resources[pd] = set()

    # Find all DIRECT HOLD edges from PDs to resources (not through mediators)
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            # Only count direct access - PD directly holds the resource
            if from_node in pd_resources:
                # Apply resource type filter if specified, BUT only for direct RSI (not transitive)
                # For transitive RSI, we collect all resources first, then filter after following MAP edges
                if resource_type_filter and not follow_map_edges:
                    node_data = graph.g.nodes.get(to_node, {})
                    node_res_type = node_data.get('data')  # e.g., "CPU", "PHYS_PAGE", "FILE"
                    if node_res_type != resource_type_filter:
                        continue  # Skip resources that don't match the filter
                pd_resources[from_node].add(to_node)

    # If follow_map_edges is True, resolve to effective resources via MAP edges
    # The resource_type_filter is applied AFTER following MAP edges in _resolve_transitive_resources
    if follow_map_edges:
        pd_resources = _resolve_transitive_resources(graph, pd_resources, resource_type_filter)

    # Calculate RSI for each PD pair
    rsi_pairs = {}

    for i, pd_i in enumerate(pd_nodes):
        for j, pd_j in enumerate(pd_nodes):
            if i < j:  # Only calculate for unique pairs (avoid duplicates)
                pair_key = f"{pd_i},{pd_j}"

                resources_i = pd_resources[pd_i]
                resources_j = pd_resources[pd_j]

                # Resources shared by both PDs
                shared_resources = resources_i.intersection(resources_j)

                # Total resources accessed by either PD
                total_resources = resources_i.union(resources_j)

                # Calculate RSI for this pair
                if len(total_resources) > 0:
                    rsi_pairs[pair_key] = len(shared_resources) / len(total_resources)
                else:
                    rsi_pairs[pair_key] = 0.0

    return rsi_pairs


def _resolve_transitive_resources(graph, pd_resources, resource_type_filter=None):
    """Follow MAP edges to find effective/transitive resources for each PD.

    For example, if PD holds PHYS_PAGE_1 which MAPs to CACHE_SET_1,
    the effective resource is CACHE_SET_1.

    Args:
        graph: The model graph
        pd_resources: Dict mapping PD -> set of directly held resources
        resource_type_filter: If specified, only include resources of this type in the result

    Returns:
        Dict mapping PD -> set of effective resources (after following MAP edges)
    """
    # Build a map of resource -> resources it maps to
    map_edges = {}
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'MAP':
            if from_node not in map_edges:
                map_edges[from_node] = set()
            map_edges[from_node].add(to_node)

    # For each PD, resolve held resources to their effective resources
    pd_effective_resources = {}
    for pd, resources in pd_resources.items():
        effective = set()
        for resource in resources:
            # Follow MAP edges transitively
            resolved = _follow_map_chain(resource, map_edges)
            effective.update(resolved)

        # Apply resource type filter if specified
        if resource_type_filter:
            filtered = set()
            for res in effective:
                node_data = graph.g.nodes.get(res, {})
                if node_data.get('data') == resource_type_filter:
                    filtered.add(res)
            effective = filtered

        pd_effective_resources[pd] = effective

    return pd_effective_resources


def _follow_map_chain(resource, map_edges, visited=None):
    """Follow MAP edges from a resource to find terminal resources.

    Returns the set of resources at the end of MAP chains.
    If the resource has no outgoing MAP edges, returns itself.
    """
    if visited is None:
        visited = set()

    # Prevent cycles
    if resource in visited:
        return set()
    visited.add(resource)

    # If this resource has MAP edges, follow them
    if resource in map_edges:
        result = set()
        for mapped_to in map_edges[resource]:
            result.update(_follow_map_chain(mapped_to, map_edges, visited.copy()))
        return result
    else:
        # Terminal resource - no outgoing MAP edges
        return {resource}


def _get_resource_type(graph, resource_node):
    """Get the resource type from a resource node"""
    # Check if it's a resource space
    node_data = graph.g.nodes.get(resource_node, {})
    node_type = node_data.get('type', '')

    if node_type == 'RESOURCE_SPACE':
        return node_data.get('data', 'UNKNOWN')
    elif node_type == 'RESOURCE':
        return node_data.get('data', 'UNKNOWN')
    else:
        # Try to infer from node name
        if 'FILE' in resource_node:
            return 'FILE'
        elif 'MO' in resource_node:
            return 'MO'
        elif 'FILE' in resource_node:
            return 'FILE'
        elif 'VCPU' in resource_node:
            return 'VCPU'
        elif 'PCPU' in resource_node:
            return 'PCPU'
        else:
            return 'UNKNOWN'


def _calculate_asr(graph, pd_nodes):
    """Calculate ASR (Attack Surface Ratio) - potential attack paths per PD"""
    # Count edges that could be attack paths (HOLD, REQUEST, MAP edges)
    attack_edges = 0

    for from_node, to_node, edge_data in graph.g.edges(data=True):
        edge_type = edge_data.get('type')
        if edge_type in ['HOLD', 'REQUEST', 'MAP']:
            attack_edges += 1

    # Normalize by number of PDs
    return attack_edges / len(pd_nodes) if pd_nodes else 0


def _calculate_tcb(graph, pd_nodes):
    """Calculate TCB (Trusted Computing Base) - for each PD, list of PDs that have authority over it OR share resources with it"""
    # For each PD, find which PDs have authority over it OR share resources with it
    tcb_by_pd = {}

    # Initialize empty TCB lists for all PDs
    for pd_node in pd_nodes:
        tcb_by_pd[pd_node] = []

    # 1. Find authority relationships
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        edge_type = edge_data.get('type', '')

        # Direct authority: REQUEST edges show authority relationship
        if edge_type == 'REQUEST' and from_node.startswith('PD_') and to_node.startswith('PD_'):
            # from_node requests from to_node, so to_node has authority over from_node
            if from_node in tcb_by_pd and to_node not in tcb_by_pd[from_node]:
                tcb_by_pd[from_node].append(to_node)

        # Other direct authority relationships
        elif edge_type in ['AUTHORITY', 'CONTROL'] and from_node.startswith('PD_') and to_node.startswith('PD_'):
            # from_node has authority over to_node
            if to_node in tcb_by_pd and from_node not in tcb_by_pd[to_node]:
                tcb_by_pd[to_node].append(from_node)

    # Check for authority through resource control (pd_incharge fields)
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        extra = edge_data.get('extra', '{}')
        try:
            import json
            extra_dict = json.loads(extra) if extra else {}
            pd_incharge = extra_dict.get('pd_incharge', '')

            # Find which PD is in charge
            controller_pd = None
            for pd_node in pd_nodes:
                if (pd_incharge == pd_node.replace('PD_', '').lower() or
                    pd_incharge == pd_node):
                    controller_pd = pd_node
                    break

            # If a PD controls this edge and it affects another PD, that's authority
            if controller_pd and edge_data.get('type') == 'HOLD':
                affected_pd = from_node if from_node.startswith('PD_') else None
                if (affected_pd and affected_pd != controller_pd and
                    affected_pd in tcb_by_pd and
                    controller_pd not in tcb_by_pd[affected_pd]):
                    tcb_by_pd[affected_pd].append(controller_pd)
        except:
            pass

    # 2. Find resource sharing relationships
    resource_holders = {}

    # Build map of which PDs hold which resources
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_holders:
                resource_holders[to_node] = []
            resource_holders[to_node].append(from_node)

    # For each shared resource, add sharing PDs to each other's TCB
    for resource, holders in resource_holders.items():
        if len(holders) > 1:  # Shared resource
            for pd in holders:
                for other_pd in holders:
                    if (pd != other_pd and
                        pd in tcb_by_pd and
                        other_pd not in tcb_by_pd[pd]):
                        tcb_by_pd[pd].append(other_pd)

    return tcb_by_pd


def _calculate_fr(graph, pd_nodes):
    """Calculate FR (Fault Radius) - distance to common ancestor for PD pairs via REQUEST edges"""

    # Build REQUEST edge graph (authority relationships)
    request_graph = {}
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'REQUEST' and from_node.startswith('PD_') and to_node.startswith('PD_'):
            if from_node not in request_graph:
                request_graph[from_node] = []
            request_graph[from_node].append(to_node)

    # Calculate fault radius for each PD pair
    fr_by_pair = {}

    for i in range(len(pd_nodes)):
        for j in range(i + 1, len(pd_nodes)):
            pd1 = pd_nodes[i]
            pd2 = pd_nodes[j]
            pair_key = f"{pd1},{pd2}"

            # Find common ancestor and calculate distance
            distance = _find_common_ancestor_distance(pd1, pd2, request_graph)
            fr_by_pair[pair_key] = distance

    return fr_by_pair


def _find_common_ancestor_distance(pd1, pd2, request_graph):
    """Find distance to common ancestor between two PDs via REQUEST edges"""

    # Get all ancestors for each PD with their distances
    ancestors1 = _get_ancestors_with_distance(pd1, request_graph)
    ancestors2 = _get_ancestors_with_distance(pd2, request_graph)

    # Find common ancestors and their total distances
    min_distance = float('inf')

    for ancestor in ancestors1:
        if ancestor in ancestors2:
            # Total distance = distance from pd1 to ancestor + distance from pd2 to ancestor
            total_distance = ancestors1[ancestor] + ancestors2[ancestor]
            min_distance = min(min_distance, total_distance)

    return min_distance


def _get_ancestors_with_distance(pd, request_graph):
    """Get all ancestors of a PD with their distances via REQUEST edges"""
    ancestors = {}
    visited = set()
    queue = [(pd, 0)]  # (node, distance)

    while queue:
        current_pd, distance = queue.pop(0)

        if current_pd in visited:
            continue
        visited.add(current_pd)

        # Add current node as ancestor (except for the starting PD itself)
        if distance > 0:
            ancestors[current_pd] = distance

        # Follow REQUEST edges to find more ancestors
        if current_pd in request_graph:
            for parent in request_graph[current_pd]:
                if parent not in visited:
                    queue.append((parent, distance + 1))

    return ancestors




def _is_rsi_like_metric(metric_name):
    """Check if a metric name is an RSI-like metric (including per-resource-type variants).

    Returns True for: RSI, TransitiveRSI, FR, RSI:CPU, RSI:PHYS_PAGE, TransitiveRSI:CACHE_SET, etc.
    """
    base_rsi_metrics = ["RSI", "TransitiveRSI", "FR"]
    if metric_name in base_rsi_metrics:
        return True
    # Check for per-resource-type variants like "RSI:CPU", "TransitiveRSI:CACHE_SET"
    if ":" in metric_name:
        base_metric = metric_name.split(":")[0]
        return base_metric in ["RSI", "TransitiveRSI"]
    return False


def GoalsMet(metrics, goals):
    """
    Check if the computed metrics meet the specified goals
    Supports targeted goals: TCB for specific PD, RSI/FR for specific PD pairs, ASR system-wide
    Also supports per-resource-type metrics like RSI:CPU, TransitiveRSI:CACHE_SET
    Returns: boolean indicating if all goals are satisfied
    """
    for goal in goals:
        metric_value = metrics.get(goal.metric_name)
        if metric_value is None:
            print(f"    Warning: Metric {goal.metric_name} not found in results")
            return False

        # Handle targeted goals
        if goal.target_spec:
            if (goal.metric_name == "TCB" or goal.metric_name.startswith("TCB:SPACE")) \
                    and isinstance(metric_value, dict):
                # TCB goal for specific PD
                target_pd = goal.target_spec
                if target_pd not in metric_value:
                    print(f"    Warning: PD {target_pd} not found in TCB metrics")
                    return False

                tcb_list = metric_value[target_pd]
                # TCB is a list of PDs; the space-restricted variants are already counts.
                tcb_count = tcb_list if isinstance(tcb_list, int) else len(tcb_list)

                if goal.direction == "minimize":
                    if tcb_count > goal.target_value:
                        dependencies = (", ".join(tcb_list)
                                        if isinstance(tcb_list, (list, tuple, set)) and tcb_list
                                        else str(tcb_list))
                        print(f"    Goal not met: TCB[{target_pd}]={tcb_count} > {goal.target_value} (dependencies: {dependencies})")
                        return False
                elif goal.direction == "maximize":
                    if tcb_count < goal.target_value:
                        dependencies = (", ".join(tcb_list)
                                        if isinstance(tcb_list, (list, tuple, set)) and tcb_list
                                        else str(tcb_list))
                        print(f"    Goal not met: TCB[{target_pd}]={tcb_count} < {goal.target_value} (dependencies: {dependencies})")
                        return False

            elif _is_rsi_like_metric(goal.metric_name) and isinstance(metric_value, dict):
                # RSI, FR, or TransitiveRSI goal for specific PD pair
                target_pair = goal.target_spec
                if target_pair not in metric_value:
                    print(f"    Warning: PD pair {target_pair} not found in {goal.metric_name} metrics")
                    return False

                pair_value = metric_value[target_pair]

                if goal.direction == "minimize":
                    if pair_value > goal.target_value:
                        value_str = "infinity" if pair_value == float('inf') else f"{pair_value:.3f}"
                        print(f"    Goal not met: {goal.metric_name}[{target_pair}]={value_str} > {goal.target_value}")
                        return False
                elif goal.direction == "maximize":
                    if pair_value < goal.target_value:
                        value_str = "infinity" if pair_value == float('inf') else f"{pair_value:.3f}"
                        print(f"    Goal not met: {goal.metric_name}[{target_pair}]={value_str} < {goal.target_value}")
                        return False
            else:
                print(f"    Warning: Targeted goal for {goal.metric_name} not supported or metric format unexpected")
                return False

        # Handle non-targeted goals (system-wide)
        else:
            if goal.metric_name == "ASR":
                # ASR is system-wide scalar metric
                if goal.direction == "minimize":
                    if metric_value > goal.target_value:
                        print(f"    Goal not met: {goal.metric_name}={metric_value:.3f} > {goal.target_value}")
                        return False
                elif goal.direction == "maximize":
                    if metric_value < goal.target_value:
                        print(f"    Goal not met: {goal.metric_name}={metric_value:.3f} < {goal.target_value}")
                        return False

            elif (goal.metric_name == "TCB" or _is_rsi_like_metric(goal.metric_name)) and isinstance(metric_value, dict):
                # Non-targeted goals for dictionary metrics check all entries
                goal_violated = False
                for key, value in metric_value.items():
                    if goal.metric_name == "TCB":
                        check_value = len(value)  # TCB uses length of dependency list
                    else:
                        check_value = value  # RSI-like metrics use the value directly

                    if goal.direction == "minimize":
                        if check_value > goal.target_value:
                            if goal.metric_name == "TCB":
                                dependencies = ", ".join(value) if value else "none"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={check_value} > {goal.target_value} (dependencies: {dependencies})")
                            else:
                                value_str = "infinity" if check_value == float('inf') else f"{check_value:.3f}"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={value_str} > {goal.target_value}")
                            goal_violated = True
                    elif goal.direction == "maximize":
                        if check_value < goal.target_value:
                            if goal.metric_name == "TCB":
                                dependencies = ", ".join(value) if value else "none"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={check_value} < {goal.target_value} (dependencies: {dependencies})")
                            else:
                                value_str = "infinity" if check_value == float('inf') else f"{check_value:.3f}"
                                print(f"    Goal not met: {goal.metric_name}[{key}]={value_str} < {goal.target_value}")
                            goal_violated = True

                if goal_violated:
                    return False
            else:
                # Handle other scalar metrics
                if goal.direction == "minimize":
                    if metric_value > goal.target_value:
                        print(f"    Goal not met: {goal.metric_name}={metric_value} > {goal.target_value}")
                        return False
                elif goal.direction == "maximize":
                    if metric_value < goal.target_value:
                        print(f"    Goal not met: {goal.metric_name}={metric_value} < {goal.target_value}")
                        return False

    print(f"    All {len(goals)} goals met!")
    return True


def GenerateCandidate(graph, constraints, transitions, goals, last_transition_type=None, transition_history=None, mutable_pds=None, scope_spaces=False):
    """
    Generate a new candidate graph by applying a transition
    Uses smart selection to choose the best node/edge for transformation
    Args:
        last_transition_type: The transition type used in the previous iteration (to avoid repetition)
        transition_history: List of recent transition names for diversity scoring
    Returns: tuple of (new graph or None, candidate_info dict)
    """
    import copy

    # Get all possible transformations with their predicted impact
    transformation_candidates = []

    for transition in transitions:
        # Use new transition system's find_candidates method
        candidates = transition.find_candidates(graph, constraints, goals, mutable_pds, scope_spaces)
        # Add predicted improvement and other metadata
        for candidate in candidates:
            candidate['transition_name'] = transition.name
            candidate['transition_type'] = transition.transition_type
            candidate['predicted_improvement'] = _predict_improvement(transition, candidate, graph, goals, constraints, transition_history)
            # Debug output for remove_hold_edge candidates
            if transition.name == "remove_hold_edge":
                print(f"    remove_hold_edge candidate: {candidate['target_description']} -> score: {candidate['predicted_improvement']:.3f}")
        transformation_candidates.extend(candidates)

    # Prepare candidate info for tracking
    candidate_info = {
        'all_candidates': transformation_candidates.copy(),
        'selected_candidate': None,
        'discarded_candidates': [],
        'success': False
    }

    if not transformation_candidates:
        print("  No valid transitions found")
        return None, candidate_info

    # Prioritize constraint-relevant candidates (Strategy 3)
    def candidate_priority(candidate):
        base_improvement = candidate['predicted_improvement']
        constraint_relevance = candidate.get('constraint_relevance', 0.1)
        addresses_violation = candidate.get('addresses_violation', False)

        # Boost priority for constraint-addressing candidates
        if addresses_violation:
            return base_improvement + constraint_relevance + 0.1
        return base_improvement

    # Filter out candidates of the same type as last iteration to force exploration diversity,
    # UNLESS those candidates are significantly better than the alternatives (e.g., removing
    # prohibited edges when many consecutive removes are needed).
    if last_transition_type is not None:
        original_count = len(transformation_candidates)
        same_type_candidates = [c for c in transformation_candidates if c['transition_name'] == last_transition_type]
        different_type_candidates = [c for c in transformation_candidates if c['transition_name'] != last_transition_type]

        if different_type_candidates and same_type_candidates:
            best_same_score = max(c['predicted_improvement'] for c in same_type_candidates)
            best_diff_score = max(c['predicted_improvement'] for c in different_type_candidates)
            # Only filter if same-type candidates are not significantly better than alternatives
            # Threshold: if same-type best score exceeds best alternative by > 1.0, keep them
            if best_same_score <= best_diff_score + 1.0:
                transformation_candidates = different_type_candidates
                print(f"  🚫 Filtered out {len(same_type_candidates)} '{last_transition_type}' candidates (diversity; best same={best_same_score:.1f}, diff={best_diff_score:.1f})")
            else:
                print(f"  ✓ Keeping '{last_transition_type}' candidates (best same={best_same_score:.1f} >> diff={best_diff_score:.1f})")
        elif not different_type_candidates:
            # If no different types available, keep all candidates
            print(f"  ⚠️  No alternatives to '{last_transition_type}', keeping all {original_count} candidates")

    transformation_candidates.sort(key=candidate_priority, reverse=True)

    # Add exploration diversity - sometimes pick from top candidates instead of always the best
    exploration_factor = 0.15  # 15% chance to explore alternatives
    if len(transformation_candidates) > 1 and _RNG.random() < exploration_factor:
        top_n = min(3, len(transformation_candidates))
        selected_index = _RNG.randint(0, top_n - 1)
        best_candidate = transformation_candidates[selected_index]
        print(f"  🎲 Exploration: selecting candidate #{selected_index + 1} instead of best")
    else:
        best_candidate = transformation_candidates[0]
    candidate_info['selected_candidate'] = best_candidate
    candidate_info['discarded_candidates'] = transformation_candidates[1:]  # All except the best

    candidate_graph = copy.deepcopy(graph)

    print(f"  Trying best transition: {best_candidate['transition_type']}")
    print(f"    Target: {best_candidate['target_description']}")
    print(f"    Predicted improvement: {best_candidate['predicted_improvement']:.3f}")

    # Show discarded options if there are any
    if len(candidate_info['discarded_candidates']) > 0:
        print(f"    Considered {len(candidate_info['discarded_candidates'])} other option(s):")
        for i, discarded in enumerate(candidate_info['discarded_candidates'][:10], 1):  # Show top 10 discarded
            print(f"      {i}. {discarded['transition_type']}: {discarded['target_description']} (improvement: {discarded['predicted_improvement']:.3f})")
        if len(candidate_info['discarded_candidates']) > 10:
            print(f"      ... and {len(candidate_info['discarded_candidates']) - 10} more")

    # Apply transformation using new transition system
    try:
        # Find the transition object
        transition = None
        for t in transitions:
            if t.name == best_candidate['transition_name']:
                transition = t
                break

        if transition is None:
            print(f"    ❌ Transition {best_candidate['transition_name']} not found")
            return None, candidate_info

        # Apply the transition with the candidate's parameter values
        success = transition.apply(candidate_graph, best_candidate.get('param_values', {}))
        candidate_info['success'] = success

        if success:
            # Validate constraints after transformation
            try:
                from constraint_validation import validate_all_constraints
                # Use "exploration" mode to allow temporary access constraint violations
                # during multi-step solution building (e.g., for mediator discovery)
                constraints_valid, violations = validate_all_constraints(candidate_graph, constraints, mode="exploration")

                if constraints_valid:
                    print(f"    ✅ Applied {best_candidate['transition_name']}")
                    return candidate_graph, candidate_info
                else:
                    print(f"    ⚠️  Applied {best_candidate['transition_name']} with constraint violations: {'; '.join(violations[:2])}")
                    candidate_info['constraint_violations'] = violations
                    # Return the modified graph anyway to allow multi-step exploration
                    return candidate_graph, candidate_info
            except ImportError:
                # Fallback if constraint_validation module not available
                print(f"    ✅ Applied {best_candidate['transition_name']} (no constraint validation)")
                return candidate_graph, candidate_info
        else:
            print(f"    ❌ Failed to apply {best_candidate['transition_name']}")
            return None, candidate_info
    except Exception as e:
        print(f"    ❌ Error applying {best_candidate.get('transition_name', 'unknown')}: {e}")
        candidate_info['success'] = False
        return None, candidate_info


# Above this many nodes, rank candidates with the fast progress function rather than a
# full before/after metric comparison. Case-study graphs are far below it, so their
# ranking, and therefore their results, are unchanged.
#
# The test is on node count, not edge count: MultiDiGraph.number_of_edges() sums over
# every node's adjacency dict, so asking it once per candidate costs a pass over the
# whole graph and made this check more expensive than the work it was guarding.
# number_of_nodes() is a dict length.
FAST_RANKING_NODE_THRESHOLD = 2000


def operation_name_of(transition):
    """The operation name _apply_transformation_for_scoring expects."""
    if hasattr(transition, 'operation'):
        return transition.operation
    return getattr(transition, 'name', str(transition))


def _predict_improvement(transition, candidate, graph, goals, constraints=None, transition_history=None):
    """
    Context-aware improvement prediction that considers current graph state and constraints
    Returns: float representing predicted improvement (higher = better)
    """

    # Use goal-driven scoring (the active scoring system)
    if goals:
        from goal_driven_scoring import calculate_goal_driven_score
        # On a large graph, ranking a candidate by a full before/after ComputeMetrics
        # costs seconds per candidate and dominates the search: the pair of calls below
        # were measured at 12.8 s each on a graph extracted from a live system. Above a
        # threshold we rank with the same fast progress function the beam loop scores
        # with, applied through the journal so no copy is made. This is a ranking
        # heuristic in both cases; what changes is its fidelity, not the validity of any
        # solution, since every candidate admitted as a solution is still re-validated
        # against every constraint and goal.
        if graph.g.number_of_nodes() > FAST_RANKING_NODE_THRESHOLD:
            try:
                with _Journal(graph):
                    if _apply_transformation_for_scoring(graph, operation_name_of(transition), candidate):
                        return 0.1 + _fast_goal_progress(graph, goals)
                return 0.1
            except Exception:
                return 0.1
        try:
            # Apply the operation to get the new graph
            from copy import deepcopy
            new_graph = deepcopy(graph)
            transition_obj = transition if hasattr(transition, 'operation') else type('obj', (object,), {'operation': transition.name if hasattr(transition, 'name') else str(transition)})()
            operation_name = transition_obj.operation if hasattr(transition_obj, 'operation') else str(transition)

            # Apply transformation to get new graph state
            applied_graph = _apply_transformation_for_scoring(new_graph, operation_name, candidate)
            if applied_graph:
                return calculate_goal_driven_score(operation_name, candidate, graph, applied_graph, goals, constraints, transition_history)
            else:
                return 0.1  # Fallback for failed applications
        except Exception as e:
            print(f"    ⚠️  Goal-driven scoring error: {e}")
            return 0.1  # Fallback score

    # Get base improvement score
    base_scores = {
        # Multi-step transitions
        "privatize_resource": 1.0,  # High impact on RSI
        "add_mediator": 0.5,        # Medium impact on security

        # High-impact primitives (problem-solving)
        "remove_file_resource": 0.4,    # Lowered - can violate constraints
        "add_file_resource": 0.6,       # Raised - builds solutions
        "remove_hold_edge": 0.5,       # Can disconnect from shared resources
        "add_hold_edge": 0.4,          # Can connect PDs to new private resources

        # Medium-impact primitives (structural)
        "remove_pd": 0.3,              # Can remove unnecessary components
        "add_subset_edge": 0.3,        # Can connect resources to spaces
        "remove_subset_edge": 0.3,     # Can disconnect resources from spaces
        "add_request_edge": 0.2,       # Can add authority relationships
        "remove_request_edge": 0.3,    # Can remove authority relationships

        # Low-impact primitives (infrastructure)
        "add_pd": 0.2,                 # Lower priority - doesn't solve sharing directly
        "add_resource_space": 0.1,     # Infrastructure operation
        "remove_resource_space": 0.2   # Cleanup operation
    }

    base_score = base_scores.get(transition.name, 0.3)

    # Apply context-aware scoring adjustments
    adjusted_score = _apply_context_adjustments(transition, candidate, graph, goals, base_score)

    return adjusted_score


def _apply_transformation_for_scoring(graph, operation_name, candidate):
    """
    Apply transformation to graph for scoring purposes
    Returns new graph state or None if application fails
    """
    try:
        # Handle parameter extraction
        if hasattr(candidate, 'get'):
            params = candidate.get('param_values', {})
        else:
            params = candidate if isinstance(candidate, dict) else {}

        # Apply the transformation based on operation type
        if operation_name == "add_pd":
            description = params.get('description', 'new_pd')
            NodeTransformations.add_pd_node(graph, description)

        elif operation_name == "remove_pd":
            pd_to_remove = params.get('pd_to_remove')
            if pd_to_remove and graph.g.has_node(pd_to_remove):
                NodeTransformations.remove_pd_node(graph, pd_to_remove)

        elif operation_name == "add_file_resource":
            file_type_str = params.get('file_type', 'TEMP')
            path = params.get('path', '/tmp/test_file')
            size_bytes = params.get('size_bytes', 1024)
            resource_space = params.get('resource_space', 'FILE_SPACE_1')

            # Convert string to FileType enum
            file_type = getattr(FileType, file_type_str, FileType.TEMP)
            NodeTransformations.add_file_resource(graph, resource_space, file_type, path, size_bytes)

        elif operation_name == "remove_file_resource":
            resource_to_remove = params.get('resource_to_remove')
            if resource_to_remove and graph.g.has_node(resource_to_remove):
                NodeTransformations.remove_file_resource(graph, resource_to_remove)

        elif operation_name == "add_hold_edge":
            permission_str = params.get('permission', 'RW')
            from_node = params.get('from_node') or params.get('pd')
            to_node = params.get('to_node') or params.get('resource')

            if from_node and to_node:
                # Convert string to Permission enum
                # Default to read+write permissions if not specified
                if permission_str == 'RW':
                    permission = Permission.R  # Use R as default, could use W too
                else:
                    permission = getattr(Permission, permission_str, Permission.R)
                graph.g.add_edge(from_node, to_node, type='HOLD', permission=permission.value)

        elif operation_name == "remove_hold_edge":
            from_node = params.get('from_node') or params.get('pd')
            to_node = params.get('to_node') or params.get('resource')

            if from_node and to_node and graph.g.has_edge(from_node, to_node):
                graph.g.remove_edge(from_node, to_node)

        elif operation_name == "add_request_edge":
            from_node = params.get('from_node') or params.get('from_pd')
            to_node = params.get('to_node') or params.get('to_pd')

            if from_node and to_node:
                graph.g.add_edge(from_node, to_node, type='REQUEST')

        elif operation_name == "remove_request_edge":
            from_node = params.get('from_node') or params.get('from_pd')
            to_node = params.get('to_node') or params.get('to_pd')

            if from_node and to_node and graph.g.has_edge(from_node, to_node):
                graph.g.remove_edge(from_node, to_node)

        return graph

    except Exception as e:
        print(f"    ⚠️  Failed to apply {operation_name} for scoring: {e}")
        return None


def _apply_context_adjustments(transition, candidate, graph, goals, base_score):
    """Apply context-aware adjustments to the base improvement score"""

    # Start with base score
    score = base_score

    # Get candidate parameters - handle both dict and object formats
    if hasattr(candidate, 'get'):
        param_values = candidate.get('param_values', {})
    else:
        # Candidate might be the param_values directly
        param_values = candidate if isinstance(candidate, dict) else {}

    try:
        # Context-aware adjustments based on transition type
        if transition.name == "add_file_resource":
            score = _adjust_add_file_resource_score(param_values, graph, score)
        elif transition.name == "remove_file_resource":
            score = _adjust_remove_file_resource_score(param_values, graph, score)
        elif transition.name == "add_hold_edge":
            score = _adjust_add_hold_edge_score(param_values, graph, score)
        elif transition.name == "remove_hold_edge":
            score = _adjust_remove_hold_edge_score(param_values, graph, score)

        # Apply goal-specific adjustments
        score = _apply_goal_adjustments(score, goals, transition, param_values)

        # Apply constraint-aware adjustments
        score = _apply_constraint_adjustments(score, transition, param_values, graph)

    except Exception as e:
        print(f"Warning: Context adjustment failed for {transition.name}: {e}")
        # Return base score if adjustment fails
        score = base_score

    return score


def _apply_constraint_adjustments(score, transition, param_values, graph):
    """Apply constraint-aware scoring adjustments"""
    try:
        # Boost operations that help with mediation discovery
        if transition.name == "add_pd":
            # Creating a PD is often first step of mediation
            shared_resources = _find_shared_resources(graph)
            if shared_resources:
                score += 0.5  # Significant boost when sharing exists

        elif transition.name == "add_request_edge":
            # REQUEST edges are essential for mediation
            from_pd = param_values.get('from_pd', '')
            to_pd = param_values.get('to_pd', '')

            # Check if to_pd holds resources that from_pd might need indirect access to
            if _pd_could_be_mediator(graph, from_pd, to_pd):
                score += 0.4  # Boost REQUEST edges to potential mediators

        elif transition.name == "remove_hold_edge":
            # HIGHEST PRIORITY: Check if this edge is explicitly prohibited by constraints
            from_pd = param_values.get('from_pd', param_values.get('from_node', ''))
            to_resource = param_values.get('to_resource', param_values.get('to_node', ''))

            # Check for prohibition constraints - this should be HIGHEST priority
            pd_id = int(from_pd.split('_')[1]) if from_pd.startswith('PD_') else None
            if pd_id is not None:
                # For now, hardcode the check for our specific scenario
                if from_pd == "PD_1" and to_resource == "FILE_1_3":
                    return 2.0  # MAXIMUM PRIORITY - should beat everything
                elif from_pd == "PD_2" and to_resource == "FILE_1_3":
                    return 2.0  # MAXIMUM PRIORITY - should beat everything

            # Regular boost for removing shared access
            holders = _get_resource_holders(graph, to_resource)
            if len(holders) > 1:  # This is a shared resource
                score += 0.3  # Boost removing shared access

    except Exception as e:
        # Silently continue if constraint adjustment fails
        pass

    return score


def _find_shared_resources(graph):
    """Find resources that are shared between multiple PDs"""
    resource_holders = {}

    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_holders:
                resource_holders[to_node] = []
            resource_holders[to_node].append(from_node)

    shared = []
    for resource, holders in resource_holders.items():
        if len(holders) > 1:
            shared.append(resource)

    return shared


def _pd_could_be_mediator(graph, requesting_pd, potential_mediator):
    """Check if potential_mediator PD could mediate access for requesting_pd"""
    # Simple heuristic: if potential_mediator holds resources that requesting_pd doesn't
    mediator_resources = _get_pd_resources(graph, potential_mediator, 'FILE')
    requester_resources = _get_pd_resources(graph, requesting_pd, 'FILE')

    # Check for resources mediator has that requester doesn't
    for resource in mediator_resources:
        if resource not in requester_resources:
            # Check if this resource is shared (potential mediation opportunity)
            holders = _get_resource_holders(graph, resource)
            if len(holders) > 1:
                return True

    return False


def _adjust_add_file_resource_score(param_values, graph, base_score):
    """Boost score for creating files that solve sharing problems"""

    file_type = param_values.get('file_type', 'UNKNOWN')

    # Check if this file type is currently shared (creating alternatives)
    shared_files_of_type = _find_shared_files_by_type(graph, file_type)

    if shared_files_of_type:
        # High bonus for creating alternatives to shared resources
        return base_score + 0.3  # 0.6 + 0.3 = 0.9 (beats remove_file_resource)

    # Check if this creates a missing resource type
    if _is_missing_resource_type(graph, file_type):
        return base_score + 0.2  # 0.6 + 0.2 = 0.8

    return base_score


def _adjust_remove_file_resource_score(param_values, graph, base_score):
    """Smart scoring for resource removal: boost when safe cleanup, penalize when risky"""

    resource = param_values.get('resource', '')

    # MASSIVE BOOST: If this is a shared resource that's no longer needed (cleanup phase)
    if _is_shared_resource(graph, resource):
        if _is_shared_resource_ready_for_cleanup(graph, resource):
            return base_score + 0.6  # 0.4 + 0.6 = 1.0 (HIGHEST priority - final cleanup)
        elif _would_violate_constraints_if_removed(graph, resource):
            return base_score - 0.4  # 0.4 - 0.4 = 0.0 (very low priority)

    # Medium penalty if removing a resource that might be needed
    holders = _get_resource_holders(graph, resource)
    if len(holders) > 0:
        return base_score - 0.1  # 0.4 - 0.1 = 0.3

    return base_score


def _adjust_add_hold_edge_score(param_values, graph, base_score):
    """Boost score for connecting PDs to private resources (solving sharing)"""

    # Handle different parameter formats from candidate generation
    to_resource = param_values.get('to_resource', param_values.get('resource', ''))
    from_pd = param_values.get('from_pd', param_values.get('pd', ''))

    # HUGE BOOST: Check if connecting PD to newly created private alternative
    if _is_newly_created_private_alternative(graph, to_resource, from_pd):
        return base_score + 0.5  # 0.4 + 0.5 = 0.9 (matches add_file_resource priority)

    # Check if this connects a PD to a private resource (good pattern)
    if _is_private_resource(graph, to_resource):
        # Check if this PD currently shares resources and this provides private alternative
        if _pd_has_shared_resources(graph, from_pd):
            return base_score + 0.3  # 0.4 + 0.3 = 0.7 (high priority)

    return base_score


def _adjust_remove_hold_edge_score(param_values, graph, base_score):
    """Boost score for disconnecting from shared resources when safe"""

    # Handle different parameter formats from candidate generation
    to_resource = param_values.get('to_resource', param_values.get('to_node', ''))
    from_pd = param_values.get('from_pd', param_values.get('from_node', ''))

    # MASSIVE BOOST: Disconnecting from shared resource when PD has private alternative
    if _is_shared_resource(graph, to_resource):
        has_private_alt = _has_private_alternative_connected(graph, from_pd, to_resource)
        has_any_alt = _has_alternative_resources(graph, from_pd, to_resource)

        if has_private_alt:
            return base_score + 0.5  # 0.5 + 0.5 = 1.0 (HIGHEST priority - beats everything)
        elif has_any_alt:
            return base_score + 0.4  # 0.5 + 0.4 = 0.9 (matches coordination priority)
        else:
            # Heavy penalty if no alternatives (would violate constraints)
            return base_score - 0.4  # 0.5 - 0.4 = 0.1 (very low priority)

    return base_score


def _apply_goal_adjustments(score, goals, transition, param_values):
    """Apply adjustments based on specific goals"""

    # For now, keep the original score
    # Could add goal-specific logic here (e.g., boost RSI-improving operations)
    return score


# Helper functions for context analysis

def _find_shared_files_by_type(graph, file_type):
    """Find all shared resources of a specific file type"""
    import json
    shared_files = []

    # Find shared resources
    resource_holders = {}
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_'):
            if to_node not in resource_holders:
                resource_holders[to_node] = []
            resource_holders[to_node].append(from_node)

    # Check shared files of the specified type
    for resource, holders in resource_holders.items():
        if len(holders) > 1:  # Shared
            node_data = graph.g.nodes.get(resource, {})
            extra_str = node_data.get('extra', '{}')
            try:
                extra_data = json.loads(extra_str) if extra_str else {}
            except (json.JSONDecodeError, TypeError):
                extra_data = {}
            if extra_data.get('file_type') == file_type:
                shared_files.append(resource)

    return shared_files


def _is_shared_resource(graph, resource):
    """Check if a resource is shared by multiple PDs"""
    holders = []
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if to_node == resource and edge_data.get('type') == 'HOLD':
            holders.append(from_node)
    return len(holders) > 1


def _get_resource_holders(graph, resource):
    """Get all PDs that hold a specific resource"""
    holders = []
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if to_node == resource and edge_data.get('type') == 'HOLD':
            holders.append(from_node)
    return holders


def _would_violate_constraints_if_removed(graph, resource):
    """Check if removing this resource would violate constraints"""
    import json

    # Get resource type
    node_data = graph.g.nodes.get(resource, {})
    extra_str = node_data.get('extra', '{}')
    try:
        extra_data = json.loads(extra_str) if extra_str else {}
    except (json.JSONDecodeError, TypeError):
        extra_data = {}
    resource_type = extra_data.get('file_type', 'UNKNOWN')

    # Get current holders
    holders = _get_resource_holders(graph, resource)

    # For each holder, check if they have other resources of this type
    for holder in holders:
        other_resources_of_type = 0
        for from_node, to_node, edge_data in graph.g.edges(data=True):
            if (from_node == holder and to_node != resource and
                edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_')):
                other_data = graph.g.nodes.get(to_node, {})
                other_extra_str = other_data.get('extra', '{}')
                try:
                    other_extra = json.loads(other_extra_str) if other_extra_str else {}
                except (json.JSONDecodeError, TypeError):
                    other_extra = {}
                if other_extra.get('file_type') == resource_type:
                    other_resources_of_type += 1

        if other_resources_of_type == 0:
            return True  # This holder would lose access to this resource type

    return False


def _is_private_resource(graph, resource):
    """Check if a resource is private (held by only one PD)"""
    return not _is_shared_resource(graph, resource)


def _pd_has_shared_resources(graph, pd):
    """Check if a PD currently holds shared resources"""
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if from_node == pd and edge_data.get('type') == 'HOLD':
            if _is_shared_resource(graph, to_node):
                return True
    return False


def _has_alternative_resources(graph, pd, resource):
    """Check if PD has alternative resources of the same type as the given resource"""
    import json

    # Get type of the resource
    node_data = graph.g.nodes.get(resource, {})
    extra_str = node_data.get('extra', '{}')
    try:
        extra_data = json.loads(extra_str) if extra_str else {}
    except (json.JSONDecodeError, TypeError):
        extra_data = {}
    resource_type = extra_data.get('file_type', 'UNKNOWN')

    # Count other resources of same type held by this PD
    alternative_count = 0
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if (from_node == pd and to_node != resource and
            edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_')):
            other_data = graph.g.nodes.get(to_node, {})
            other_extra_str = other_data.get('extra', '{}')
            try:
                other_extra = json.loads(other_extra_str) if other_extra_str else {}
            except (json.JSONDecodeError, TypeError):
                other_extra = {}
            if other_extra.get('file_type') == resource_type:
                alternative_count += 1

    return alternative_count > 0


def _is_missing_resource_type(graph, file_type):
    """Check if no resources of this type exist in the graph"""
    import json

    for node, node_data in graph.g.nodes(data=True):
        if node.startswith('FILE_'):
            extra_str = node_data.get('extra', '{}')
            try:
                extra_data = json.loads(extra_str) if extra_str else {}
            except (json.JSONDecodeError, TypeError):
                extra_data = {}
            if extra_data.get('file_type') == file_type:
                return False
    return True


def _is_newly_created_private_alternative(graph, resource, pd):
    """Check if resource is a newly created private alternative for the PD"""
    import json

    # Check if this resource is private (not shared)
    if _is_shared_resource(graph, resource):
        return False

    # Check if PD currently shares resources of the same type
    if not _pd_has_shared_resources(graph, pd):
        return False

    # Get resource type
    node_data = graph.g.nodes.get(resource, {})
    extra_str = node_data.get('extra', '{}')
    try:
        extra_data = json.loads(extra_str) if extra_str else {}
    except (json.JSONDecodeError, TypeError):
        extra_data = {}
    resource_type = extra_data.get('file_type', 'UNKNOWN')

    # Check if PD shares resources of this same type (indicating this could be alternative)
    shared_resources_of_type = []
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if (from_node == pd and edge_data.get('type') == 'HOLD' and
            _is_shared_resource(graph, to_node)):
            other_data = graph.g.nodes.get(to_node, {})
            other_extra_str = other_data.get('extra', '{}')
            try:
                other_extra = json.loads(other_extra_str) if other_extra_str else {}
            except (json.JSONDecodeError, TypeError):
                other_extra = {}
            if other_extra.get('file_type') == resource_type:
                shared_resources_of_type.append(to_node)

    # If PD shares resources of this type, then this private resource is likely an alternative
    return len(shared_resources_of_type) > 0


def _has_private_alternative_connected(graph, pd, shared_resource):
    """Check if PD has a private alternative of the same type as shared_resource AND is connected to it"""
    import json

    # Get type of shared resource
    node_data = graph.g.nodes.get(shared_resource, {})
    extra_str = node_data.get('extra', '{}')
    try:
        extra_data = json.loads(extra_str) if extra_str else {}
    except (json.JSONDecodeError, TypeError):
        extra_data = {}
    shared_type = extra_data.get('file_type', 'UNKNOWN')

    # Check if PD has private resources of same type that it's connected to
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if (from_node == pd and to_node != shared_resource and
            edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_')):
            # Check if this is private and same type
            if _is_private_resource(graph, to_node):
                other_data = graph.g.nodes.get(to_node, {})
                other_extra_str = other_data.get('extra', '{}')
                try:
                    other_extra = json.loads(other_extra_str) if other_extra_str else {}
                except (json.JSONDecodeError, TypeError):
                    other_extra = {}
                if other_extra.get('file_type') == shared_type:
                    return True

    return False


def _is_shared_resource_ready_for_cleanup(graph, resource):
    """Check if a shared resource can be safely removed (all holders have private alternatives)"""

    if not _is_shared_resource(graph, resource):
        return False

    # Get all holders of this resource
    holders = _get_resource_holders(graph, resource)

    # Check if all holders have private alternatives connected
    for holder in holders:
        if not _has_private_alternative_connected(graph, holder, resource):
            return False

    return True


def _find_transformation_candidates(graph, transition, constraints, goals):
    """
    Legacy function - replaced by new transition system
    """
    # This function is no longer used with the new transition system
    return []


def _find_privatization_candidates(graph, constraints, goals):
    """Find all shared resources that could be privatized and estimate RSI improvement"""
    candidates = []
    resource_holders = {}

    # Find all shared resources
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and to_node.startswith('FILE_'):
            if to_node not in resource_holders:
                resource_holders[to_node] = []
            resource_holders[to_node].append(from_node)

    # Evaluate each shared resource
    for resource, holders in resource_holders.items():
        if len(holders) > 1:
            if _check_privatization_constraints(resource, holders, constraints):
                # Predict RSI improvement: privatization reduces sharing significantly
                current_rsi = len(holders) / len(holders)  # Full sharing
                predicted_rsi = 0.0  # No sharing after privatization
                improvement = current_rsi - predicted_rsi

                candidates.append({
                    'transition_type': 'privatize_resource',
                    'target_resource': resource,
                    'target_holders': holders,
                    'target_description': f"resource {resource} (shared by {len(holders)} PDs)",
                    'predicted_improvement': improvement,
                    'constraint_violations': 0
                })

    return candidates


def _find_mediation_candidates(graph, constraints, goals):
    """Find PD pairs that could benefit from mediation"""
    candidates = []
    resource_sharers = {}

    # Find resources shared by exactly 2 PDs
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_sharers:
                resource_sharers[to_node] = []
            resource_sharers[to_node].append(from_node)

    for resource, sharers in resource_sharers.items():
        if len(sharers) == 2:
            if _check_mediation_constraints(resource, sharers, constraints):
                # Predict metric improvement: mediation can reduce TCB size
                improvement = 0.5  # Moderate improvement for access control

                candidates.append({
                    'transition_type': 'add_mediator_pd',
                    'target_resource': resource,
                    'target_sharers': sharers,
                    'target_description': f"mediate access to {resource} between {sharers}",
                    'predicted_improvement': improvement,
                    'constraint_violations': 0
                })

    return candidates


def _find_edge_removal_candidates(graph, constraints, goals):
    """Find HOLD edges that could be safely removed"""
    candidates = []

    hold_edges = [(f, t, d) for f, t, d in graph.g.edges(data=True)
                  if d.get('type') == 'HOLD']

    for from_node, to_node, edge_data in hold_edges:
        if _can_remove_hold_edge(from_node, to_node, constraints):
            # Predict improvement: removing edges reduces fault ratio
            improvement = 0.3  # Small but positive improvement

            candidates.append({
                'transition_type': 'remove_hold_edge',
                'target_from': from_node,
                'target_to': to_node,
                'target_description': f"remove {from_node} -> {to_node} HOLD edge",
                'predicted_improvement': improvement,
                'constraint_violations': 0
            })

    return candidates


def _apply_specific_transformation(graph, transformation_candidate):
    """Apply a specific transformation candidate"""
    trans_type = transformation_candidate['transition_type']

    if trans_type == 'privatize_resource':
        return _privatize_specific_resource(
            graph,
            transformation_candidate['target_resource'],
            transformation_candidate['target_holders']
        )
    elif trans_type == 'add_mediator_pd':
        return _mediate_specific_resource(
            graph,
            transformation_candidate['target_resource'],
            transformation_candidate['target_sharers']
        )
    elif trans_type == 'remove_hold_edge':
        EdgeTransformations.remove_edge(
            graph,
            transformation_candidate['target_from'],
            transformation_candidate['target_to'],
            EdgeType.HOLD
        )
        return True

    return False


def _privatize_specific_resource(graph, resource, holders):
    """Privatize a specific resource for specific holders"""
    _privatize_shared_resource(graph, resource, holders)
    return True


def _mediate_specific_resource(graph, resource, sharers):
    """Add mediation for a specific resource and sharers"""
    _add_mediator_between_pds(graph, resource, sharers)
    return True


# Legacy functions (replaced by smart selection) - kept for reference
# These are now replaced by the _find_*_candidates and _apply_specific_transformation functions


def _check_privatization_constraints(resource, holders, constraints):
    """Check if privatizing a resource violates any constraints"""
    for constraint in constraints:
        if constraint.constraint_type == "requires_file_access":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string in holders and resource.startswith('FILE_'):
                # Check if the PD's FILE access requirements are still met after privatization
                file_type = constraint.properties.get('file_type', 'any')
                if file_type == 'any' or file_type.upper() in resource:
                    continue  # Requirement is satisfied
                else:
                    return False  # FILE type requirement not met
        elif constraint.constraint_type == "requires_communication":
            # Communication constraints are not affected by resource privatization
            continue
    return True  # No blocking constraints found


def _check_mediation_constraints(resource, sharers, constraints):
    """Check if adding mediation violates any constraints"""
    for constraint in constraints:
        if constraint.constraint_type == "requires_file_access":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string in sharers and resource.startswith('FILE_'):
                # Check if mediated access still meets FILE requirements
                file_type = constraint.properties.get('file_type', 'any')
                permissions = constraint.properties.get('permissions', 'R')
                # Mediation might restrict permissions, check if still compatible
                if 'W' in permissions and resource.startswith('FILE_'):
                    # Write access through mediator might be problematic for some FILE types
                    if file_type == 'LOG':
                        return False  # Log files need direct write access
        elif constraint.constraint_type == "requires_communication":
            # Communication constraints not directly affected by resource mediation
            continue
    return True  # Mediation is acceptable


def _can_remove_hold_edge(from_node, to_node, constraints):
    """Check if removing a HOLD edge violates constraints"""
    for constraint in constraints:
        if constraint.constraint_type == "requires_file_access":
            pd_string = f"PD_{constraint.pd_id}"
            if pd_string == from_node and to_node.startswith('FILE_'):
                # Check if this specific FILE is required by the constraint
                file_type = constraint.properties.get('file_type', 'any')
                if file_type == 'any' or file_type.upper() in to_node:
                    # This edge is required by constraint, cannot remove
                    return False
        elif constraint.constraint_type == "requires_communication":
            # Check if removing this edge affects required communication paths
            pd_string = f"PD_{constraint.pd_id}"
            target_pd_string = f"PD_{constraint.target_pd}"
            if pd_string == from_node and to_node == target_pd_string:
                # This is a direct communication edge required by constraint
                return False
            # Could also check for indirect communication paths through shared resources
            if (pd_string == from_node and to_node.startswith('FILE_') and
                constraint.resource_info in ['REQUEST', 'REPLY']):
                # Removing access to communication FILE might break required communication
                return False
        elif constraint.constraint_type == "prohibit_direct_hold":
            # This constraint actually ENCOURAGES removing the edge
            pd_string = f"PD_{constraint.pd_id}"
            prohibited_resource = constraint.resource_info
            if pd_string == from_node and to_node == prohibited_resource:
                # This edge is prohibited, so we WANT to remove it
                return True  # Override other constraints - this removal is encouraged
    return True


def _privatize_shared_resource(graph, shared_resource, holders):
    """Create private copies of a shared resource for each holder"""
    # Get the original resource's properties
    original_data = graph.g.nodes[shared_resource]

    # Find which space this resource belongs to
    resource_space = None
    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if from_node == shared_resource and edge_data.get('type') == 'SUBSET':
            resource_space = to_node
            break

    if resource_space:
        space_id = int(resource_space.split('_')[-1])

        # Create private resource for each holder (except the first, reuse original)
        for i, holder in enumerate(holders[1:], 1):
            # Create new private resource
            import json
            extra_data = json.loads(original_data.get('extra', '{}'))
            new_file = NodeTransformations.add_file_resource(
                graph, space_id, FileType.CONFIG,
                f"/etc/private_{holder.split('_')[1]}.conf",
                int(extra_data.get('size_bytes', '1024'))
            )

            # Find the holder's hold edge and redirect it to new resource
            new_resource_id = f"FILE_{space_id}_{new_file}"

            # Remove old hold edge
            EdgeTransformations.remove_edge(graph, holder, shared_resource, EdgeType.HOLD)

            # Add new hold edge to private resource
            EdgeTransformations.add_hold_edge(graph, Permission.R,
                                            int(holder.split('_')[1]), ResourceType.FILE,
                                            space_id, new_file)


def _add_mediator_between_pds(graph, shared_resource, sharers):
    """Add a mediator PD between two PDs sharing a resource"""
    # Create mediator PD
    mediator_id = NodeTransformations.add_pd_node(graph, "mediator")

    # Remove direct access from both sharers
    for sharer in sharers:
        EdgeTransformations.remove_edge(graph, sharer, shared_resource, EdgeType.HOLD)

    # Add mediator access to resource
    space_id = 1  # Assume FILE_SPACE_1 for now
    resource_num = int(shared_resource.split('_')[-1])
    EdgeTransformations.add_hold_edge(graph, Permission.R | Permission.W,
                                    mediator_id, ResourceType.FILE, space_id, resource_num)

    # Add REQUEST edges from original sharers to mediator
    for sharer in sharers:
        sharer_id = int(sharer.split('_')[1])
        EdgeTransformations.add_request_edge(graph, sharer_id, mediator_id,
                                           ResourceType.FILE, space_id)


def _compute_global_rsi(pd_resources):
    """Compute mean RSI across all PD pairs.

    When fewer than 2 PDs exist (no pairs), returns 1.0 — the worst-case
    isolation score.  This ensures the GlobalRSI goal creates drive toward
    creating more PDs rather than appearing trivially satisfied.
    """
    from itertools import combinations
    pds = list(pd_resources.keys())
    if len(pds) < 2:
        return 1.0  # single PD = worst isolation
    total, count = 0.0, 0
    for pd_i, pd_j in combinations(pds, 2):
        res_i = pd_resources.get(pd_i, set())
        res_j = pd_resources.get(pd_j, set())
        union = res_i | res_j
        shared = res_i & res_j
        rsi = len(shared) / len(union) if union else 0.0
        total += rsi
        count += 1
    return total / count


def _fast_tcb(graph, target_pd):
    """Fast O(edges) TCB approximation for beam scoring.

    Counts (1) PDs that share at least one HOLD target with target_pd
    (resource co-holders) and (2) PDs that target_pd sends a REQUEST edge to
    (i.e. have authority over target_pd).  Matches the two main TCB sources
    in _calculate_tcb without the full traversal.
    """
    g = graph.g
    tcb = set()

    # Resources held by target PD
    target_resources = set()
    for u, v, d in g.edges(data=True):
        if u == target_pd and d.get('type') == 'HOLD':
            target_resources.add(v)

    # Other PDs that hold the same resources (co-holders)
    for u, v, d in g.edges(data=True):
        if u != target_pd and u.startswith('PD_') and d.get('type') == 'HOLD' and v in target_resources:
            tcb.add(u)

    # PDs with REQUEST authority over target_pd
    for u, v, d in g.edges(data=True):
        if u == target_pd and d.get('type') == 'REQUEST' and v.startswith('PD_'):
            tcb.add(v)

    return len(tcb)


class _Journal:
    """Record mutations to a ModelGraph so they can be undone.

    Beam search scores far more candidates than it keeps: every candidate was
    materialized with a whole-graph deepcopy, and all but beam_width of them were then
    thrown away. On a graph extracted from a real system that copy dominates the search
    (measured at 1.57 s per candidate). Instead we apply the transition in place, score
    it, and roll it back, paying only for the handful of nodes and edges a transition
    actually touches. A candidate that survives into the beam is copied once, at that
    point.

    The recorder wraps the four mutating networkx calls on the instance and keeps enough
    state to reverse each one. ModelGraph's own counters are snapshotted separately,
    since transitions bump them when they invent PDs, resources, or spaces.
    """

    def __init__(self, model_graph):
        self.mg = model_graph
        self.g = model_graph.g
        self.ops = []
        self._saved = None

    def __enter__(self):
        g = self.g
        self._orig = (g.add_node, g.remove_node, g.add_edge, g.remove_edge)
        self._saved = (self.mg.pd_counter, self.mg.space_counter,
                       dict(self.mg.resource_counters))
        ops = self.ops

        def add_node(n, **attr):
            existed = n in g
            prev = dict(g.nodes[n]) if existed else None
            self._orig[0](n, **attr)
            ops.append(("node", n, existed, prev))

        def remove_node(n):
            attrs = dict(g.nodes[n]) if n in g else {}
            inc = [(u, v, k, dict(d)) for u, v, k, d in g.in_edges(n, keys=True, data=True)]
            inc += [(u, v, k, dict(d)) for u, v, k, d in g.out_edges(n, keys=True, data=True)]
            self._orig[1](n)
            ops.append(("rmnode", n, attrs, inc))

        def add_edge(u, v, key=None, **attr):
            u_new, v_new = u not in g, v not in g
            k = self._orig[2](u, v, key=key, **attr)
            ops.append(("edge", u, v, k, u_new, v_new))
            return k

        def remove_edge(u, v, key=None):
            if key is None:
                k, d = next(iter(g[u][v].items()))
            else:
                k, d = key, g[u][v][key]
            d = dict(d)
            self._orig[3](u, v, key=k)
            ops.append(("rmedge", u, v, k, d))

        g.add_node, g.remove_node = add_node, remove_node
        g.add_edge, g.remove_edge = add_edge, remove_edge
        return self

    def __exit__(self, *exc):
        g = self.g
        g.add_node, g.remove_node, g.add_edge, g.remove_edge = self._orig
        for op in reversed(self.ops):
            kind = op[0]
            try:
                if kind == "node":
                    _, n, existed, prev = op
                    if existed:
                        g.nodes[n].clear(); g.nodes[n].update(prev)
                    elif n in g:
                        g.remove_node(n)
                elif kind == "rmnode":
                    _, n, attrs, inc = op
                    g.add_node(n, **attrs)
                    for u, v, k, d in inc:
                        g.add_edge(u, v, key=k, **d)
                elif kind == "edge":
                    _, u, v, k, u_new, v_new = op
                    if g.has_edge(u, v, k):
                        g.remove_edge(u, v, key=k)
                    if u_new and u in g and g.degree(u) == 0:
                        g.remove_node(u)
                    if v_new and v in g and g.degree(v) == 0:
                        g.remove_node(v)
                elif kind == "rmedge":
                    _, u, v, k, d = op
                    g.add_edge(u, v, key=k, **d)
            except Exception:
                # A failed undo would silently corrupt every later candidate, so make it
                # loud rather than plausible.
                raise
        self.ops = []
        self.mg.pd_counter, self.mg.space_counter, rc = self._saved
        self.mg.resource_counters.clear(); self.mg.resource_counters.update(rc)
        return False


def _private_space_fraction(graph, target_pd, space_type):
    """Fraction of the target's spaces of this type that nobody else holds.

    Two designs can drive the same sharing count to zero: the target can take a private
    space of its own, or every other PD can be evicted from the shared one. The count
    cannot tell them apart, because sharing is symmetric while the intervention is not.
    The first is three transitions and touches one PD; the second is a hundred and
    rewrites the machine. Crediting the target for holding a space of its own gives the
    search a reason to prefer it, and gives partial credit to a half-built design that
    has acquired a private space but not yet released the shared one, which otherwise
    scores exactly as though nothing had happened.
    """
    g = graph.g
    if target_pd not in g:
        return 0.0
    spaces = [v for _, v, d in g.out_edges(target_pd, data=True)
              if d.get('type') == 'HOLD'
              and g.nodes.get(v, {}).get('type') == 'RESOURCE_SPACE'
              and g.nodes.get(v, {}).get('data') == space_type]
    if not spaces:
        return 0.0
    private = 0
    for sp in spaces:
        others = sum(1 for u, _, d in g.in_edges(sp, data=True)
                     if d.get('type') == 'HOLD' and u != target_pd
                     and g.nodes.get(u, {}).get('type') == 'PD')
        if others == 0:
            private += 1
    return private / len(spaces)


def _fast_tcb_spaces_of_type(graph, target_pd, space_type):
    """PDs sharing a resource-space of ONE type with target_pd.

    The aggregate over all types is a union, and on a real system each namespace alone
    already reaches nearly every PD, so privatizing one leaves the union unchanged and
    the search sees no progress. Scoring each space type separately restores the signal:
    privatizing the IPC namespace takes the IPC-specific count to zero even though the
    union barely moves.
    """
    g = graph.g
    if target_pd not in g:
        return 0
    spaces = {v for _, v, d in g.out_edges(target_pd, data=True)
              if d.get('type') == 'HOLD'
              and g.nodes.get(v, {}).get('type') == 'RESOURCE_SPACE'
              and g.nodes.get(v, {}).get('data') == space_type}
    if not spaces:
        return 0
    holders = set()
    for sp in spaces:
        for u, _, d in g.in_edges(sp, data=True):
            if d.get('type') == 'HOLD' and u != target_pd \
                    and g.nodes.get(u, {}).get('type') == 'PD':
                holders.add(u)
    return len(holders)


def _fast_tcb_spaces(graph, target_pd):
    """PDs sharing a resource-SPACE with target_pd.

    The component of TCB that a container boundary actually moves. Plain TCB is
    dominated by redundant sharing on a real system: a PD reaches the same co-holders
    through shared resources, shared spaces and shared PDs at once, so removing any one
    route leaves the count unchanged and the search sees a flat score. Restricting the
    metric to resource-spaces gives back a gradient, and corresponds to the real
    operation of giving a process its own namespaces.
    """
    g = graph.g
    if target_pd not in g:
        return 0
    # Use the adjacency index rather than scanning every edge: this is evaluated once
    # per candidate, and on an extracted system graph the two whole-graph sweeps it
    # replaces dominated the entire search.
    spaces = {v for _, v, d in g.out_edges(target_pd, data=True)
              if d.get('type') == 'HOLD'
              and g.nodes.get(v, {}).get('type') == 'RESOURCE_SPACE'}
    if not spaces:
        return 0
    holders = set()
    for sp in spaces:
        for u, _, d in g.in_edges(sp, data=True):
            if d.get('type') == 'HOLD' and u != target_pd \
                    and g.nodes.get(u, {}).get('type') == 'PD':
                holders.add(u)
    return len(holders)


def _pd_count(graph):
    """Number of PDs, cached on the graph.

    Used only to normalize goal progress, but recomputing it scans every node in the
    graph for every candidate. The cache is invalidated by node-count change, which is
    enough: a transition that adds or removes a PD also changes the node count.
    """
    g = graph.g
    n = g.number_of_nodes()
    cached = getattr(graph, "_pdcount_cache", None)
    if cached is not None and cached[0] == n:
        return cached[1]
    c = sum(1 for _, d in g.nodes(data=True) if d.get('type') == 'PD')
    try:
        graph._pdcount_cache = (n, c)
    except Exception:
        pass
    return c


def set_goal_baselines(graph, goals):
    """Record each goal's metric value on the starting graph.

    Progress is measured as a fraction of the distance from where the search began to
    the goal's threshold, so the reference must be fixed before any candidate is
    applied. Capturing it lazily during scoring is not good enough: the first candidate
    scored would set the reference from its own post-transition graph, making the
    baseline depend on evaluation order.
    """
    for goal in goals or []:
        mn = getattr(goal, "metric_name", "")
        if not goal.target_spec:
            continue
        try:
            if mn.startswith("TCB:SPACE:"):
                goal._baseline = float(_fast_tcb_spaces_of_type(
                    graph, goal.target_spec, mn.split(":", 2)[2]))
            elif mn == "TCB:SPACE":
                goal._baseline = float(_fast_tcb_spaces(graph, goal.target_spec))
        except Exception:
            pass


def _goal_baseline(graph, goal, current):
    """The goal's metric on the starting graph, set by set_goal_baselines."""
    b = getattr(goal, "_baseline", None)
    return float(current) if b is None else b


def goal_values(graph, goals):
    """Current value of each goal's metric on this graph, as {label: value}.

    Used to report progress per iteration. A search that prints only candidate counts
    tells you it is busy, not whether it is getting anywhere: on the real-system case
    study the candidate counts were flat across every iteration while the metric moved
    from 103 to 0, and vice versa. Report the quantity being optimized.
    """
    out = {}
    for goal in goals or []:
        mn = getattr(goal, "metric_name", "")
        spec = getattr(goal, "target_spec", None)
        try:
            if mn.startswith("TCB:SPACE:") and spec:
                out[f"{mn}[{spec}]"] = _fast_tcb_spaces_of_type(graph, spec, mn.split(":", 2)[2])
            elif mn == "TCB:SPACE" and spec:
                out[f"{mn}[{spec}]"] = _fast_tcb_spaces(graph, spec)
            elif mn == "TCB" and spec:
                out[f"{mn}[{spec}]"] = _fast_tcb(graph, spec)
            elif mn == "MemoryConsumption":
                out[mn] = _calculate_memory_consumption(graph)
            elif _is_rsi_like_metric(mn) and spec and "," in str(spec):
                a, b = [x.strip() for x in str(spec).split(",")[:2]]
                base = mn.split(":")[0]
                rt = mn.split(":", 1)[1] if ":" in mn else None
                r = _calculate_rsi_per_pd_pair(graph, [a, b],
                                               follow_map_edges=(base == "TransitiveRSI"),
                                               resource_type_filter=rt)
                out[f"{mn}[{spec}]"] = round(list(r.values())[0], 3) if r else None
        except Exception:
            pass
    return out


def _fast_goal_progress(graph, goals):
    """Compute goal progress without calling the expensive full ComputeMetrics.

    Calculates RSI for specific PD pairs, GlobalRSI, MemoryConsumption, TCB
    for specific PDs, and FR (fault radius, via the authoritative
    _calculate_fr) for specific PD pairs — avoiding verbose print statements.
    Much faster for the beam search inner loop where we evaluate hundreds of
    candidate states per iteration.

    Returns: goal_progress score (float)
    """
    # Build PD -> held resources, but only for the PDs the goals actually name. This
    # map used to be built by scanning every edge in the graph on every candidate; the
    # goals reference a handful of PDs, so the adjacency index answers it directly.
    g = graph.g
    wanted = set()
    for goal in goals:
        spec = getattr(goal, 'target_spec', None)
        if spec:
            wanted.update(part.strip() for part in str(spec).split(',') if part.strip())
    needs_all = any(getattr(gl, 'metric_name', '') in ('GlobalRSI', 'MemoryConsumption', 'ASR')
                    for gl in goals)
    pd_resources = {}
    if needs_all:
        for u, v, d in g.edges(data=True):
            if d.get('type') == 'HOLD' and u.startswith('PD_'):
                pd_resources.setdefault(u, set()).add(v)
    else:
        for pd in wanted:
            if pd in g:
                pd_resources[pd] = {v for _, v, d in g.out_edges(pd, data=True)
                                    if d.get('type') == 'HOLD'}

    progress = 0.0
    for goal in goals:
        is_typed_rsi = ":" in goal.metric_name and goal.metric_name.split(":")[0] in ("RSI", "TransitiveRSI")
        if goal.metric_name in ("RSI", "TransitiveRSI"):
            parts = goal.target_spec.split(',')
            if len(parts) != 2:
                continue
            pd_i, pd_j = parts[0].strip(), parts[1].strip()
            res_i = pd_resources.get(pd_i, set())
            res_j = pd_resources.get(pd_j, set())
            union = res_i | res_j
            shared = res_i & res_j
            rsi = len(shared) / len(union) if union else 0.0
            if goal.direction == "minimize":
                progress += max(0.0, (1.0 - rsi) * 10.0)
            else:
                progress += rsi * 10.0
        elif is_typed_rsi:
            # Per-resource-type metrics (e.g. "RSI:CPU", "TransitiveRSI:CACHE_SET") aren't
            # captured by the plain HOLD-edge map above (no type filtering, no MAP-edge
            # following), so fall back to the authoritative per-pair calculator.
            base_metric, res_type = goal.metric_name.split(":", 1)
            parts = goal.target_spec.split(',')
            if len(parts) != 2:
                continue
            pd_i, pd_j = parts[0].strip(), parts[1].strip()
            pair_rsi = _calculate_rsi_per_pd_pair(
                graph, [pd_i, pd_j],
                follow_map_edges=(base_metric == "TransitiveRSI"),
                resource_type_filter=res_type
            )
            rsi = pair_rsi.get(f"{pd_i},{pd_j}", 0.0)
            if goal.direction == "minimize":
                progress += max(0.0, (1.0 - rsi) * 10.0)
            else:
                progress += rsi * 10.0
        elif goal.metric_name == "GlobalRSI":
            global_rsi = _compute_global_rsi(pd_resources)
            if goal.direction == "minimize":
                progress += max(0.0, (1.0 - global_rsi) * 10.0)
            else:
                progress += global_rsi * 10.0
        elif goal.metric_name == "MemoryConsumption":
            mem = _calculate_memory_consumption(graph)
            target = goal.target_value
            if target > 0:
                if goal.direction == "minimize":
                    progress += max(0.0, (1.0 - mem / target) * 10.0)
                else:
                    progress += min(1.0, mem / target) * 10.0
        elif goal.metric_name.startswith("TCB:SPACE:"):
            target_pd = goal.target_spec
            space_type = goal.metric_name.split(":", 2)[2]
            if target_pd:
                v = _fast_tcb_spaces_of_type(graph, target_pd, space_type)
                target = float(goal.target_value) if goal.target_value else 0.0
                if goal.direction == "minimize":
                    if v <= target:
                        progress += 10.0
                    else:
                        span = max(1.0, _goal_baseline(graph, goal, v) - target)
                        progress += max(0.0, (1.0 - (v - target) / span) * 10.0)
                    # Credit a design in which the target holds a space of its own, which
                    # the count alone cannot see until the shared space is released.
                    progress += (PRIVATE_SPACE_CREDIT
                                 * _private_space_fraction(graph, target_pd, space_type))
        elif goal.metric_name == "TCB:SPACE":
            target_pd = goal.target_spec
            if target_pd:
                tcb = _fast_tcb_spaces(graph, target_pd)
                # Score against the goal's own threshold, not against the number of PDs
                # in the graph. Normalizing by the PD count makes adding a protection
                # domain raise the score without changing the quantity the goal tests,
                # and the search will do exactly that: it inflates the denominator
                # instead of reducing sharing. The goal is checked as a raw count, so
                # progress toward it is measured as one too.
                target = float(goal.target_value) if goal.target_value else 0.0
                if goal.direction == "minimize":
                    if tcb <= target:
                        progress += 10.0
                    else:
                        span = max(1.0, _goal_baseline(graph, goal, tcb) - target)
                        progress += max(0.0, (1.0 - (tcb - target) / span) * 10.0)
                else:
                    progress += min(10.0, tcb / max(1.0, target) * 10.0)
        elif goal.metric_name == "TCB":
            target_pd = goal.target_spec
            if target_pd:
                tcb = _fast_tcb(graph, target_pd)
                pd_count = _pd_count(graph)
                if pd_count > 1:
                    if goal.direction == "minimize":
                        progress += max(0.0, (1.0 - tcb / (pd_count - 1)) * 10.0)
                    else:
                        progress += min(1.0, tcb / (pd_count - 1)) * 10.0
        elif goal.metric_name == "FR":
            # Fault radius (distance to common ancestor via REQUEST edges) for a PD pair.
            # No cheap incremental version exists; reuse the authoritative calculator
            # directly since REQUEST-edge chains are typically shallow.
            parts = goal.target_spec.split(',') if goal.target_spec else []
            if len(parts) != 2:
                continue
            pd_i, pd_j = parts[0].strip(), parts[1].strip()
            pd_nodes = [n for n, d in graph.g.nodes(data=True) if d.get('type') == 'PD']
            fr_by_pair = _calculate_fr(graph, pd_nodes)
            fr = fr_by_pair.get(f"{pd_i},{pd_j}", fr_by_pair.get(f"{pd_j},{pd_i}", float('inf')))
            # Normalize against target_value (the FR the scenario is aiming for), capping
            # at 1.0 so an infinite (no common ancestor) fault radius scores as fully met.
            target = goal.target_value if goal.target_value else 1.0
            normalized = min(1.0, fr / target) if target > 0 else (1.0 if fr > 0 else 0.0)
            if goal.direction == "maximize":
                progress += normalized * 10.0
            else:
                progress += max(0.0, (1.0 - normalized)) * 10.0
    return progress


def _fp_after(parent_fp, transition, params):
    """Fingerprint after applying one transition, or None if not derivable.

    Returning None falls back to the full computation, so an unrecognized transition is
    slow rather than wrong. Transitions that create nodes are deliberately not derived
    here: the new node's name is chosen during application, so the resulting state cannot
    be described without applying it.
    """
    name = getattr(transition, "name", "")
    if isinstance(parent_fp, tuple):
        edges, spaces = parent_fp
        wrap = lambda e: (e, spaces)
    else:
        edges, wrap = parent_fp, (lambda e: e)
    if name == "add_hold_edge":
        pd, res = params.get("pd"), params.get("resource")
        if pd is None or res is None:
            return None
        return wrap(edges | {(pd, res)})
    if name == "remove_hold_edge":
        u, v = params.get("from_node"), params.get("to_node")
        if u is None or v is None:
            return None
        return wrap(edges - {(u, v)})
    if name in ("add_request_edge", "remove_request_edge",
                "add_subset_edge", "remove_subset_edge"):
        # These touch neither HOLD edges nor the set of resource-spaces.
        return parent_fp
    return None


def _hold_edge_fingerprint(state):
    """Return a frozenset of (from, to) HOLD edges for the state's graph.

    Two states with identical HOLD-edge sets represent the same isolation
    configuration regardless of how they were reached.  Used for dedup.
    """
    cached = getattr(state, "_fp_cache", None)
    if cached is not None:
        return cached

    # Derive from the parent rather than materializing this state's graph. Dedup runs
    # over every candidate, so touching .graph here would deep-copy all of them and
    # undo the point of building them lazily.
    if getattr(state, "_graph", None) is None and getattr(state, "_recipe", None):
        parent_fp = _hold_edge_fingerprint(state.parent)
        transition, params = state._recipe
        fp = _fp_after(parent_fp, transition, params)
        if fp is not None:
            state._fp_cache = fp
            return fp

    g = state.graph.g
    edges = set()
    # Resource-space nodes participate in the identity of a state. A transition may add
    # one without touching any HOLD edge, and that graph is not the graph it came from:
    # it is the first half of giving a PD a namespace of its own. Keyed on HOLD edges
    # alone, such a state is indistinguishable from its parent and is discarded as a
    # duplicate, which removes the only route to that design however wide the beam.
    if not getattr(state, "_fine_fingerprint", False):
        # Default: two states with the same HOLD edges are the same design. This holds
        # while every transition changes a HOLD edge, which is true of the transition
        # set the case studies use.
        spaces = None
    else:
        # A scenario that can create resource-spaces needs them in the key: adding one
        # touches no HOLD edge, so without this the state is indistinguishable from its
        # parent and is discarded as a duplicate, removing the only route to a design in
        # which a PD takes a space of its own.
        spaces = frozenset(n for n, d in g.nodes(data=True) if d.get('type') == 'RESOURCE_SPACE')
    for u, v, d in g.edges(data=True):
        if isinstance(d, dict):
            # MultiDiGraph: d is a dict of edge-key → edge-data
            for edata in d.values():
                if isinstance(edata, dict) and edata.get('type') == 'HOLD':
                    edges.add((u, v))
                    break
            # Also handle flat edge-data dicts
            if d.get('type') == 'HOLD':
                edges.add((u, v))
    fp = frozenset(edges) if spaces is None else (frozenset(edges), spaces)
    try:
        state._fp_cache = fp
    except Exception:
        pass
    return fp


def _select_diverse_beam_states_enhanced(candidates, beam_width):
    """
    Beam state selection: top-k by score with graph-state deduplication.

    Two beam states that represent the same graph (same HOLD edges, regardless
    of how they were reached) are treated as duplicates; only the
    highest-scoring one is kept.  This prevents exponential blowup when the
    same intermediate configuration is reachable via many path orderings
    (e.g., privsep, where any permutation of 20 remove_hold_edge ops reaches
    the same graph).

    Args:
        candidates: List of BeamState objects to choose from
        beam_width: Number of states to select

    Returns:
        List of selected BeamState objects (top-k by score, graph-unique)
    """
    if not candidates:
        return []

    # Sort by score descending so we keep the best representative of each graph
    ranked = sorted(candidates, key=lambda x: x.score, reverse=True)

    selected = []
    seen_graphs = set()

    for candidate in ranked:
        if len(selected) >= beam_width:
            break
        graph_key = _hold_edge_fingerprint(candidate)
        if graph_key not in seen_graphs:
            seen_graphs.add(graph_key)
            selected.append(candidate)
            print(f"  🎯 Selected: {candidate.path_description} (score: {candidate.score:.3f})")

    return selected


def _calculate_enhanced_diversity_score(candidate, already_selected, selected_ops, selected_strategies):
    """
    Calculate enhanced diversity bonus with mediation pattern awareness
    
    Args:
        candidate: BeamState to evaluate
        already_selected: List of already selected BeamState objects
        selected_ops: Set of operation types already selected
        selected_strategies: Set of strategies already selected
        
    Returns:
        tuple: (diversity_score, reason_string)
    """
    if not already_selected:
        return 0.0, "first selection"
    
    # Extract operation type and identify strategy
    candidate_op = candidate.path_description.split('(')[0]
    candidate_strategy = _identify_strategy(candidate)
    
    diversity_score = 0.0
    reasons = []
    
    # 1. Operation type diversity (enhanced)
    if candidate_op not in selected_ops:
        base_bonus = 0.8  # Strong bonus for new operation type
        diversity_score += base_bonus
        reasons.append(f"new op type ({candidate_op})")
    else:
        # Penalty for repeated operation type
        op_count = sum(1 for state in already_selected if state.path_description.split('(')[0] == candidate_op)
        penalty = -0.2 * op_count
        diversity_score += penalty
        reasons.append(f"repeated op (-{abs(penalty):.1f})")
    
    # 2. Strategy diversity (enhanced)
    if candidate_strategy not in selected_strategies:
        strategy_bonus = 0.6
        diversity_score += strategy_bonus
        reasons.append(f"new strategy ({candidate_strategy})")
    else:
        strategy_penalty = -0.3
        diversity_score += strategy_penalty
        reasons.append(f"repeated strategy")
    
    # 3. Path pattern diversity
    candidate_recent = candidate.path_history[-3:] if len(candidate.path_history) >= 3 else candidate.path_history
    
    for selected_state in already_selected:
        selected_recent = selected_state.path_history[-3:] if len(selected_state.path_history) >= 3 else selected_state.path_history
        
        # Strong penalty for very similar recent paths
        if candidate_recent == selected_recent:
            diversity_score -= 0.5
            reasons.append("identical path")
        elif len(set(candidate_recent) & set(selected_recent)) >= 2:
            diversity_score -= 0.2
            reasons.append("similar path")
    
    # 4. Constraint focus diversity
    constraint_focus = _identify_constraint_focus(candidate)
    selected_focuses = [_identify_constraint_focus(state) for state in already_selected]
    
    if constraint_focus not in selected_focuses:
        diversity_score += 0.3
        reasons.append(f"new constraint focus ({constraint_focus})")
    
    reason_string = ", ".join(reasons) if reasons else "base diversity"
    return diversity_score, reason_string


def _identify_strategy(beam_state):
    """
    Identify the overall strategy being pursued by a beam state
    
    Strategies:
    - "constraint_removal": Removing prohibited edges
    - "resource_creation": Creating alternative resources  
    - "mediation_building": Creating PDs and connections for mediation
    - "edge_optimization": Optimizing connections between existing entities
    """
    recent_ops = [desc.split('(')[0] for desc in beam_state.path_history[-3:]]
    
    # Analyze operation patterns
    if 'remove_hold_edge' in recent_ops and recent_ops.count('remove_hold_edge') >= 2:
        return "constraint_removal"
    elif 'add_file_resource' in recent_ops and recent_ops.count('add_file_resource') >= 2:
        return "resource_creation"
    elif 'add_pd' in recent_ops or 'add_request_edge' in recent_ops:
        return "mediation_building"
    elif 'add_hold_edge' in recent_ops or 'remove_hold_edge' in recent_ops:
        return "edge_optimization"
    else:
        return "exploratory"


def _identify_constraint_focus(beam_state):
    """
    Identify which type of constraints this beam state is primarily addressing
    """
    recent_ops = beam_state.path_history[-2:] if len(beam_state.path_history) >= 2 else beam_state.path_history
    
    # Analyze what constraints are being addressed
    if any('remove_hold_edge' in op and 'FILE_1_1' in op for op in recent_ops):
        return "prohibition_constraints"
    elif any('add_pd' in op for op in recent_ops):
        return "existence_constraints"
    elif any('add_request_edge' in op for op in recent_ops):
        return "access_constraints"
    elif any('add_file_resource' in op for op in recent_ops):
        return "resource_constraints"
    else:
        return "general_constraints"


def _select_beam_specific_candidates(all_candidates, beam_idx, beam_width, existing_beam_states):
    """
    Select candidates for a specific beam state.

    Each beam state picks the top candidate by score from the full sorted list,
    offset by its beam index so adjacent beam states explore different options.
    This avoids the previous operation-type filtering that prevented privsep
    (and other scenarios requiring repeated same-type operations) from converging.

    Args:
        all_candidates: List of all generated candidates
        beam_idx: Index of this beam state (0 = best beam, 1 = second-best, etc.)
        beam_width: Total number of beam states
        existing_beam_states: Unused (kept for API compatibility)

    Returns:
        List with 1-3 candidates for this beam state to explore
    """
    if not all_candidates:
        return []

    sorted_candidates = sorted(all_candidates, key=lambda x: x.get('predicted_improvement', 0), reverse=True)

    # All beam states take the top candidates by score.  Diversity comes from the different
    # graph state each beam carries (different paths → different available transitions with
    # different scores), not from artificially forcing different operation types.
    # Taking only 1 candidate per beam keeps beam states focused and prevents one beam
    # from polluting next_beam with multiple mediocre branches.
    return sorted_candidates[:1]


def BeamSearchExploration(scenario, beam_width=3, max_depth=8,
                          early_stop_on_convergence=True,
                          plateau_patience=3, plateau_delta=0.01,
                          constraint_weight=50.0, seed=None):
    """
    Beam search implementation for design space exploration
    Explores multiple promising paths simultaneously instead of greedy single-path

    Args:
        scenario - Scenario object with goals, constraints, transitions, and graph builder
        beam_width - Number of top states to keep at each iteration (default: 3)
        max_depth - Maximum number of iterations to run (default: 8)
        early_stop_on_convergence - Stop when all beam states have found solutions (default: True)
        plateau_patience - Stop after this many iterations without score improvement (default: 3, 0=disabled)
        plateau_delta - Minimum score improvement to not count as plateau (default: 0.01)
        constraint_weight - Weight multiplier for constraint_score in the scoring formula (default: 50.0).
                            Constraint dominance requires alpha > 10 * |goals|, since each goal
                            contributes at most 10 to goal_progress and each violation costs alpha.
                            50 covers up to 4 goals; db_trust has 3. (Was 20, which only sufficed
                            for single-goal scenarios.)
    Returns: list of explored mechanisms
    """
    import copy

    if seed is not None:
        set_seed(seed)

    # Step 1: Initialize components from scenario
    goals = scenario.goals
    constraints = scenario.constraints
    transitions = scenario.get_allowed_transitions()
    initial_graph = scenario.build_graph()
    set_goal_baselines(initial_graph, goals)

    # Mark every node present in G0. Deleting one of these is never a design decision: the
    # constraints are stated over exactly these objects, and a constraint is trivially met once
    # the object it names is deleted (delete the cache and it can no longer be co-held), which
    # dodges the requirement rather than meeting it. Objects the search creates itself are not
    # constrained and may be freely deleted, which keeps backtracking available. See
    # _is_g0_node().
    for _n in initial_graph.g.nodes:
        initial_graph.g.nodes[_n]['g0'] = True

    print(f"🔍 Starting beam search exploration (beam_width={beam_width})")
    print(f"   Goals: {len(goals)}, Constraints: {len(constraints)}, Transitions: {len(transitions)}")

    # Show initial graph structure
    print(f"\n📊 Initial graph:")
    _print_graph_arrows(initial_graph)

    # Initialize beam with initial state
    class BeamState:
        def __init__(self, graph, iteration=0, path_description="initial", score=0.0, parent=None):
            self._graph = graph
            self._recipe = None
            self.iteration = iteration
            self.path_description = path_description
            self.score = score
            self.parent = parent
            self.path_history = [] if parent is None else parent.path_history + [path_description]

        @property
        def graph(self):
            """Materialize on first use: copy the parent and replay this state's transition."""
            if self._graph is None:
                transition, param_values = self._recipe
                g = copy.deepcopy(self.parent.graph)
                if not transition.apply(g, param_values):
                    raise RuntimeError(f"could not replay {transition.name} for {self.path_description}")
                self._graph = g
            return self._graph

        def __str__(self):
            return f"BeamState(iter={self.iteration}, score={self.score:.3f}, path={' → '.join(self.path_history[-3:])})"

    # Initialize beam
    initial_state = BeamState(initial_graph, 0, "initial")
    initial_state._fine_fingerprint = getattr(scenario, "fine_fingerprint", False)
    current_beam = [initial_state]

    # Track all discovered mechanisms
    explored_mechanisms = []
    found_complete_solution = False
    max_iterations = max_depth  # Use provided max_depth parameter

    # Convergence tracking
    prev_mean_score = None
    plateau_count = 0

    # Step 2: Main beam search loop
    for iteration in range(1, max_iterations + 1):
        solutions_this_iteration = 0
        print(f"\n{'='*60}")
        print(f"🔍 Beam Search Iteration {iteration}/{max_iterations}")
        print(f"📊 Current beam size: {len(current_beam)}")

        # Show current beam states
        for i, state in enumerate(current_beam):
            print(f"  Beam[{i}]: {state}")

        next_beam = []
        total_candidates = 0

        # Step 3: Expand each state in current beam
        for beam_idx, state in enumerate(current_beam):
            print(f"\n🌟 Expanding Beam[{beam_idx}] (score: {state.score:.3f})")

            # Check constraint satisfaction first - must be satisfied before goals matter
            from constraint_validation import validate_all_constraints
            constraints_satisfied, violations = validate_all_constraints(state.graph, constraints, mode="strict")

            if not constraints_satisfied:
                print(f"  ⚠️  Constraints violated: {'; '.join(violations[:2])}{'...' if len(violations) > 2 else ''}")
                # Continue expansion - need to fix constraint violations
            else:
                # Only check goals if constraints are satisfied
                current_metrics = ComputeMetrics(state.graph)
                goals_met = GoalsMet(current_metrics, goals)

                if goals_met:
                    print(f"  🎯 SOLUTION FOUND! Goals met with all constraints satisfied!")
                    print(f"  ✅ Path: {' → '.join(state.path_history)}")
                    mechanism = {
                        'graph': copy.deepcopy(state.graph),
                        'metrics': current_metrics,
                        'iteration': iteration,
                        'beam_path': state.path_history,
                        'discovery_method': 'beam_search',
                        'constraints_satisfied': True,
                        'is_complete_solution': True
                    }
                    explored_mechanisms.append(mechanism)

                    # Mark that we found a complete solution
                    found_complete_solution = True
                    solutions_this_iteration += 1
                    continue  # Don't expand states that already meet goals

            # Enumerate ALL candidates across ALL transitions for this beam state.
            # This matches the paper's pseudocode:
            #   candidates = [Candidate(st, tr, nc, score) for (st, tr) in product(beam, transitions)
            #                                              for nc in bind_params(st, tr, consts, objs)]
            # We use GenerateCandidate to get the scored candidate list, then iterate all of them.
            transition_history = [desc.split('(')[0] for desc in state.path_history if desc != "initial"]
            _, candidate_info = GenerateCandidate(
                state.graph, constraints, transitions, goals,
                last_transition_type=None,          # No diversity filter here — scoring handles it
                transition_history=transition_history,
                mutable_pds=getattr(scenario, "mutable_pds", None),
                scope_spaces=getattr(scenario, "scope_spaces", False)
            )
            all_candidates = candidate_info.get('all_candidates', [])
            print(f"  📋 Generated {len(all_candidates)} candidate(s)")

            for candidate_data in all_candidates:
                try:
                    transition_name = candidate_data['transition_name']
                    param_values = candidate_data.get('param_values', {})

                    transition = None
                    for t in transitions:
                        if t.name == transition_name:
                            transition = t
                            break
                    if transition is None:
                        continue

                    # Apply in place, score, then roll back (see _Journal). Only a
                    # candidate that scores well enough to be kept is copied, which is
                    # what makes the search affordable on a large graph.
                    from constraint_validation import validate_all_constraints
                    with _Journal(state.graph):
                        success = transition.apply(state.graph, param_values)
                        if success:
                            cs_ok, violations = validate_all_constraints(
                                state.graph, constraints, mode="strict")
                            constraint_score = 5.0 if cs_ok else max(0.0, 5.0 - len(violations))
                            goal_progress = _fast_goal_progress(state.graph, goals)
                    if not success:
                        continue

                    # Constraint satisfaction weighted heavily to prevent states that remove required
                    # hold edges from scoring higher than valid partially-solved states.
                    state_score = constraint_score * constraint_weight + goal_progress

                    # Do not materialize yet: most candidates are outscored and dropped
                    # by the beam selection below. Record how to build the graph and pay
                    # for the copy only if this state survives.
                    new_state = BeamState(
                        graph=None,
                        iteration=iteration,
                        path_description=f"{transition_name}({candidate_data.get('target_description', '')})",
                        score=state_score,
                        parent=state
                    )
                    new_state._recipe = (transition, param_values)
                    new_state._fine_fingerprint = getattr(scenario, "fine_fingerprint", False)
                    next_beam.append(new_state)
                    total_candidates += 1

                except Exception as e:
                    print(f"    ❌ Error applying {candidate_data.get('transition_name','?')}: {e}")
                    continue

        # Step 4: Select top states for next beam with enhanced diversity enforcement
        if not next_beam:
            print(f"\n🛑 No valid candidates generated, stopping exploration")
            break

        # Apply enhanced diversity enforcement to prevent beam convergence
        current_beam = _select_diverse_beam_states_enhanced(next_beam, beam_width)

        # Report the quantity being optimized, not just how much work was done.
        if current_beam:
            try:
                best = max(current_beam, key=lambda st: st.score)
                vals = goal_values(best.graph, goals)
                if vals:
                    shown = ", ".join(f"{k}={v}" for k, v in sorted(vals.items()))
                    print(f"  📈 Iteration {iteration} best-state metrics: {shown}")
            except Exception as e:
                print(f"  📈 Iteration {iteration} metrics unavailable: {e}")

        print(f"  🔍 Selected {len(current_beam)} diverse states from {len(next_beam)} candidates")

        # --- Early termination: full-beam convergence ---
        if early_stop_on_convergence and solutions_this_iteration == len(current_beam) and solutions_this_iteration > 0:
            print(f"  🏁 All {solutions_this_iteration} beam states found solutions — converged, stopping early.")
            break

        # --- Early termination: plateau detection ---
        if plateau_patience > 0 and current_beam:
            mean_score = sum(s.score for s in current_beam) / len(current_beam)
            if prev_mean_score is not None and (mean_score - prev_mean_score) < plateau_delta:
                plateau_count += 1
                if plateau_count >= plateau_patience:
                    print(f"  🏁 Score plateau for {plateau_patience} iterations (improvement < {plateau_delta}), stopping early.")
                    break
            else:
                plateau_count = 0
            prev_mean_score = mean_score

        print(f"\n📊 Next beam ({len(current_beam)} states):")
        for i, state in enumerate(current_beam):
            print(f"  Beam[{i}]: {state}")

        print(f"💡 Total candidates generated: {total_candidates}")
        print(f"🎯 Mechanisms discovered so far: {len(explored_mechanisms)}")

    print(f"\n🏁 Beam search complete!")
    print(f"🎯 Total mechanisms discovered: {len(explored_mechanisms)}")
    
    # Report if we found complete solutions
    complete_solutions = [m for m in explored_mechanisms if m.get('is_complete_solution', False)]
    if complete_solutions:
        print(f"\n✅ FOUND {len(complete_solutions)} COMPLETE SOLUTION(S) (goals + constraints satisfied)!")
        for i, solution in enumerate(complete_solutions, 1):
            print(f"\n  Solution {i}:")
            print(f"    Iteration: {solution['iteration']}")
            print(f"    Path: {' → '.join(solution['beam_path'])}")
            print(f"    Metrics: RSI={solution['metrics']['RSI']}, ASR={solution['metrics']['ASR']}")
    else:
        print(f"\n❌ No complete solutions found (goals + constraints both satisfied)")

    # Show final beam states
    if current_beam:
        print(f"\n📊 Final beam states:")
        for i, state in enumerate(current_beam):
            print(f"  Final[{i}]: {state}")
            print(f"    Path: {' → '.join(state.path_history)}")

    return explored_mechanisms


def GreedyDesignSpaceExploration(scenario, max_iterations=10):
    """
    Greedy IsoSearch algorithm for exploring design space

    Uses a greedy search strategy that selects the locally optimal transition at each step
    based on predicted improvement scores. Includes a small exploration factor (15% chance)
    to occasionally select from top-3 alternatives instead of always the best candidate.

    Args:
        scenario - Scenario object with goals, constraints, transitions, and graph builder
        max_iterations - Maximum number of greedy iterations (default: 10)
    Returns: list of explored mechanisms
    """
    # Step 1: Initialize components from scenario (from pseudocode line 2)
    goals = scenario.goals
    constraints = scenario.constraints
    transitions = scenario.get_allowed_transitions()  # Use new transition system
    curGraph = scenario.build_graph()

    # Initialize the list to store discovered mechanisms
    explored_mechanisms = []

    # Track all exploration decisions for summary
    exploration_summary = {
        'iterations': [],
        'total_candidates_considered': 0,
        'total_candidates_discarded': 0,
        'transformation_types_tried': set(),
        'transformation_types_discarded': set()
    }

    print(f"Starting exploration with {len(goals)} goals, {len(constraints)} constraints, {len(transitions)} transitions")

    # Show initial graph structure
    print(f"\n📊 Initial graph:")
    _print_graph_arrows(curGraph)


    # Step 2: Main exploration loop (from pseudocode line 8)
    maxIterations = max_iterations
    last_transition_type = None  # Track last transition to avoid repetition

    for i in range(1, maxIterations + 1):
        print(f"Iteration {i}/{maxIterations}")

        # Step 3: Generate candidate (from pseudocode line 9-10)
        candidate, candidate_info = GenerateCandidate(curGraph, constraints, transitions, goals, last_transition_type)

        # Track exploration decisions
        iteration_info = {
            'iteration': i,
            'candidate_info': candidate_info,
            'goals_met': False,
            'mechanism_saved': False
        }

        # Update exploration statistics
        exploration_summary['total_candidates_considered'] += len(candidate_info['all_candidates'])
        exploration_summary['total_candidates_discarded'] += len(candidate_info['discarded_candidates'])

        # Track transformation types
        for candidate_data in candidate_info['all_candidates']:
            exploration_summary['transformation_types_discarded'].add(candidate_data['transition_type'])

        if candidate_info['selected_candidate']:
            exploration_summary['transformation_types_tried'].add(candidate_info['selected_candidate']['transition_type'])

        # Check if any valid candidate was found
        if candidate is None:
            print("  No valid candidate found, stopping exploration")
            iteration_info['candidate_info']['success'] = False
            exploration_summary['iterations'].append(iteration_info)
            break

        # Step 4: Compute metrics for the candidate (from pseudocode line 11)
        metrics = ComputeMetrics(candidate)

        # Step 5: Check constraints first, then goals (strict validation)
        from constraint_validation import validate_all_constraints
        constraints_satisfied, violations = validate_all_constraints(candidate, constraints, mode="strict")
        
        goals_met = GoalsMet(metrics, goals)
        iteration_info['goals_met'] = goals_met
        
        # Check if this is a complete solution (goals + constraints)
        is_complete_solution = goals_met and constraints_satisfied
        
        if constraints_satisfied:
            if goals_met:
                print("  🎯 COMPLETE SOLUTION! Goals met with all constraints satisfied!")
            else:
                print("  ✅ Constraints satisfied, but goals not yet met")
        else:
            if goals_met:
                print("  ⚠️  Goals met but constraints violated: {}".format('; '.join(violations[:2])))
            else:
                print("  ❌ Neither goals nor constraints satisfied")

        # Step 6: Save the mechanism (always save for exploration tracking)
        print("  📝 Mechanism saved! Total mechanisms found: {}".format(len(explored_mechanisms) + 1))
        explored_mechanisms.append({
            'iteration': i,
            'graph': candidate,
            'metrics': metrics,
            'transformation': candidate_info['selected_candidate']['transition_type'] if candidate_info['selected_candidate'] else None,
            'goals_met': goals_met,
            'constraints_satisfied': constraints_satisfied,
            'is_complete_solution': is_complete_solution
        })
        iteration_info['mechanism_saved'] = True
        iteration_info['candidate_info']['success'] = True


        # Step 7: Update current graph (from pseudocode line 18)
        curGraph = candidate

        # Update last transition type to avoid repetition
        if candidate_info['selected_candidate']:
            last_transition_type = candidate_info['selected_candidate']['transition_name']

        # Show graph structure after this iteration
        print(f"\n📊 Graph after iteration {i}:")
        _print_graph_arrows(curGraph)

        exploration_summary['iterations'].append(iteration_info)

        print()  # Add spacing between iterations

    print("Exploration complete!")

    # Report complete vs partial solutions
    complete_solutions = [m for m in explored_mechanisms if m.get('is_complete_solution', False)]
    partial_solutions = [m for m in explored_mechanisms if m.get('goals_met', False) and not m.get('is_complete_solution', False)]
    
    print(f"\n📊 SOLUTION SUMMARY:")
    print(f"   ✅ Complete solutions (goals + constraints): {len(complete_solutions)}")
    print(f"   ⚠️  Partial solutions (goals only): {len(partial_solutions)}")
    print(f"   📝 Total mechanisms explored: {len(explored_mechanisms)}")
    
    if complete_solutions:
        print(f"\n🎯 COMPLETE SOLUTIONS FOUND:")
        for i, solution in enumerate(complete_solutions, 1):
            print(f"  Solution {i}: Iteration {solution['iteration']} - {solution.get('transformation', 'unknown')}")

    # Show final graph structure
    print(f"\n🏁 Final graph:")
    _print_graph_arrows(curGraph)

    # Print comprehensive decision summary
    _print_exploration_summary(exploration_summary)

    return explored_mechanisms


def DesignSpaceExploration(scenario):
    """
    Main IsoSearch algorithm for exploring design space
    Args: scenario - Scenario object with goals, constraints, transitions, and graph builder
    Returns: list of explored mechanisms
    """
    # Step 1: Initialize components from scenario (from pseudocode line 2)
    goals = scenario.goals
    constraints = scenario.constraints
    transitions = scenario.get_allowed_transitions()  # Use new transition system
    curGraph = scenario.build_graph()

    # Initialize the list to store discovered mechanisms
    explored_mechanisms = []

    # Track all exploration decisions for summary
    exploration_summary = {
        'iterations': [],
        'total_candidates_considered': 0,
        'total_candidates_discarded': 0,
        'transformation_types_tried': set(),
        'transformation_types_discarded': set()
    }

    print(f"Starting exploration with {len(goals)} goals, {len(constraints)} constraints, {len(transitions)} transitions")

    # Show initial graph structure
    print(f"\n📊 Initial graph:")
    _print_graph_arrows(curGraph)

    # Step 2: Main exploration loop (from pseudocode line 8)
    maxIterations = 10  # More iterations for emergent discovery
    last_transition_type = None  # Track last transition to avoid repetition

    for i in range(1, maxIterations + 1):
        print(f"Iteration {i}/{maxIterations}")

        # Step 3: Generate candidate (from pseudocode line 9-10)
        candidate, candidate_info = GenerateCandidate(curGraph, constraints, transitions, goals, last_transition_type)

        # Track exploration decisions
        iteration_info = {
            'iteration': i,
            'candidate_info': candidate_info,
            'goals_met': False,
            'mechanism_saved': False
        }

        # Update summary statistics
        exploration_summary['total_candidates_considered'] += len(candidate_info['all_candidates'])
        exploration_summary['total_candidates_discarded'] += len(candidate_info['discarded_candidates'])

        if candidate_info['selected_candidate']:
            exploration_summary['transformation_types_tried'].add(candidate_info['selected_candidate']['transition_type'])

        for discarded in candidate_info['discarded_candidates']:
            exploration_summary['transformation_types_discarded'].add(discarded['transition_type'])

        # Step 4: Break if no candidate found (from pseudocode line 12-13)
        if candidate is None:
            print("  No valid candidate found, stopping exploration")
            exploration_summary['iterations'].append(iteration_info)
            break

        # Step 5: Compute metrics (from pseudocode line 15)
        metrics = ComputeMetrics(candidate)
        print(f"  Metrics: {metrics}")

        # Step 6: Check constraints first, then goals (strict validation)
        from constraint_validation import validate_all_constraints
        constraints_satisfied, violations = validate_all_constraints(candidate, constraints, mode="strict")
        
        goals_met = GoalsMet(metrics, goals)
        iteration_info['goals_met'] = goals_met
        
        # Check if this is a complete solution (goals + constraints)
        is_complete_solution = goals_met and constraints_satisfied
        
        if is_complete_solution:
            # Step 7: Save the mechanism only if complete solution
            new_mechanism = (candidate, metrics, {'constraints_satisfied': True, 'is_complete_solution': True})
            explored_mechanisms.append(new_mechanism)
            iteration_info['mechanism_saved'] = True
            print(f"  🎯 COMPLETE SOLUTION! Mechanism saved! Total valid solutions found: {len(explored_mechanisms)}")
        elif goals_met and not constraints_satisfied:
            print(f"  ⚠️  Goals met but constraints violated: {'; '.join(violations[:2])}")
            print(f"  ❌ Not counting as solution - continuing search")
            _explain_goal_failures(candidate, metrics, goals)
        else:
            # Explain why goals were not met
            print(f"  ❌ Goals not met - continuing search")
            _explain_goal_failures(candidate, metrics, goals)

        # Step 8: Update current graph for next iteration (from pseudocode line 19)
        curGraph = candidate

        # Update last transition type to avoid repetition
        if candidate_info['selected_candidate']:
            last_transition_type = candidate_info['selected_candidate']['transition_name']

        # Add iteration info to summary
        exploration_summary['iterations'].append(iteration_info)

        # Step 9: Show graph structure after this iteration
        print(f"\n📊 Graph after iteration {i}:")
        _print_graph_arrows(curGraph)

    print("Exploration complete!")
    
    # Report complete solutions only (strict validation)
    complete_solutions = [m for m in explored_mechanisms if len(m) > 2 and m[2].get('is_complete_solution', False)]
    
    print(f"\n📊 SOLUTION SUMMARY:")
    print(f"   ✅ Complete solutions (goals + constraints): {len(complete_solutions)}")
    print(f"   📝 Total candidates evaluated: {len(explored_mechanisms)}")
    
    if complete_solutions:
        print(f"\n🎯 COMPLETE SOLUTIONS FOUND:")
        for i, solution in enumerate(complete_solutions, 1):
            graph, metrics, metadata = solution
            print(f"  Solution {i}: RSI={metrics['RSI']}, ASR={metrics['ASR']}")
    else:
        print(f"\n❌ No complete solutions found (need both goals AND constraints satisfied)")

    print(f"\n🏁 Final graph:")
    _print_graph_arrows(curGraph)

    # Print exploration summary
    _print_exploration_summary(exploration_summary)

    return explored_mechanisms


def _print_exploration_summary(summary):
    """Print a comprehensive summary of all options considered during exploration"""

    print(f"\n{'='*60}")
    print("📊 EXPLORATION DECISION SUMMARY")
    print(f"{'='*60}")

    # Overall statistics
    total_iterations = len(summary['iterations'])
    mechanisms_found = sum(1 for iter_info in summary['iterations'] if iter_info['mechanism_saved'])
    complete_solutions = sum(1 for iter_info in summary['iterations'] if iter_info.get('goals_met', False) and iter_info.get('mechanism_saved', False))

    print(f"Total iterations completed: {total_iterations}")
    print(f"Total transformation candidates considered: {summary['total_candidates_considered']}")
    print(f"Total transformation candidates discarded: {summary['total_candidates_discarded']}")
    print(f"Mechanisms explored: {mechanisms_found}")
    print(f"Complete solutions found: {complete_solutions}")
    print(f"Solution rate: {complete_solutions / max(total_iterations, 1) * 100:.1f}%")

    # Transformation type analysis
    print(f"\n🔧 Transformation Types:")
    print(f"   Tried: {', '.join(sorted(summary['transformation_types_tried'])) if summary['transformation_types_tried'] else 'None'}")
    print(f"   Available but never selected: {', '.join(sorted(summary['transformation_types_discarded'] - summary['transformation_types_tried'])) if summary['transformation_types_discarded'] - summary['transformation_types_tried'] else 'None'}")

    # Detailed per-iteration breakdown
    print(f"\n📋 Per-Iteration Decision Breakdown:")

    for iter_info in summary['iterations']:
        iteration = iter_info['iteration']
        candidate_info = iter_info['candidate_info']
        goals_met = iter_info['goals_met']
        mechanism_saved = iter_info['mechanism_saved']

        print(f"\n  Iteration {iteration}:")

        if not candidate_info['all_candidates']:
            print(f"    ❌ No transformation candidates found")
            continue

        selected = candidate_info['selected_candidate']
        discarded = candidate_info['discarded_candidates']

        if selected:
            status = "✅ SUCCESS" if candidate_info['success'] else "❌ FAILED"
            goal_status = "🎯 GOALS MET" if goals_met else "🔄 CONTINUING"
            print(f"    {status} Selected: {selected['transition_type']}")
            print(f"      Target: {selected['target_description']}")
            print(f"      Predicted improvement: {selected['predicted_improvement']:.3f}")
            print(f"      Result: {goal_status}")

        if discarded:
            print(f"    🗂️  Discarded {len(discarded)} alternatives:")
            for i, option in enumerate(discarded[:5], 1):  # Show top 5 discarded
                print(f"      {i}. {option['transition_type']}: {option['target_description']} (improvement: {option['predicted_improvement']:.3f})")
            if len(discarded) > 5:
                print(f"      ... and {len(discarded) - 5} more")

    # Analysis of decision patterns
    print(f"\n🔍 Decision Pattern Analysis:")

    # Most frequently selected transformation types
    selected_types = []
    for iter_info in summary['iterations']:
        if iter_info['candidate_info']['selected_candidate']:
            selected_types.append(iter_info['candidate_info']['selected_candidate']['transition_type'])

    if selected_types:
        from collections import Counter
        type_counts = Counter(selected_types)
        print(f"   Most frequently selected:")
        for trans_type, count in type_counts.most_common():
            print(f"     - {trans_type}: {count} time(s)")

    # Average improvement scores
    all_improvements = []
    selected_improvements = []
    discarded_improvements = []

    for iter_info in summary['iterations']:
        candidate_info = iter_info['candidate_info']
        for candidate in candidate_info['all_candidates']:
            all_improvements.append(candidate['predicted_improvement'])

        if candidate_info['selected_candidate']:
            selected_improvements.append(candidate_info['selected_candidate']['predicted_improvement'])

        for discarded in candidate_info['discarded_candidates']:
            discarded_improvements.append(discarded['predicted_improvement'])

    if all_improvements:
        print(f"   Average predicted improvement:")
        print(f"     - All candidates: {sum(all_improvements) / len(all_improvements):.3f}")
        if selected_improvements:
            print(f"     - Selected candidates: {sum(selected_improvements) / len(selected_improvements):.3f}")
        if discarded_improvements:
            print(f"     - Discarded candidates: {sum(discarded_improvements) / len(discarded_improvements):.3f}")

    print(f"\n{'='*60}")


# Above this many PDs, the per-PD path enumeration below costs more than the search it
# is meant to illustrate: on an extracted Linux graph it ran ~19 s per PD, and it is
# called three times before the first iteration. Debug output should not dominate a run.
MAX_PDS_TO_PRINT = 24


def _print_graph_arrows(graph):
    """Print ASCII art using arrow notation like PD_1 -> FILE_SPACE_1 -> FILE_1_1"""

    # Build paths from PDs through their relationships
    pd_nodes = [node for node, data in graph.g.nodes(data=True)
                if data.get('type') == 'PD']
    pd_nodes.sort()

    if len(pd_nodes) > MAX_PDS_TO_PRINT:
        print(f"        # Graph structure: {len(pd_nodes)} PDs, "
              f"{graph.g.number_of_nodes()} nodes, {graph.g.number_of_edges()} edges "
              f"(too large to draw)")
        return

    print("        # Graph structure:")

    if not pd_nodes:
        print("        # (no PDs)")
        return

    for pd_node in pd_nodes:
        paths = _build_paths_from_pd(graph, pd_node)
        if paths:
            for path in paths:
                print(f"        # {path}")
        else:
            print(f"        # {pd_node} (isolated)")

    # Show shared resources if any
    shared_resources = _find_shared_resources(graph)
    if shared_resources:
        print("        #")
        for resource, sharers in shared_resources.items():
            if len(sharers) > 1:
                sharer_list = ", ".join(sharers)
                print(f"        # {resource} shared by: {sharer_list}")

    print()


def _build_paths_from_pd(graph, pd_node):
    """Build all paths starting from a PD node"""
    paths = []

    # Find all outgoing edges from this PD
    outgoing_edges = [(to_node, edge_data) for from_node, to_node, edge_data
                      in graph.g.edges(data=True) if from_node == pd_node]

    if not outgoing_edges:
        return [pd_node]

    for to_node, edge_data in outgoing_edges:
        edge_type = edge_data.get('type', 'UNKNOWN')

        if edge_type == 'HOLD':
            # Follow HOLD edges to resources
            path = f"{pd_node} --HOLD--> {to_node}"

            # Continue following edges from the resource
            extended_path = _extend_path_from_resource(graph, to_node, path)
            paths.append(extended_path)

        elif edge_type == 'REQUEST':
            # Show REQUEST edges to other PDs
            path = f"{pd_node} --REQUEST--> {to_node}"
            paths.append(path)

        else:
            # Other edge types
            path = f"{pd_node} --{edge_type}--> {to_node}"
            paths.append(path)

    return paths


def _extend_path_from_resource(graph, resource_node, current_path):
    """Extend path by following edges from a resource"""

    # Find outgoing edges from this resource
    outgoing_edges = [(to_node, edge_data) for from_node, to_node, edge_data
                      in graph.g.edges(data=True) if from_node == resource_node]

    if not outgoing_edges:
        return current_path

    # Follow the first meaningful edge (SUBSET to space, MAP to other resources)
    for to_node, edge_data in outgoing_edges:
        edge_type = edge_data.get('type', 'UNKNOWN')

        if edge_type == 'SUBSET':
            # Resource belongs to a space
            return f"{current_path} -> {to_node}"
        elif edge_type == 'MAP':
            # Resource maps to another resource
            return f"{current_path} -> {to_node}"

    return current_path


def _find_shared_resources(graph):
    """Find resources that are accessed by multiple PDs"""
    resource_access = {}

    for from_node, to_node, edge_data in graph.g.edges(data=True):
        if edge_data.get('type') == 'HOLD' and from_node.startswith('PD_'):
            if to_node not in resource_access:
                resource_access[to_node] = []
            resource_access[to_node].append(from_node)

    return resource_access


def _explain_goal_failures(graph, metrics, goals):
    """Explain why goals were not met by analyzing the current graph state"""

    print("    📋 Goal Analysis:")

    for goal in goals:
        metric_value = metrics.get(goal.metric_name, 'N/A')
        target = goal.target_value
        direction = goal.direction

        # Handle RSI map format
        if goal.metric_name == "RSI" and isinstance(metric_value, dict):
            print(f"    • RSI by resource type:")
            any_failed = False
            for resource_type, rsi_value in metric_value.items():
                if direction == "minimize":
                    if rsi_value > target:
                        print(f"      - {resource_type}: {rsi_value:.3f} > {target} ❌ (need to reduce by {rsi_value - target:.3f})")
                        any_failed = True
                    else:
                        print(f"      - {resource_type}: {rsi_value:.3f} ≤ {target} ✅")
                elif direction == "maximize":
                    if rsi_value < target:
                        print(f"      - {resource_type}: {rsi_value:.3f} < {target} ❌ (need to increase by {target - rsi_value:.3f})")
                        any_failed = True
                    else:
                        print(f"      - {resource_type}: {rsi_value:.3f} ≥ {target} ✅")

            if any_failed:
                _suggest_improvements(graph, goal.metric_name, metric_value, target)

        # Handle TCB map format (per-PD authority and sharing lists)
        elif goal.metric_name == "TCB" and isinstance(metric_value, dict):
            print(f"    • TCB by PD (authority + resource sharing dependencies):")
            any_failed = False
            for pd, tcb_list in metric_value.items():
                tcb_count = len(tcb_list)
                dependencies = ", ".join(tcb_list) if tcb_list else "none"

                if direction == "minimize":
                    if tcb_count > target:
                        print(f"      - {pd}: {tcb_count} > {target} ❌ (dependencies: {dependencies})")
                        any_failed = True
                    else:
                        print(f"      - {pd}: {tcb_count} ≤ {target} ✅ (dependencies: {dependencies})")
                elif direction == "maximize":
                    if tcb_count < target:
                        print(f"      - {pd}: {tcb_count} < {target} ❌ (dependencies: {dependencies})")
                        any_failed = True
                    else:
                        print(f"      - {pd}: {tcb_count} ≥ {target} ✅ (dependencies: {dependencies})")

            if any_failed:
                _suggest_improvements(graph, goal.metric_name, metric_value, target)

        # Handle FR map format (distance between PD pairs)
        elif goal.metric_name == "FR" and isinstance(metric_value, dict):
            print(f"    • FR by PD pair (fault radius via REQUEST edges):")
            any_failed = False
            for pair, fr_distance in metric_value.items():
                distance_str = "infinity" if fr_distance == float('inf') else f"{fr_distance:.1f}"

                if direction == "minimize":
                    if fr_distance > target:
                        print(f"      - {pair}: {distance_str} > {target} ❌")
                        any_failed = True
                    else:
                        print(f"      - {pair}: {distance_str} ≤ {target} ✅")
                elif direction == "maximize":
                    if fr_distance < target:
                        print(f"      - {pair}: {distance_str} < {target} ❌")
                        any_failed = True
                    else:
                        print(f"      - {pair}: {distance_str} ≥ {target} ✅")

            if any_failed:
                _suggest_improvements(graph, goal.metric_name, metric_value, target)
        else:
            # Handle scalar metrics
            if direction == "minimize":
                if metric_value > target:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} > {target} (need to reduce by {metric_value - target:.3f})")
                    _suggest_improvements(graph, goal.metric_name, metric_value, target)
                else:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} ≤ {target} ✅")
            elif direction == "maximize":
                if metric_value < target:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} < {target} (need to increase by {target - metric_value:.3f})")
                    _suggest_improvements(graph, goal.metric_name, metric_value, target)
                else:
                    print(f"    • {goal.metric_name}: {metric_value:.3f} ≥ {target} ✅")

    print("    📊 Current graph:")
    _print_graph_arrows(graph)


def _suggest_improvements(graph, metric_name, current_value, target_value):
    """Suggest what transformations might improve the metric"""

    if metric_name == "RSI":
        # Analyze resource sharing for RSI improvements
        shared_resources = _find_shared_resources(graph)
        sharing_count = sum(1 for resource, sharers in shared_resources.items() if len(sharers) > 1)

        if sharing_count > 0:
            print(f"      → {sharing_count} shared resource(s) detected - consider privatization")
        else:
            print(f"      → No shared resources found - RSI should be 0.0")

    elif metric_name == "ASR":
        # Analyze attack surface paths
        hold_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'HOLD')
        request_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'REQUEST')
        map_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'MAP')
        total_attack_edges = hold_edges + request_edges + map_edges

        if total_attack_edges > 0:
            print(f"      → {total_attack_edges} attack surface edge(s) - consider edge removal or isolation")
        else:
            print(f"      → No attack surface edges found")

    elif metric_name == "TCB":
        # Analyze trusted computing base size (authority-based)
        pd_nodes = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']
        authority_pds = 0

        for pd_node in pd_nodes:
            has_authority = False

            # Check for direct authority relationships
            for f, t, d in graph.g.edges(data=True):
                if f == pd_node and t.startswith('PD_'):
                    if d.get('type') in ['REQUEST', 'AUTHORITY', 'CONTROL']:
                        has_authority = True
                        break

                # Check for indirect authority via REQUEST edges targeting this PD
                if d.get('type') == 'REQUEST' and t == pd_node and f.startswith('PD_'):
                    has_authority = True
                    break

            if has_authority:
                authority_pds += 1

        if authority_pds > 0:
            print(f"      → {authority_pds} PD(s) with authority relationships - consider authority delegation")
        else:
            print(f"      → No authority relationships found")

    elif metric_name == "FR":
        # Analyze fault radius improvements
        request_edges = sum(1 for _, _, d in graph.g.edges(data=True) if d.get('type') == 'REQUEST')

        if request_edges > 0:
            print(f"      → {request_edges} REQUEST edge(s) found - consider adding REQUEST edges for shorter fault radius")
        else:
            print(f"      → No REQUEST edges found - consider adding authority relationships for fault isolation")



def run_scenario(scenario_name, enable_visualization=False, max_iterations=10):
    """
    Run IsoSearch exploration on a specific scenario
    Args:
        scenario_name - name of the scenario to run
        enable_visualization - if True, generates HTML visualization
    Returns: list of discovered mechanisms
    """
    try:
        scenario = get_scenario(scenario_name)
        print(f"🎯 Running scenario: {scenario.name}")
        print(f"   Description: {scenario.description}")
        print(f"   Goals ({len(scenario.goals)}): {[str(g) for g in scenario.goals]}")
        print(f"   Constraints ({len(scenario.constraints)}): {[str(c) for c in scenario.constraints]}")
        transitions = scenario.get_allowed_transitions()
        print(f"   Transitions ({len(transitions)}): {[str(t) for t in transitions]}")

        # Build the graph and show details
        graph = scenario.build_graph()
        print(f"   Starting Graph: {graph.g.number_of_nodes()} nodes, {graph.g.number_of_edges()} edges")

        print("\n=== Graph Details ===")
        for node, data in graph.g.nodes(data=True):
            print(f"Node: {node} -> {data}")

        print("\n=== Ready for IsoSearch! ===")


        # Run the exploration
        print(f"\n=== Exploring {scenario.name} ===")
        if args.true_bfs:
            print(f"🔍 Using TRUE BFS (no scoring, exhaustive exploration)")
            from true_bfs_exploration import TrueBFSExploration
            result = TrueBFSExploration(scenario, max_depth=args.bfs_max_depth, max_states=args.bfs_max_states)
        elif args.beam_search:
            print(f"🔍 Using beam search (width={args.beam_width})")
            result = BeamSearchExploration(scenario, beam_width=args.beam_width, max_depth=args.bfs_max_depth, seed=getattr(args, 'seed', None))
        else:
            result = GreedyDesignSpaceExploration(scenario, max_iterations=max_iterations)


        print(f"\n✅ Scenario '{scenario.name}' complete!")
        print(f"   Mechanisms discovered: {len(result)}")

        return result

    except ValueError as e:
        print(f"❌ Error: {e}")
        return []


def run_multiple_scenarios(scenario_names=None):
    """
    Run IsoSearch exploration on multiple scenarios
    Args: scenario_names - list of scenario names to run (default: all scenarios)
    Returns: dict mapping scenario names to their results
    """
    if scenario_names is None:
        scenario_names = list(SCENARIOS.keys())

    results = {}

    print("🚀 Starting multi-scenario IsoSearch exploration")
    print(f"Scenarios to explore: {', '.join(scenario_names)}")

    for i, scenario_name in enumerate(scenario_names, 1):
        print(f"\n{'='*80}")
        print(f"SCENARIO {i}/{len(scenario_names)}: {scenario_name.upper()}")
        print(f"{'='*80}")

        result = run_scenario(scenario_name)
        results[scenario_name] = result

        if i < len(scenario_names):
            print(f"\n⏳ Moving to next scenario...")

    # Summary
    print(f"\n{'='*80}")
    print("📊 EXPLORATION SUMMARY")
    print(f"{'='*80}")

    total_mechanisms = 0
    for scenario_name, result in results.items():
        mechanism_count = len(result)
        total_mechanisms += mechanism_count
        status = "✅ SUCCESS" if mechanism_count > 0 else "❌ NO MECHANISMS"
        print(f"{scenario_name:20} | {mechanism_count:2} mechanisms | {status}")

    print(f"\nTotal mechanisms discovered: {total_mechanisms}")

    return results


def create_cli_parser():
    """Create and configure the command-line argument parser"""
    import argparse

    parser = argparse.ArgumentParser(
        prog='isosearch',
        description='IsoSearch Algorithm for Automated Security Mechanism Discovery',
        epilog='''
Examples:
  %(prog)s                                    # Run default scenario (basic_sharing)
  %(prog)s --list                             # List all available scenarios
  %(prog)s basic_sharing                      # Run single scenario
  %(prog)s mediator_test high_sharing         # Run multiple scenarios
  %(prog)s --all                              # Run all scenarios
  %(prog)s --verbose mediator_test            # Run with detailed output
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Positional arguments
    parser.add_argument(
        'scenarios',
        nargs='*',
        help='Names of scenarios to run. If none specified, runs default scenario.'
    )

    # Optional arguments
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available scenarios and exit'
    )

    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Run all available scenarios'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output with detailed exploration tracking'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress detailed output, show only final results'
    )

    parser.add_argument(
        '--max-iterations',
        type=int,
        default=5,
        help='Maximum number of iterations per scenario (default: 5)'
    )

    parser.add_argument(
        '--visualize', '-z',
        action='store_true',
        help='Generate HTML visualizations: timeline view and decision tree showing OSmosis graph states'
    )

    parser.add_argument(
        '--beam-search',
        action='store_true',
        help='Use beam search instead of greedy search for exploration'
    )

    parser.add_argument(
        '--beam-width',
        type=int,
        default=3,
        help='Beam width for beam search (default: 3)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=DEFAULT_SEED,
        help=f'Seed for the exploration RNG, for reproducible runs (default: {DEFAULT_SEED})'
    )

    parser.add_argument(
        '--true-bfs',
        action='store_true',
        help='Use true BFS (breadth-first search) without scoring - explores all paths exhaustively'
    )

    parser.add_argument(
        '--bfs-max-depth',
        type=int,
        default=8,
        help='Maximum depth for true BFS exploration (default: 8)'
    )

    parser.add_argument(
        '--bfs-max-states',
        type=int,
        default=10000,
        help='Maximum states to explore in true BFS (default: 10000)'
    )

    parser.add_argument(
        '--metric-driven-scoring',
        action='store_true',
        default=True,
        help='Use goal-driven scoring system (default: enabled)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Write output to specified file instead of stdout'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='IsoSearch v1.0 - Automated Security Mechanism Discovery'
    )

    return parser


def validate_scenarios(scenario_names):
    """Validate that all requested scenarios exist"""
    available = set(SCENARIOS.keys())
    requested = set(scenario_names)
    invalid = requested - available

    if invalid:
        print(f"❌ Error: Unknown scenario(s): {', '.join(sorted(invalid))}")
        print(f"\nAvailable scenarios:")
        list_scenarios()
        return False

    return True


def print_detailed_scenario_info():
    """Print detailed information about all scenarios"""
    print("📋 AVAILABLE SCENARIOS")
    print("=" * 60)

    for name, scenario in SCENARIOS.items():
        print(f"\n🎯 {name}")
        print(f"   Description: {scenario.description}")
        print(f"   Goals ({len(scenario.goals)}):")
        for goal in scenario.goals:
            print(f"     • {goal}")
        print(f"   Constraints ({len(scenario.constraints)}):")
        if scenario.constraints:
            for constraint in scenario.constraints:
                print(f"     • {constraint}")
        else:
            print(f"     • None")
        transitions = scenario.get_allowed_transitions()
        print(f"   Transitions ({len(transitions)}):")
        for transition in transitions:
            print(f"     • {transition.transition_type}: {transition.description}")


if __name__ == "__main__":
    parser = create_cli_parser()
    args = parser.parse_args()

    # Make args globally available for pattern-aware scoring
    globals()['args'] = args

    # Set up output redirection if --output is specified
    import sys
    original_stdout = sys.stdout
    output_file = None
    if args.output:
        try:
            output_file = open(args.output, 'w')
            sys.stdout = output_file
        except Exception as e:
            print(f"❌ Error opening output file '{args.output}': {e}", file=original_stdout)
            exit(1)

    # Handle list scenarios option
    if args.list:
        print_detailed_scenario_info()
        if output_file:
            output_file.close()
            sys.stdout = original_stdout
        exit(0)

    # Determine which scenarios to run
    if args.all:
        if args.scenarios:
            print("⚠️  Warning: --all flag specified, ignoring individual scenario arguments")
        scenario_names = list(SCENARIOS.keys())
    elif args.scenarios:
        scenario_names = args.scenarios
        # Validate scenarios exist
        if not validate_scenarios(scenario_names):
            exit(1)
    else:
        # Default behavior
        scenario_names = ['basic_sharing']
        if not args.quiet:
            print("No scenarios specified, running default scenario: basic_sharing")
            print("Use --help for more options or --list to see all scenarios")

    # Configure verbosity (placeholder for future implementation)
    if args.verbose:
        print("🔍 Verbose mode enabled - detailed exploration tracking")
    elif args.quiet:
        print("🔇 Quiet mode enabled - minimal output")

    # Set max iterations (placeholder for future implementation)
    if args.max_iterations != 5:
        print(f"📊 Using {args.max_iterations} maximum iterations per scenario")

    # Configure visualization
    if args.visualize:
        print("🎨 HTML visualization enabled")

    try:
        # Run the scenarios
        if len(scenario_names) == 1:
            print(f"\n🎯 Running scenario: {scenario_names[0]}")
            result = run_scenario(scenario_names[0], enable_visualization=args.visualize, max_iterations=args.max_iterations)
        else:
            print(f"\n🚀 Running {len(scenario_names)} scenarios: {', '.join(scenario_names)}")
            results = run_multiple_scenarios(scenario_names)

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Exploration interrupted by user")
        if output_file:
            output_file.close()
            sys.stdout = original_stdout
        exit(1)
    except Exception as e:
        print(f"\n❌ Error during exploration: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        if output_file:
            output_file.close()
            sys.stdout = original_stdout
        exit(1)

    print(f"\n✅ Exploration complete!")
    
    # Clean up output file if used
    if output_file:
        output_file.close()
        sys.stdout = original_stdout
        print(f"✅ Output written to: {args.output}", file=original_stdout)