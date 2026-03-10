"""
test_scenarios.py — Integration tests per container type.
Each test uses the scenario_graph fixture (parametrized).

Run with: sudo python -m pytest tests/test_scenarios.py -v
Requires: Docker, Podman, Apptainer, Kata installed on Linux VM.
"""

import os
import sys
import pytest

PROC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROC_DIR)

from graph_queries import (
    shared_resources,
    shared_resource_spaces,
    can_control,
    controlled_by,
)


# ---------------------------------------------------------------------------
# Baseline: two plain processes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["processes"], indirect=True)
def test_processes_baseline(scenario_graph):
    G, pids = scenario_graph
    assert len(pids) == 2, "Expected exactly 2 PIDs from setup.sh"
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"

    # Same user → can signal each other
    assert kvs_pd in can_control(G, app_pd), "Same-uid processes should hold each other"
    assert app_pd in can_control(G, kvs_pd)

    # Shared file resources (they're in the same mount namespace / home dir)
    file_shared = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(file_shared) > 0, "Baseline processes should share file resources"

    # Same parent cgroup → shared PAGE_QUOTA space
    cg_shared = shared_resource_spaces(G, app_pd, kvs_pd, "PAGE_QUOTA")
    assert len(cg_shared) > 0, "Baseline processes should share cgroup resource space"


# ---------------------------------------------------------------------------
# Docker regular
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["docker-regular"], indirect=True)
def test_docker_regular_no_writable_file_sharing(scenario_graph):
    """Regular Docker containers should NOT share writable (ext4/overlay) file resources.
    Read-only image layers (squashfs) are excluded — they appear as shared MO resources."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    file_shared = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(file_shared) == 0, \
        f"Docker containers should not share writable FILE resources, but found: {file_shared}"

@pytest.mark.parametrize("scenario_graph", ["docker-regular"], indirect=True)
def test_docker_regular_shared_image_layers_as_mo(scenario_graph):
    """Containers using the same base image share read-only pages (MO/VMR resources)."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    mo_shared = shared_resources(G, app_pd, kvs_pd, "MO")
    assert len(mo_shared) > 0, \
        "Same-image Docker containers should share physical memory pages (base image layers)"


@pytest.mark.parametrize("scenario_graph", ["docker-regular"], indirect=True)
def test_docker_regular_daemon_in_kernel_hold(scenario_graph):
    """dockerd should be reachable under the kernel PD (kernel holds dockerd's ADS)."""
    G, _ = scenario_graph
    kernel_pd = next(
        (n for n, d in G.nodes(data=True) if "Linux" in d.get("data", "")), None
    )
    assert kernel_pd is not None, "Kernel PD not found"
    dockerd_pd = next(
        (n for n, d in G.nodes(data=True) if d.get("data") == "dockerd"), None
    )
    if dockerd_pd is None:
        pytest.skip("dockerd PD not found in graph (may be outside extracted PIDs)")
    assert dockerd_pd in can_control(G, kernel_pd), \
        "Kernel should hold dockerd (has same uid or root)"


# ---------------------------------------------------------------------------
# Docker rootless
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["docker-rootless"], indirect=True)
def test_docker_rootless_no_kernel_hold(scenario_graph):
    """Rootless Docker daemon should NOT be held by the kernel (different uid)."""
    G, _ = scenario_graph
    kernel_pd = next(
        (n for n, d in G.nodes(data=True) if "Linux" in d.get("data", "")), None
    )
    dockerd_pd = next(
        (n for n, d in G.nodes(data=True) if d.get("data") == "dockerd"), None
    )
    if kernel_pd is None or dockerd_pd is None:
        pytest.skip("kernel or dockerd PD not found")
    assert dockerd_pd not in can_control(G, kernel_pd), \
        "Rootless dockerd should not be held by kernel PD"


@pytest.mark.parametrize("scenario_graph", ["docker-rootless"], indirect=True)
def test_docker_rootless_slirp_shared(scenario_graph):
    """Rootless Docker: exactly one slirp4netns process serves all containers."""
    G, _ = scenario_graph
    slirp_pds = [
        n for n, d in G.nodes(data=True)
        if "slirp" in d.get("data", "").lower()
    ]
    # One shared slirp4netns for rootless Docker (vs. one per container in Podman)
    assert len(slirp_pds) <= 1, \
        f"Expected at most 1 slirp4netns PD in rootless Docker, found {len(slirp_pds)}"


# ---------------------------------------------------------------------------
# Podman
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["podman"], indirect=True)
def test_podman_no_writable_file_sharing(scenario_graph):
    """Podman containers should NOT share writable file resources by default."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    file_shared = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(file_shared) == 0, \
        f"Podman containers should not share writable FILE resources, found: {file_shared}"


# ---------------------------------------------------------------------------
# Apptainer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["apptainer"], indirect=True)
def test_apptainer_silently_shares_home(scenario_graph):
    """Apptainer mounts the host home dir by default → processes share FILE resources."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    file_shared = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(file_shared) > 0, \
        "Apptainer should share home-dir file resources (default bind mount)"


@pytest.mark.parametrize("scenario_graph", ["apptainer"], indirect=True)
def test_apptainer_cgroup_shared(scenario_graph):
    """Apptainer instances share the same cgroup (no isolation by default)."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    cg_shared = shared_resource_spaces(G, app_pd, kvs_pd, "PAGE_QUOTA")
    assert len(cg_shared) > 0, \
        "Apptainer instances should share cgroup (PAGE_QUOTA) resource space"


# ---------------------------------------------------------------------------
# Kata Containers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["kata"], indirect=True)
def test_kata_no_file_sharing(scenario_graph):
    """Kata containers each have a separate VM → no shared file resources."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    file_shared = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(file_shared) == 0, \
        f"Kata containers should not share file resources, found: {file_shared}"
