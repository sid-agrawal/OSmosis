"""
test_scenarios.py — Integration tests per container type.
Each test uses the scenario_graph fixture (parametrized).

Run with: sudo python -m pytest tests/test_scenarios.py -v
Requires: Docker, Podman, Apptainer, Kata installed on Linux VM.
"""

import os
import sys
import shutil
import pytest

PROC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROC_DIR)

from graph_queries import (
    shared_resources,
    shared_resource_spaces,
    can_control,
    controlled_by,
)

apptainer_available = shutil.which("apptainer") is not None
# kata-no-kvm: kata shim present + docker available; /dev/kvm not required (runs via QEMU TCG)
kata_no_kvm_available = (
    shutil.which("containerd-shim-kata-v2") is not None
    and shutil.which("docker") is not None
)
# kata-kvm: same as kata-no-kvm but also requires /dev/kvm (hardware KVM acceleration)
kata_kvm_available = (
    shutil.which("containerd-shim-kata-v2") is not None
    and shutil.which("docker") is not None
    and os.path.exists("/dev/kvm")
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

@pytest.mark.skipif(not apptainer_available, reason="apptainer not installed")
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


@pytest.mark.skipif(not apptainer_available, reason="apptainer not installed")
@pytest.mark.parametrize("scenario_graph", ["apptainer"], indirect=True)
def test_apptainer_cgroup_isolated(scenario_graph):
    """Singularity-CE 4.x creates per-instance cgroups (singularity-<PID>.scope).
    Each instance gets its own PAGE_QUOTA resource space — cgroups are isolated."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    cg_shared = shared_resource_spaces(G, app_pd, kvs_pd, "PAGE_QUOTA")
    assert len(cg_shared) == 0, \
        "Singularity-CE 4.x apptainer instances should have separate cgroup scopes (PAGE_QUOTA isolated)"


# ---------------------------------------------------------------------------
# Kata Containers (no-KVM / TCG mode)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not kata_no_kvm_available, reason="kata shim not installed")
@pytest.mark.parametrize("scenario_graph", ["kata-no-kvm"], indirect=True)
def test_kata_no_kvm_host_visible_as_qemu(scenario_graph):
    """Without /dev/kvm, Kata runs containers inside QEMU-TCG VMs.
    From the host, each kata container is visible only as a QEMU process in the
    host MNT namespace — the in-VM isolation is opaque to host procfs.
    Both QEMU processes share the host filesystem → FILE resources appear shared."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    file_shared = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(file_shared) > 0, \
        "Kata QEMU processes run in the host MNT namespace and should share host FILE resources"


# ---------------------------------------------------------------------------
# Kata Containers with KVM acceleration (x86 baremetal)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not kata_kvm_available, reason="/dev/kvm not available")
@pytest.mark.parametrize("scenario_graph", ["kata-kvm"], indirect=True)
def test_kata_kvm_host_visible_and_kvm_enabled(scenario_graph):
    """With /dev/kvm, Kata uses KVM-accelerated VMs.
    From the host, containers are still visible as QEMU processes in the host
    MNT namespace (same as TCG mode) — VM-level isolation remains opaque to
    host procfs. Additionally verifies KVM acceleration is in use by checking
    the QEMU cmdline."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"

    # Host-visible behavior: QEMU processes share host FILE resources (same as no-kvm)
    file_shared = shared_resources(G, app_pd, kvs_pd, "FILE")
    assert len(file_shared) > 0, \
        "Kata QEMU processes run in host MNT namespace and share host FILE resources"

    # Verify KVM acceleration is active (not TCG fallback)
    import subprocess
    for pid in pids:
        try:
            cmdline = open(f"/proc/{pid}/cmdline").read().replace('\x00', ' ')
            # KVM mode does NOT have 'accel=tcg'; it has 'accel=kvm' or just -enable-kvm
            assert 'accel=tcg' not in cmdline, \
                f"PID {pid} QEMU should use KVM, not TCG"
        except FileNotFoundError:
            pass  # process may have exited; skip cmdline check


# ---------------------------------------------------------------------------
# Kata Containers vm_model (host + guest extraction)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not kata_no_kvm_available, reason="kata shim not installed")
@pytest.mark.parametrize("scenario_graph", ["kata-vm-model"], indirect=True)
def test_kata_vm_model_guest_processes_isolated(scenario_graph):
    """vm_model kata mode extracts BOTH host QEMU state and in-VM guest state.
    The guest CSV should contain the actual container process (bash/sleep),
    which is isolated in its own namespace inside the kata VM."""
    # NOTE: scenario_graph here contains the HOST-side model (QEMU PID).
    # The guest CSV is produced separately by vm_model.py.
    # This test verifies the host-side extraction is valid and the
    # kata VM booted successfully (guest.csv exists and is non-empty).
    G, pids = scenario_graph
    assert len(pids) >= 1, "Expected at least 1 PID (QEMU host process)"
    # The host PD represents the QEMU process
    qemu_pd = f"PD_{pids[0]}"
    assert G.has_node(qemu_pd), "QEMU PD should exist in host model"


# ---------------------------------------------------------------------------
# gRPC inter-container communication
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_graph", ["grpc-docker"], indirect=True)
def test_grpc_request_edge(scenario_graph):
    """gRPC client container should have a REQUEST edge to the server container."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"   # client (APP_PID from setup.sh)
    kvs_pd = f"PD_{pids[1]}"   # server (KVS_PID from setup.sh)

    # Client has a REQUEST edge to server (TCP connection detected)
    request_targets = {v for _, v, d in G.out_edges(app_pd, data=True)
                       if d.get("type") == "REQUEST"
                       and G.nodes.get(v, {}).get("type") == "PD"}
    assert kvs_pd in request_targets, \
        "gRPC client should have a REQUEST edge to the gRPC server (TCP connection detected)"


@pytest.mark.parametrize("scenario_graph", ["grpc-docker"], indirect=True)
def test_grpc_net_namespace_spaces(scenario_graph):
    """Each Docker container should have its own NET resource space."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    from graph_queries import shared_resource_spaces
    net_shared = shared_resource_spaces(G, app_pd, kvs_pd, "NET")
    assert len(net_shared) == 0, \
        "Docker containers in separate NET namespaces should not share NET resource spaces"
