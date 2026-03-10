"""
test_graph_queries.py — Unit tests for graph_queries.py.

Most tests build small hand-crafted nx.MultiDiGraph instances.
Tests that use live processes are marked with pytest.mark.live.
"""

import os
import sys
import pytest
import networkx as nx

PROC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROC_DIR)

from graph_queries import (
    get_pds,
    shared_resources,
    shared_resource_spaces,
    can_control,
    controlled_by,
    common_ancestors,
    tcb,
    impact_boundary,
)


# ---------------------------------------------------------------------------
# Graph builder helpers
# ---------------------------------------------------------------------------

def _pd(G, name):
    G.add_node(name, type="PD", data=name, extra="")
    return name

def _space(G, name, res_type):
    G.add_node(name, type="RESOURCE_SPACE", data=res_type, extra="")
    return name

def _res(G, name, res_type, space):
    G.add_node(name, type="RESOURCE", data=res_type, extra="")
    G.add_edge(name, space, type="SUBSET", data="")
    return name

def _hold(G, src, dst, perms="RWX"):
    G.add_edge(src, dst, type="HOLD", data=perms)

def _map(G, src, dst):
    G.add_edge(src, dst, type="MAP", data="")

def _request(G, src, dst, data=""):
    G.add_edge(src, dst, type="REQUEST", data=data)


# ---------------------------------------------------------------------------
# shared_resources tests
# ---------------------------------------------------------------------------

def test_shared_resources_finds_mo():
    """pd1 -HOLD-> vmr1 -MAP-> mo1 <-MAP- vmr2 <-HOLD- pd2: shared MO is detected."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    sp_vmr = _space(G, "VMR_SPACE_1", "VMR"); sp_mo = _space(G, "MO_SPACE_1", "MO")
    vmr1 = _res(G, "VMR_1_1_1", "VMR", sp_vmr); vmr2 = _res(G, "VMR_1_1_2", "VMR", sp_vmr)
    mo1  = _res(G, "MO_1_1_1",  "MO",  sp_mo)
    _hold(G, pd1, vmr1); _map(G, vmr1, mo1)
    _hold(G, pd2, vmr2); _map(G, vmr2, mo1)

    result = shared_resources(G, pd1, pd2, "MO")
    assert mo1 in result, f"Expected {mo1} in shared MO resources, got {result}"


def test_shared_resources_empty_when_no_sharing():
    """Two PDs with disjoint MOs share nothing."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    sp_mo = _space(G, "MO_SPACE_1", "MO")
    mo1 = _res(G, "MO_1_1_1", "MO", sp_mo)
    mo2 = _res(G, "MO_1_1_2", "MO", sp_mo)
    _hold(G, pd1, mo1)
    _hold(G, pd2, mo2)

    result = shared_resources(G, pd1, pd2)
    assert len(result) == 0, f"Expected empty shared resources, got {result}"


def test_shared_resources_permission_filter():
    """Permission filter: only edges whose data contains the access_mode letter."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    sp_vmr = _space(G, "VMR_SPACE_1", "VMR")
    vmr1 = _res(G, "VMR_1_1_1", "VMR", sp_vmr)

    # pd1: read+write, pd2: read-only
    _hold(G, pd1, vmr1, "RW")
    _hold(G, pd2, vmr1, "R")

    # Both hold vmr1, so it is shared regardless of filter
    assert vmr1 in shared_resources(G, pd1, pd2)
    # With 'W' filter, only edges containing 'W' are followed — pd2 has only 'R'
    assert vmr1 not in shared_resources(G, pd1, pd2, access_mode="W"), \
        "vmr1 should not appear when filtering for W on pd2's R-only edge"
    # With 'X' filter, neither holds vmr1 via X
    assert vmr1 not in shared_resources(G, pd1, pd2, access_mode="X")


def test_shared_resources_no_type_filter():
    """Without res_type filter, all resource types are returned."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    sp_file = _space(G, "FILE_SPACE_1", "FILE")
    f1 = _res(G, "FILE_1_1_1", "FILE", sp_file)
    _hold(G, pd1, f1); _hold(G, pd2, f1)

    assert f1 in shared_resources(G, pd1, pd2)
    assert f1 in shared_resources(G, pd1, pd2, "FILE")
    assert f1 not in shared_resources(G, pd1, pd2, "MO")


# ---------------------------------------------------------------------------
# can_control / controlled_by tests
# ---------------------------------------------------------------------------

def test_can_control_direct_hold():
    """pd1 -HOLD-> pd2: can_control(pd1) == {pd2}."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    _hold(G, pd1, pd2)

    assert can_control(G, pd1) == {pd2}
    assert can_control(G, pd2) == set()


def test_controlled_by():
    """Multiple PDs holding pd2 all appear in controlled_by(pd2)."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2"); pd_root = _pd(G, "PD_root")
    _hold(G, pd1, pd2)
    _hold(G, pd_root, pd2)

    assert controlled_by(G, pd2) == {pd1, pd_root}
    assert controlled_by(G, pd1) == set()


def test_can_control_not_transitive():
    """can_control is not transitive — only direct HOLD edges count."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2"); pd3 = _pd(G, "PD_3")
    _hold(G, pd1, pd2)
    _hold(G, pd2, pd3)

    assert can_control(G, pd1) == {pd2}
    assert pd3 not in can_control(G, pd1)


# ---------------------------------------------------------------------------
# common_ancestors tests
# ---------------------------------------------------------------------------

def test_common_ancestors_kernel():
    """Two PDs both requesting from a kernel PD: common_ancestors returns that PD."""
    G = nx.MultiDiGraph()
    kernel = _pd(G, "PD_kernel")
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    _request(G, pd1, kernel)
    _request(G, pd2, kernel)

    ancestors = common_ancestors(G, pd1, pd2)
    assert kernel in ancestors


def test_common_ancestors_empty():
    """No common ancestors when PDs request from different providers."""
    G = nx.MultiDiGraph()
    kernel1 = _pd(G, "PD_k1"); kernel2 = _pd(G, "PD_k2")
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    _request(G, pd1, kernel1)
    _request(G, pd2, kernel2)

    assert len(common_ancestors(G, pd1, pd2)) == 0


# ---------------------------------------------------------------------------
# shared_resource_spaces tests
# ---------------------------------------------------------------------------

def test_shared_resource_spaces_cgroup():
    """Two PDs holding the same PAGE_QUOTA space appear in shared_resource_spaces."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    cg_space = _space(G, "PAGE_QUOTA_SPACE_99", "PAGE_QUOTA")
    _hold(G, pd1, cg_space)
    _hold(G, pd2, cg_space)

    result = shared_resource_spaces(G, pd1, pd2, "PAGE_QUOTA")
    assert cg_space in result


def test_shared_resource_spaces_different_types():
    """Type filter works: VMR space shared but PAGE_QUOTA filter returns empty."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    vmr_space = _space(G, "VMR_SPACE_1", "VMR")
    _hold(G, pd1, vmr_space)
    _hold(G, pd2, vmr_space)

    assert vmr_space in shared_resource_spaces(G, pd1, pd2, "VMR")
    assert len(shared_resource_spaces(G, pd1, pd2, "PAGE_QUOTA")) == 0


# ---------------------------------------------------------------------------
# get_pds helper
# ---------------------------------------------------------------------------

def test_get_pds():
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    _space(G, "VMR_SPACE_1", "VMR")  # Not a PD

    assert set(get_pds(G)) == {pd1, pd2}


# ---------------------------------------------------------------------------
# TCB / IB smoke tests on hand-crafted graph
# ---------------------------------------------------------------------------

def test_tcb_contains_holder():
    """TCB integrity field includes PDs that hold pd."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    _hold(G, pd1, pd2)

    result = tcb(G, pd2)
    assert pd1 in result["integrity"]


def test_impact_boundary_control():
    """IB control field includes PDs that pd holds."""
    G = nx.MultiDiGraph()
    pd1 = _pd(G, "PD_1"); pd2 = _pd(G, "PD_2")
    _hold(G, pd1, pd2)

    result = impact_boundary(G, pd1)
    assert pd2 in result["control"]


# ---------------------------------------------------------------------------
# Live-process tests (require pypfs + root)
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_shared_resources_vdso(loaded_graph_static):
    """vdso VMR appears as shared resource between two static processes."""
    G = loaded_graph_static
    pds = get_pds(G)
    assert len(pds) >= 2, "Need at least 2 PDs"
    shared = shared_resources(G, pds[0], pds[1], "VMR")
    vdso_shared = [
        r for r in shared
        if "VDSO" in str(G.nodes[r].get("extra", ""))
    ]
    assert len(vdso_shared) > 0, "vdso VMR not found in shared resources between static procs"
