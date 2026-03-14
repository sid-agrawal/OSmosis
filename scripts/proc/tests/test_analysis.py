"""
test_analysis.py — Discovery / insight tests comparing container runtimes.
These tests confirm novel findings described in the paper.

Run with: sudo python -m pytest tests/test_analysis.py -v
Requires: Docker (regular + rootless), Podman, Apptainer installed.
"""

import os
import sys
import shutil
import pytest

PROC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROC_DIR)

apptainer_available = shutil.which("apptainer") is not None

from graph_queries import (
    get_pds,
    shared_resources,
    shared_resource_spaces,
    can_control,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_pd(G, name_substr):
    return next(
        (n for n, d in G.nodes(data=True) if name_substr in d.get("data", "")),
        None,
    )


def _scenario_pds(G, pids):
    """Return (app_pd, kvs_pd) string IDs from PID list."""
    return f"PD_{pids[0]}", f"PD_{pids[1]}"


# ---------------------------------------------------------------------------
# vdso shared between static binaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["processes"], indirect=True)
def test_shared_physical_pages(scenario_graph):
    """
    Two hello processes (dynamically linked) share physical memory objects (MOs)
    corresponding to libc, vdso, and other kernel-mapped pages. VMR nodes are
    per-address-space and are never shared between processes in the model; sharing
    is captured at the MO (physical page) level.
    """
    G, pids = scenario_graph
    app_pd, kvs_pd = _scenario_pds(G, pids)
    # Shared at MO level (physical pages)
    shared_mo = shared_resources(G, app_pd, kvs_pd, "MO")
    # Shared FILE resources (same filesystem mount)
    shared_file = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(shared_mo) > 0 or len(shared_file) > 0, \
        "Expected two hello processes to share MO (physical pages) or FILE resources"


# ---------------------------------------------------------------------------
# Apptainer silently shares home vs Docker doesn't
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not apptainer_available, reason="apptainer not installed")
@pytest.mark.parametrize("scenario_graph", ["apptainer"], indirect=True)
def test_apptainer_silently_shares_home(scenario_graph):
    """Apptainer's default home-dir bind mount creates unexpected file sharing."""
    G, pids = scenario_graph
    app_pd, kvs_pd = _scenario_pds(G, pids)
    shared_files = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(shared_files) > 0, \
        "Apptainer should silently share home directory as FILE resource"


@pytest.mark.parametrize("scenario_graph", ["docker-regular"], indirect=True)
def test_docker_shared_resources_empty_by_default(scenario_graph):
    """Regular Docker provides stronger isolation: no shared FILE resources."""
    G, pids = scenario_graph
    app_pd, kvs_pd = _scenario_pds(G, pids)
    assert len(shared_resources(G, app_pd, kvs_pd, "FILE")) == 0, \
        "Docker containers should not share FILE resources by default"


# ---------------------------------------------------------------------------
# Per-container slirp (Podman) vs shared slirp (rootless Docker)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["podman"], indirect=True)
def test_podman_containers_modeled(scenario_graph):
    """
    Podman containers should appear as PD nodes in the model.
    The network isolation mechanism depends on whether podman is rootful or rootless:
    - Rootless: each container gets its own slirp4netns/pasta process
    - Rootful: kernel networking, no per-container network daemon
    This test verifies that both container PDs are present in the model.
    """
    G, pids = scenario_graph
    pd_names = [d.get("data", "") for _, d in G.nodes(data=True) if d.get("type") == "PD"]
    # Both container processes should be modeled
    assert len(pids) >= 2, f"Expected at least 2 container PIDs, got {pids}"
    for pid in pids:
        assert f"PD_{pid}" in G.nodes, f"Container PID {pid} not found as PD in model"


@pytest.mark.parametrize("scenario_graph", ["docker-rootless"], indirect=True)
def test_docker_rootless_shared_slirp(scenario_graph):
    """
    Rootless Docker: all containers share a single slirp4netns / RootlessKit process.
    """
    G, _ = scenario_graph
    slirp_pds = [
        n for n, d in G.nodes(data=True)
        if "slirp" in d.get("data", "").lower()
        or "rootlesskit" in d.get("data", "").lower()
    ]
    assert len(slirp_pds) == 1, \
        f"Rootless Docker should have exactly 1 network provider PD, found {len(slirp_pds)}"


# ---------------------------------------------------------------------------
# Cgroup isolation: Singularity-CE 4.x creates per-instance cgroups
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not apptainer_available, reason="apptainer not installed")
@pytest.mark.parametrize("scenario_graph", ["apptainer"], indirect=True)
def test_apptainer_cgroup_isolated(scenario_graph):
    """Singularity-CE 4.x creates per-instance cgroups (singularity-<PID>.scope).
    Each instance gets its own PAGE_QUOTA resource space — PAGE_QUOTA is isolated,
    unlike the FILE resource (home dir) which is still shared."""
    G, pids = scenario_graph
    app_pd, kvs_pd = _scenario_pds(G, pids)
    assert len(shared_resource_spaces(G, app_pd, kvs_pd, "PAGE_QUOTA")) == 0, \
        "Singularity-CE 4.x apptainer instances should have separate per-instance cgroup scopes"


@pytest.mark.parametrize("scenario_graph", ["docker-regular"], indirect=True)
def test_docker_cgroup_not_shared(scenario_graph):
    """Docker assigns each container its own cgroup → no shared PAGE_QUOTA space."""
    G, pids = scenario_graph
    app_pd, kvs_pd = _scenario_pds(G, pids)
    assert len(shared_resource_spaces(G, app_pd, kvs_pd, "PAGE_QUOTA")) == 0, \
        "Docker containers should not share cgroup (PAGE_QUOTA) resource spaces"
