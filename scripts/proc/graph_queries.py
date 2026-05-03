"""
graph_queries.py — Pure-Python query functions over a nx.MultiDiGraph model graph.

The graph is produced by ModelGraph.to_csv() + metrics.read_csv_to_graph(), or
directly from ModelGraph.g. Node attributes: type (PD/RESOURCE/RESOURCE_SPACE),
data (resource/space type name or PD name), extra. Edge attributes: type
(HOLD/MAP/SUBSET/REQUEST), data (permissions or resource-space ID string).
"""

import json
import networkx as nx
from collections import deque


# ---------------------------------------------------------------------------
# Basic selectors
# ---------------------------------------------------------------------------

def get_pds(G: nx.MultiDiGraph) -> list[str]:
    """Return all PD node IDs (string form, e.g. 'PD_1')."""
    return [n for n, d in G.nodes(data=True) if d.get("type") == "PD"]


def get_resources(G: nx.MultiDiGraph, res_type: str | None = None) -> list[str]:
    """Return all RESOURCE node IDs, optionally filtered by data field (e.g. 'FILE')."""
    return [
        n for n, d in G.nodes(data=True)
        if d.get("type") == "RESOURCE"
        and (res_type is None or d.get("data") == res_type)
    ]


def get_resource_spaces(G: nx.MultiDiGraph, res_type: str | None = None) -> list[str]:
    """Return all RESOURCE_SPACE node IDs, optionally filtered by data field."""
    return [
        n for n, d in G.nodes(data=True)
        if d.get("type") == "RESOURCE_SPACE"
        and (res_type is None or d.get("data") == res_type)
    ]


# ---------------------------------------------------------------------------
# Reachability helpers (internal)
# ---------------------------------------------------------------------------

def _reachable_resources(G: nx.MultiDiGraph, pd: str,
                          res_type: str | None = None,
                          access_mode: str | None = None) -> set[str]:
    """
    BFS from pd following HOLD and MAP edges.
    Returns the set of RESOURCE nodes reachable.
    Optionally filter by:
      res_type    — only nodes whose data == res_type
      access_mode — only HOLD edges whose data field contains access_mode letter
    """
    visited = set()
    queue = deque([pd])

    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)

        for _, dst, edata in G.out_edges(node, data=True):
            etype = edata.get("type")
            if etype == "HOLD":
                # Do NOT follow inter-PD HOLD edges (those represent signal-sending
                # capability, not resource access — handled by can_control()).
                if G.nodes[dst].get("type") == "PD":
                    continue
                # If access_mode filter, check the permissions string on the edge
                if access_mode is not None:
                    perm_str = edata.get("data", "")
                    if access_mode not in perm_str:
                        continue
                if dst not in visited:
                    queue.append(dst)
            elif etype == "MAP":
                if dst not in visited:
                    queue.append(dst)

    # Collect RESOURCE nodes (not the starting PD itself)
    result = set()
    for node in visited:
        if node == pd:
            continue
        ndata = G.nodes[node]
        if ndata.get("type") == "RESOURCE":
            if res_type is None or ndata.get("data") == res_type:
                result.add(node)
    return result


def _reachable_spaces(G: nx.MultiDiGraph, pd: str,
                       res_type: str | None = None) -> set[str]:
    """
    BFS from pd following HOLD edges only (not inter-PD HOLD edges).
    Returns the set of RESOURCE_SPACE nodes reachable.
    """
    visited = set()
    queue = deque([pd])

    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)

        for _, dst, edata in G.out_edges(node, data=True):
            if edata.get("type") == "HOLD" and dst not in visited:
                # Do NOT follow inter-PD HOLD edges
                if G.nodes[dst].get("type") == "PD":
                    continue
                queue.append(dst)

    result = set()
    for node in visited:
        if node == pd:
            continue
        ndata = G.nodes[node]
        if ndata.get("type") == "RESOURCE_SPACE":
            if res_type is None or ndata.get("data") == res_type:
                result.add(node)
    return result


# ---------------------------------------------------------------------------
# Core query functions
# ---------------------------------------------------------------------------

def shared_resources(G: nx.MultiDiGraph, pd1: str, pd2: str,
                     res_type: str | None = None,
                     access_mode: str | None = None) -> set[str]:
    """
    Resources reachable from both pd1 and pd2 via HOLD/MAP edges.
    Optionally filter by res_type (e.g. 'FILE', 'MO') and
    access_mode (single character in permissions string, e.g. 'W').
    """
    r1 = _reachable_resources(G, pd1, res_type, access_mode)
    r2 = _reachable_resources(G, pd2, res_type, access_mode)
    return r1 & r2


def shared_resource_spaces(G: nx.MultiDiGraph, pd1: str, pd2: str,
                            res_type: str | None = None) -> set[str]:
    """Resource spaces reachable from both pd1 and pd2 via HOLD edges."""
    s1 = _reachable_spaces(G, pd1, res_type)
    s2 = _reachable_spaces(G, pd2, res_type)
    return s1 & s2


def can_control(G: nx.MultiDiGraph, pd: str) -> set[str]:
    """PDs that pd has a direct HOLD edge to (can signal/terminate)."""
    result = set()
    for _, dst, edata in G.out_edges(pd, data=True):
        if edata.get("type") == "HOLD" and G.nodes[dst].get("type") == "PD":
            result.add(dst)
    return result


def controlled_by(G: nx.MultiDiGraph, pd: str) -> set[str]:
    """PDs that have a direct HOLD edge to pd (can signal/terminate pd)."""
    result = set()
    for src, _, edata in G.in_edges(pd, data=True):
        if edata.get("type") == "HOLD" and G.nodes[src].get("type") == "PD":
            result.add(src)
    return result


def common_ancestors(G: nx.MultiDiGraph, pd1: str, pd2: str) -> set[str]:
    """PDs reachable from both pd1 and pd2 via REQUEST edges (common dependency providers)."""

    def _request_reachable(start: str) -> set[str]:
        visited = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            for _, dst, edata in G.out_edges(node, data=True):
                if edata.get("type") == "REQUEST" and dst not in visited:
                    queue.append(dst)
        visited.discard(start)
        return visited

    return _request_reachable(pd1) & _request_reachable(pd2)


def tcb(G: nx.MultiDiGraph, pd: str) -> dict:
    """
    Compute the Trusted Computing Base for pd.
    Returns a dict keyed by CIA concern:
      'integrity'    — PDs that can modify pd (controlled_by + shared write resources)
      'availability' — PDs sharing resource spaces (quota exhaustion)
      'ancestors'    — common dependency providers (common_ancestors with every other PD)
    """
    result = {
        "integrity": controlled_by(G, pd),
        "shared_resources": set(),
        "availability": set(),
        "ancestors": set(),
    }
    for other in get_pds(G):
        if other == pd:
            continue
        result["shared_resources"] |= shared_resources(G, pd, other)
        result["availability"] |= shared_resource_spaces(G, pd, other)
        result["ancestors"] |= common_ancestors(G, pd, other)
    return result


def impact_boundary(G: nx.MultiDiGraph, pd: str) -> dict:
    """
    Compute the Impact Boundary for pd.
    Returns a dict keyed by concern:
      'control'      — PDs pd can terminate (can_control)
      'shared_write' — resources pd can write that others also hold
      'quota_share'  — resource spaces pd shares with others
    """
    ctrl = can_control(G, pd)
    write_shared = set()
    quota_shared = set()
    for other in get_pds(G):
        if other == pd:
            continue
        write_shared |= shared_resources(G, pd, other, access_mode="W")
        quota_shared |= shared_resource_spaces(G, pd, other, res_type="PAGE_QUOTA")
    return {
        "control": ctrl,
        "shared_write_resources": write_shared,
        "quota_share": quota_shared,
    }


# ---------------------------------------------------------------------------
# MAC profile and syscall surface queries
# ---------------------------------------------------------------------------

def _pd_extra(G: nx.MultiDiGraph, pd: str) -> dict:
    """Parse and return the 'extra' JSON dict for a PD node, or {}."""
    raw = G.nodes.get(pd, {}).get("extra", "")
    if not raw or raw != raw:  # handles NaN from CSV load
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def syscall_surface(G: nx.MultiDiGraph, pd: str) -> set:
    """Return the set of docker-security-critical syscalls this PD is allowed to invoke.

    Reads 'allowed_syscalls' from the PD node's extra JSON field (persists through
    CSV round-trip). Values set by procfs_data.__add_processes():
    - Full set (no seccomp): process can invoke all tracked syscalls.
    - Empty set (docker-default seccomp): all tracked syscalls are blocked.
    Returns an empty set if the attribute is absent or unparseable.
    """
    extra = _pd_extra(G, pd)
    allowed = extra.get("allowed_syscalls", None)
    if allowed is None:
        return set()
    if isinstance(allowed, list):
        return set(allowed)
    try:
        return set(json.loads(allowed))
    except Exception:
        return set()


def mac_peers(G: nx.MultiDiGraph, pd: str) -> set:
    """Return PDs that share the same MAC (AppArmor/SELinux) label as pd.

    Reads 'lsm_label' from each PD node's extra JSON field.
    """
    label = _pd_extra(G, pd).get("lsm_label", None)
    if not label:
        return set()
    return {
        n for n, d in G.nodes(data=True)
        if d.get("type") == "PD"
        and n != pd
        and _pd_extra(G, n).get("lsm_label", "") == label
    }


def _different_mac_profile(G: nx.MultiDiGraph, pd1: str, pd2: str) -> bool:
    """True if pd1 and pd2 have different MAC (AppArmor/SELinux) labels."""
    label1 = _pd_extra(G, pd1).get("lsm_label", "")
    label2 = _pd_extra(G, pd2).get("lsm_label", "")
    return label1 != label2


def _different_syscall_surface(G: nx.MultiDiGraph, pd1: str, pd2: str) -> bool:
    """True if pd1 and pd2 have different effective syscall surfaces."""
    return syscall_surface(G, pd1) != syscall_surface(G, pd2)


# Known hypervisor process name substrings (case-insensitive).
_HYPERVISOR_NAMES = ("qemu", "kvmtool", "firecracker", "cloud-hypervisor", "runsc")


def _is_hypervisor(G: nx.MultiDiGraph, pd: str) -> bool:
    """True if pd is a hypervisor process (inferred from process name).

    Detects QEMU, Firecracker, kvmtool, and cloud-hypervisor by name.
    Can be extended to check for KVM device HOLD edges in the graph.
    """
    name = G.nodes.get(pd, {}).get("data", "").lower()
    return any(h in name for h in _HYPERVISOR_NAMES)


def isolation_layers(G: nx.MultiDiGraph, pd1: str, pd2: str) -> dict:
    """Count how many isolation mechanisms separate pd1 from pd2.

    Returns a dict of booleans; True means the two PDs are isolated along
    that dimension (no shared resource space / different profile / etc.).

    Keys:
      different_mnt_ns          — separate mount namespaces
      different_ipc_ns          — separate IPC namespaces
      different_net_ns          — separate network namespaces
      different_cgroup          — separate cgroup hierarchies
      different_mac_profile     — different AppArmor/SELinux label
      different_syscall_surface — different effective syscall surfaces
      vm_boundary               — at least one PD is a hypervisor process,
                                  indicating a VM isolation boundary
    """
    return {
        "different_mnt_ns":
            not bool(shared_resource_spaces(G, pd1, pd2, res_type="MNT")),
        "different_ipc_ns":
            not bool(shared_resource_spaces(G, pd1, pd2, res_type="IPC")),
        "different_net_ns":
            not bool(shared_resource_spaces(G, pd1, pd2, res_type="NET")),
        "different_cgroup":
            not bool(shared_resource_spaces(G, pd1, pd2, res_type="PAGE_QUOTA")),
        "different_mac_profile":
            _different_mac_profile(G, pd1, pd2),
        "different_syscall_surface":
            _different_syscall_surface(G, pd1, pd2),
        "vm_boundary":
            _is_hypervisor(G, pd1) or _is_hypervisor(G, pd2),
    }
