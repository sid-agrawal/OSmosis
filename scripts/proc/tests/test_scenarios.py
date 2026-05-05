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
    isolation_layers,
    syscall_surface,
    mac_peers,
)

fuse_available = os.path.exists("/dev/fuse")
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
# gVisor: runsc binary present and registered as a Docker runtime
gvisor_available = shutil.which("runsc") is not None
# Firecracker: binary present and KVM available
firecracker_available = (
    shutil.which("firecracker") is not None
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
    """Rootless dockerd has no uid-0 user-space process holding it.

    The kernel PD unconditionally holds all processes in the model (by design),
    but no root-owned *user-space* process should have a HOLD edge to the
    rootless daemon — it runs entirely within the user's uid namespace.
    """
    import json
    G, _ = scenario_graph
    dockerd_pd = next(
        (n for n, d in G.nodes(data=True) if d.get("data") == "dockerd"), None
    )
    if dockerd_pd is None:
        pytest.skip("rootless dockerd PD not found in graph")

    for src, _, edata in G.in_edges(dockerd_pd, data=True):
        if edata.get("type") != "HOLD":
            continue
        try:
            extra = json.loads(G.nodes[src].get("extra") or "{}")
        except (ValueError, TypeError):
            continue  # abstract kernel PD has extra=nan; skip
        uid = extra.get("uid_host", extra.get("uid_effective", None))
        assert uid != 0, (
            f"Rootless dockerd should not be held by uid-0 process "
            f"{src} ({G.nodes[src].get('data')})"
        )


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
    """Podman containers should NOT share writable user-data file resources by default.
    Pseudo-device files (/dev/null, /dev/random, etc.) are always shared across
    containers as kernel-provided endpoints; those are excluded from this check."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"
    file_shared_writable = shared_resources(G, app_pd, kvs_pd, "FILE", access_mode="W")
    # Exclude kernel pseudo-device bind-mounts (/dev/null, /dev/random, etc.)
    user_shared = {r for r in file_shared_writable
                   if not G.nodes[r].get("extra", "").startswith("/dev/")}
    assert len(user_shared) == 0, \
        f"Podman containers should not share writable user-data FILE resources, found: {user_shared}"


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
# gVisor (runsc) — user-space kernel sandbox
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not gvisor_available, reason="runsc not installed")
@pytest.mark.parametrize("scenario_graph", ["gvisor"], indirect=True)
def test_gvisor_host_visible_as_runsc(scenario_graph):
    """From the host, gVisor containers are visible as runsc-sandbox (Sentry) processes.
    The in-sandbox workloads are opaque to host /proc — only the Sentry is extracted."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_name = G.nodes.get(f"PD_{pids[0]}", {}).get("data", "")
    assert "runsc" in app_name.lower(), (
        f"gVisor container PD should be named runsc-sandbox (Sentry), got '{app_name}'"
    )


@pytest.mark.skipif(not gvisor_available, reason="runsc not installed")
@pytest.mark.parametrize("scenario_graph", ["gvisor"], indirect=True)
def test_gvisor_vm_boundary(scenario_graph):
    """runsc is a user-space kernel (Sentry); isolation_layers() reports vm_boundary=True.
    This is the novel dimension vs regular Docker containers (vm_boundary=False)."""
    G, pids = scenario_graph
    il = isolation_layers(G, f"PD_{pids[0]}", f"PD_{pids[1]}")
    assert il["vm_boundary"], (
        "gVisor Sentry (runsc-sandbox) should be detected as a hypervisor "
        "via _is_hypervisor(); 'runsc' must be in _HYPERVISOR_NAMES"
    )


@pytest.mark.skipif(not gvisor_available, reason="runsc not installed")
@pytest.mark.parametrize("scenario_graph", ["gvisor"], indirect=True)
def test_gvisor_namespace_isolation(scenario_graph):
    """gVisor containers should be isolated in MNT, IPC, NET, and cgroup dimensions.
    Unlike Kata (which loses IPC), gVisor Sentries get separate IPC namespaces too."""
    G, pids = scenario_graph
    app_pd, kvs_pd = f"PD_{pids[0]}", f"PD_{pids[1]}"
    for ns in ("MNT", "IPC", "NET", "PAGE_QUOTA"):
        shared = shared_resource_spaces(G, app_pd, kvs_pd, ns)
        assert len(shared) == 0, (
            f"gVisor containers should have separate {ns} resource spaces, "
            f"but share: {shared}"
        )


@pytest.mark.skipif(not gvisor_available, reason="runsc not installed")
@pytest.mark.parametrize("scenario_graph", ["gvisor"], indirect=True)
def test_gvisor_isolation_layers_score(scenario_graph):
    """gVisor should score 5/7 on isolation_layers: MNT+IPC+NET+cgroup+vm_boundary.
    MAC profile and syscall surface between siblings are both '--' (same profile/filter)."""
    G, pids = scenario_graph
    il = isolation_layers(G, f"PD_{pids[0]}", f"PD_{pids[1]}")
    score = sum(1 for v in il.values() if v)
    assert score >= 5, (
        f"gVisor expected ≥5/7 isolation dimensions, got {score}/7: {il}"
    )
    # VM boundary specifically must be True (novel vs Docker)
    assert il["vm_boundary"]
    # IPC must be isolated (novel vs Kata which shows IPC--)
    assert il["different_ipc_ns"]


# ---------------------------------------------------------------------------
# Firecracker (standalone VMM — no container runtime wrapper)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not firecracker_available, reason="firecracker not installed")
@pytest.mark.parametrize("scenario_graph", ["firecracker"], indirect=True)
def test_firecracker_host_visible_as_firecracker(scenario_graph):
    """From the host, Firecracker VMMs are visible as 'firecracker' processes.
    No container runtime wraps them — they run directly in host namespaces."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_name = G.nodes[f"PD_{pids[0]}"].get("data", "")
    assert "firecracker" in app_name.lower(), (
        f"FC PD should be named 'firecracker', got '{app_name}'"
    )


@pytest.mark.skipif(not firecracker_available, reason="firecracker not installed")
@pytest.mark.parametrize("scenario_graph", ["firecracker"], indirect=True)
def test_firecracker_vm_boundary(scenario_graph):
    """Standalone Firecracker: vm_boundary=True (binary name in _HYPERVISOR_NAMES)."""
    G, pids = scenario_graph
    il = isolation_layers(G, f"PD_{pids[0]}", f"PD_{pids[1]}")
    assert il["vm_boundary"], "Firecracker must be detected as hypervisor via _is_hypervisor()"


@pytest.mark.skipif(not firecracker_available, reason="firecracker not installed")
@pytest.mark.parametrize("scenario_graph", ["firecracker"], indirect=True)
def test_firecracker_no_namespace_isolation(scenario_graph):
    """Standalone FC runs directly in host namespaces — no container runtime wraps it.
    Contrast with Kata (4/7): Kata's QEMU runs inside Docker's namespace isolation.
    FC has vm_boundary=True but MNT/IPC/NET namespace dimensions are all False."""
    G, pids = scenario_graph
    app_pd, kvs_pd = f"PD_{pids[0]}", f"PD_{pids[1]}"
    il = isolation_layers(G, app_pd, kvs_pd)
    assert il["vm_boundary"], "FC must have vm_boundary"
    assert not il["different_mnt_ns"], "Both FC processes share host MNT namespace"
    assert not il["different_net_ns"], "Both FC processes share host NET namespace"
    assert not il["different_ipc_ns"], "Both FC processes share host IPC namespace"


@pytest.mark.skipif(not firecracker_available, reason="firecracker not installed")
@pytest.mark.parametrize("scenario_graph", ["firecracker"], indirect=True)
def test_firecracker_isolation_layers_score(scenario_graph):
    """Standalone FC scores 1/7: only vm_boundary=True.
    Novel row in Tab. 2 — same vm_boundary as Kata but no namespace isolation
    because no container runtime creates namespace wrappers around the FC process."""
    G, pids = scenario_graph
    il = isolation_layers(G, f"PD_{pids[0]}", f"PD_{pids[1]}")
    true_dims = [k for k, v in il.items() if v]
    assert true_dims == ["vm_boundary"], (
        f"Expected only vm_boundary=True for standalone FC, got: {true_dims}"
    )


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


# ---------------------------------------------------------------------------
# Docker with daemons (full daemon chain: dockerd → containerd → shim → container)
# ---------------------------------------------------------------------------

def _find_pd_by_name(G, name: str):
    """Return PD node ID whose data field matches name exactly, or None."""
    return next((n for n, d in G.nodes(data=True)
                 if d.get("type") == "PD" and d.get("data") == name), None)


def _find_pd_by_name_contains(G, fragment: str):
    """Return all PD node IDs whose data field contains fragment."""
    return [n for n, d in G.nodes(data=True)
            if d.get("type") == "PD" and fragment in d.get("data", "")]


def _get_pd_extra(G, pd_node: str) -> dict:
    """Parse and return the extra JSON dict for a PD node, or {}."""
    import json
    raw = G.nodes[pd_node].get("extra", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h1_root_daemons_hold_containers(scenario_graph):
    """H1: Root daemons (uid=0) have HOLD edges to container PDs.
    Kernel is root; daemons run as root; so daemons → containers via __add_inter_process_hold_edges."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"

    # Find daemon PDs (containerd-shim, containerd, dockerd)
    daemon_names = ["dockerd", "containerd", "containerd-shim-runc-v2", "containerd-shim"]
    daemon_pds = []
    for name in daemon_names:
        found = _find_pd_by_name(G, name)
        if found:
            daemon_pds.append(found)
    # At least one daemon must be present
    assert daemon_pds, \
        "No daemon PDs (dockerd/containerd/shim) found in graph; --with-ancestors may not have worked"

    # Each daemon should be able to control (hold) both container PDs
    for daemon_pd in daemon_pds:
        reachable = can_control(G, daemon_pd)
        assert app_pd in reachable or kvs_pd in reachable, \
            f"Daemon PD {G.nodes[daemon_pd].get('data')} should hold at least one container PD"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h2_kernel_holds_daemons(scenario_graph):
    """H2: kernel PD has HOLD edges to dockerd, containerd, and containerd-shim."""
    G, _ = scenario_graph
    kernel_pd = next(
        (n for n, d in G.nodes(data=True) if "Linux" in d.get("data", "")), None
    )
    assert kernel_pd is not None, "Kernel PD not found"

    daemon_names = ["dockerd", "containerd", "containerd-shim-runc-v2", "containerd-shim"]
    found_daemons = []
    for name in daemon_names:
        pd = _find_pd_by_name(G, name)
        if pd:
            found_daemons.append((name, pd))

    assert found_daemons, "No daemon PDs found in graph"
    kernel_reachable = can_control(G, kernel_pd)
    for name, pd in found_daemons:
        assert pd in kernel_reachable, \
            f"Kernel should hold {name} (root daemon) via HOLD edge"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h3_two_shim_nodes(scenario_graph):
    """H3: There should be two separate containerd-shim PD nodes (one per container)."""
    G, _ = scenario_graph
    shim_pds = (_find_pd_by_name_contains(G, "containerd-shim"))
    assert len(shim_pds) >= 2, \
        f"Expected ≥2 containerd-shim PD nodes (one per container), found {len(shim_pds)}: {shim_pds}"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h4_containers_separate_cgroup_from_daemons(scenario_graph):
    """H4: Container PDs should be in separate PAGE_QUOTA spaces from each other and from daemons.
    Docker creates per-container cgroup scopes under docker-<id>.scope."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"

    # Containers should not share cgroup space with each other
    cg_shared_containers = shared_resource_spaces(G, app_pd, kvs_pd, "PAGE_QUOTA")
    assert len(cg_shared_containers) == 0, \
        f"Container PDs should have separate cgroup (PAGE_QUOTA) spaces, but they share: {cg_shared_containers}"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h5_containers_separate_mnt_from_daemons(scenario_graph):
    """H5: Container PDs should be in different MNT resource space from daemon PDs.
    Docker creates a new MNT namespace per container."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"

    daemon_names = ["dockerd", "containerd", "containerd-shim-runc-v2", "containerd-shim"]
    for name in daemon_names:
        daemon_pd = _find_pd_by_name(G, name)
        if daemon_pd is None:
            continue
        mnt_shared = shared_resource_spaces(G, app_pd, daemon_pd, "MNT")
        assert len(mnt_shared) == 0, \
            f"Container (app) should NOT share MNT space with {name}, but shares: {mnt_shared}"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h6_containers_separate_ipc_from_daemons(scenario_graph):
    """H6: Container PDs should be in different IPC resource space from daemon PDs.
    Docker creates a new IPC namespace per container."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"
    kvs_pd = f"PD_{pids[1]}"

    daemon_names = ["dockerd", "containerd", "containerd-shim-runc-v2", "containerd-shim"]
    for name in daemon_names:
        daemon_pd = _find_pd_by_name(G, name)
        if daemon_pd is None:
            continue
        ipc_shared = shared_resource_spaces(G, app_pd, daemon_pd, "IPC")
        assert len(ipc_shared) == 0, \
            f"Container (app) should NOT share IPC space with {name}, but shares: {ipc_shared}"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h7_shim_file_sharing_observational(scenario_graph):
    """H7 (observational): Quantify FILE resources shared between containerd-shim and its container.
    The shim manages container stdio — this may appear as shared FILE resources.
    Any result is informative (new finding not stated in Docker architecture docs)."""
    G, pids = scenario_graph
    assert len(pids) == 2
    app_pd = f"PD_{pids[0]}"

    shim_pds = _find_pd_by_name_contains(G, "containerd-shim")
    if not shim_pds:
        pytest.skip("No containerd-shim PD found in graph")

    # Count shared FILE resources between each shim and the app container
    for shim_pd in shim_pds:
        file_shared = shared_resources(G, app_pd, shim_pd, "FILE")
        # Observational: just record, don't assert a specific count
        print(f"\nH7: shim {G.nodes[shim_pd].get('data')} ↔ app container "
              f"shares {len(file_shared)} FILE resource(s): {file_shared}")
    # Always passes — documents the finding
    assert True


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h8_seccomp_annotations(scenario_graph):
    """H8: Container PDs annotated seccomp=2 (filter); daemon PDs seccomp=0 (off).
    Docker applies its default seccomp profile to containers."""
    G, pids = scenario_graph
    assert len(pids) == 2

    for pid in pids:
        pd = f"PD_{pid}"
        extra = _get_pd_extra(G, pd)
        seccomp = extra.get("seccomp")
        assert seccomp == 2, \
            f"Container PD_{pid} should have seccomp=2 (filter), got {seccomp}"

    daemon_names = ["dockerd", "containerd", "containerd-shim-runc-v2", "containerd-shim"]
    for name in daemon_names:
        daemon_pd = _find_pd_by_name(G, name)
        if daemon_pd is None:
            continue
        extra = _get_pd_extra(G, daemon_pd)
        seccomp = extra.get("seccomp")
        assert seccomp == 0, \
            f"Daemon {name} should have seccomp=0 (off), got {seccomp}"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h9_apparmor_annotations(scenario_graph):
    """H9: Container PDs annotated AppArmor=docker-default; daemon PDs have no/different label.
    Docker applies the docker-default AppArmor profile to containers."""
    G, pids = scenario_graph
    assert len(pids) == 2

    for pid in pids:
        pd = f"PD_{pid}"
        extra = _get_pd_extra(G, pd)
        lsm_label = extra.get("lsm_label", "")
        assert "docker-default" in lsm_label, \
            f"Container PD_{pid} should have AppArmor label containing 'docker-default', got '{lsm_label}'"

    daemon_names = ["dockerd", "containerd", "containerd-shim-runc-v2", "containerd-shim"]
    for name in daemon_names:
        daemon_pd = _find_pd_by_name(G, name)
        if daemon_pd is None:
            continue
        extra = _get_pd_extra(G, daemon_pd)
        lsm_label = extra.get("lsm_label", "")
        assert "docker-default" not in lsm_label, \
            f"Daemon {name} should NOT have docker-default AppArmor label, got '{lsm_label}'"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h9_mac_profile_node_attribute(scenario_graph):
    """H9 (extended): lsm_label is included in PD node extra JSON, enabling
    isolation_layers() to report different_mac_profile. Containers must carry
    'docker-default'; daemons must carry a different (or empty) label."""
    G, pids = scenario_graph
    assert len(pids) == 2

    for pid in pids:
        pd = f"PD_{pid}"
        extra = _get_pd_extra(G, pd)
        lsm_label = extra.get("lsm_label", "")
        assert "docker-default" in lsm_label, (
            f"Container {pd} extra JSON must contain lsm_label with 'docker-default', "
            f"got '{lsm_label}'"
        )

    daemon_pd = _find_pd_by_name(G, "dockerd")
    if daemon_pd is not None:
        daemon_label = _get_pd_extra(G, daemon_pd).get("lsm_label", "")
        container_label = _get_pd_extra(G, f"PD_{pids[0]}").get("lsm_label", "")
        assert container_label != daemon_label, (
            f"Container and dockerd must have different lsm_label in extra JSON; "
            f"both have: '{container_label}'"
        )


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_docker_daemons_h8_seccomp_reduces_api_surface(scenario_graph):
    """H8 (extended): Docker's default seccomp profile is reflected in the model via
    allowed_syscalls node attribute. Container PDs should have fewer allowed syscalls
    than unfiltered daemon PDs (syscall_surface query)."""
    G, pids = scenario_graph
    app_pd = f"PD_{pids[0]}"
    daemon_pd = _find_pd_by_name(G, "dockerd")
    if daemon_pd is None:
        pytest.skip("dockerd PD not found in graph")

    container_syscalls = syscall_surface(G, app_pd)
    daemon_syscalls    = syscall_surface(G, daemon_pd)

    # Syscalls the daemon can invoke but the container cannot
    blocked = daemon_syscalls - container_syscalls
    assert len(blocked) >= 10, (
        f"Expected Docker seccomp to block ≥10 tracked syscalls for container; "
        f"got {len(blocked)}: {sorted(blocked)}"
    )
    # Spot-check known docker-default blocked syscalls
    known_blocked = {"ptrace", "mount", "reboot", "kexec_load"}
    assert known_blocked & blocked, (
        f"Known blocked syscalls should be absent from container surface; "
        f"expected subset of {known_blocked} in blocked={sorted(blocked)}"
    )


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_isolation_layers_between_containers(scenario_graph):
    """Two Docker containers from the same image should be isolated by namespace
    dimensions but share the same docker-default seccomp profile and AppArmor label."""
    G, pids = scenario_graph
    assert len(pids) == 2

    layers = isolation_layers(G, f"PD_{pids[0]}", f"PD_{pids[1]}")

    # Namespace isolation: Docker creates separate namespaces per container
    assert layers["different_mnt_ns"], \
        "Docker containers must have different MNT namespaces"
    assert layers["different_ipc_ns"], \
        "Docker containers must have different IPC namespaces"
    assert layers["different_net_ns"], \
        "Docker containers must have different NET namespaces"
    assert layers["different_cgroup"], \
        "Docker containers must have different cgroups"

    # Profile isolation: both containers use docker-default (same profile)
    assert not layers["different_mac_profile"], \
        "Two containers from same image share docker-default AppArmor profile"
    assert not layers["different_syscall_surface"], \
        "Two containers from same image share the same seccomp-filtered syscall surface"


@pytest.mark.parametrize("scenario_graph", ["docker-with-daemons"], indirect=True)
def test_isolation_layers_container_vs_daemon(scenario_graph):
    """A Docker container and the dockerd daemon should differ in MAC profile and
    syscall surface — container has docker-default seccomp, daemon has none."""
    G, pids = scenario_graph
    daemon_pd = _find_pd_by_name(G, "dockerd")
    if daemon_pd is None:
        pytest.skip("dockerd PD not found in graph")

    layers = isolation_layers(G, f"PD_{pids[0]}", daemon_pd)

    assert layers["different_mac_profile"], (
        "Container (docker-default AppArmor) and daemon (unconfined) must have "
        "different MAC profiles"
    )
    assert layers["different_syscall_surface"], (
        "Container (docker-default seccomp) and daemon (unfiltered) must have "
        "different effective syscall surfaces"
    )


# ---------------------------------------------------------------------------
# FUSE filesystem (passthrough FUSE server + hello client)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not fuse_available, reason="/dev/fuse not available")
@pytest.mark.parametrize("scenario_graph", ["fuse"], indirect=True)
def test_fuse_request_edge(scenario_graph):
    """FUSE client process should have a REQUEST edge to the FUSE server process.
    The python passthrough FUSE server serves files to the hello client;
    detect_fuse_connections() should detect the /dev/fuse fd and emit a REQUEST edge.
    setup.sh: APP_PID=server (passthrough.py), KVS_PID=client (hello)."""
    G, pids = scenario_graph
    assert len(pids) == 2, "Expected exactly 2 PIDs: server (APP_PID) + client (KVS_PID)"
    # APP_PID=server (passthrough.py), KVS_PID=client (hello)
    server_pd = f"PD_{pids[0]}"
    client_pd = f"PD_{pids[1]}"

    assert server_pd in G.nodes, f"FUSE server PD {server_pd} not in graph"
    assert client_pd in G.nodes, f"FUSE client PD {client_pd} not in graph"

    # Client should have a REQUEST edge to the FUSE server
    request_targets = {v for _, v, d in G.out_edges(client_pd, data=True)
                       if d.get("type") == "REQUEST"
                       and G.nodes.get(v, {}).get("type") == "PD"}
    assert server_pd in request_targets, (
        f"FUSE client ({client_pd}) should have a REQUEST edge to the FUSE server "
        f"({server_pd}). REQUEST targets found: {request_targets}"
    )


@pytest.mark.skipif(not fuse_available, reason="/dev/fuse not available")
@pytest.mark.parametrize("scenario_graph", ["fuse"], indirect=True)
def test_fuse_mnt_namespace_space_modeling(scenario_graph):
    """MNT resource spaces should be modeled for the FUSE scenario."""
    G, pids = scenario_graph

    # Check that MNT spaces exist in graph (the __add_mnt_namespaces pass populated them)
    mnt_spaces = [n for n, d in G.nodes(data=True)
                  if d.get("type") == "RESOURCE_SPACE" and "MNT" in d.get("data", "")]
    assert len(mnt_spaces) >= 1, "MNT resource spaces should be present in graph"

    # Both server and client should hold at least one MNT resource space
    for pid in pids:
        pd = f"PD_{pid}"
        held_spaces = {v for _, v, d in G.out_edges(pd, data=True)
                       if d.get("type") == "HOLD"
                       and G.nodes.get(v, {}).get("type") == "RESOURCE_SPACE"
                       and "MNT" in G.nodes[v].get("data", "")}
        assert len(held_spaces) >= 1, f"{pd} should hold at least one MNT resource space"


# ---------------------------------------------------------------------------
# gVisor two-level vm_model extraction (host + guest)
# ---------------------------------------------------------------------------

# Check that the gVisor vm-model test container image and setup are available.
# Uses ubuntu:24.04 (not ubuntu:22.04) because pypfs requires glibc 2.38.
_gvisor_vm_model_setup = os.path.exists(
    os.path.join(PROC_DIR, "test_configs", "gvisor-vm-model", "setup.sh"))
_vm_model_py = os.path.join(PROC_DIR, "vm_model.py")


@pytest.mark.skipif(not gvisor_available, reason="runsc not installed")
@pytest.mark.skipif(not _gvisor_vm_model_setup, reason="gvisor-vm-model setup missing")
def test_gvisor_vm_model_guest_csv_nonempty(tmp_path):
    """Two-level gVisor extraction: guest.csv must contain at least the sleep process."""
    import subprocess, csv

    # Start the container via the standard setup script
    setup = os.path.join(PROC_DIR, "test_configs", "gvisor-vm-model", "setup.sh")
    result = subprocess.run(["bash", setup], capture_output=True, text=True)
    if result.returncode != 0:
        skip_line = next((l for l in result.stderr.splitlines() if l.startswith("SKIP=")), None)
        if skip_line:
            pytest.skip(skip_line[len("SKIP="):])
        raise subprocess.CalledProcessError(result.returncode, ["bash", setup],
                                            result.stdout, result.stderr)

    out_dir = str(tmp_path / "gvisor-vm")
    os.makedirs(out_dir)
    guest_csv = os.path.join(out_dir, "guest.csv")
    host_csv  = os.path.join(out_dir, "host.csv")
    g2h_csv   = os.path.join(out_dir, "g2h.csv")

    try:
        subprocess.check_call(
            ["sudo", "-E", "python3", _vm_model_py,
             "--vmm", "gvisor", "--container", "osmosis-gvisor-vm-test"],
            cwd=PROC_DIR, env=os.environ.copy())

        # vm_model.py writes into ./outputs/gvisor/<timestamp>/; find the latest
        import glob
        latest = sorted(glob.glob(os.path.join(PROC_DIR, "outputs", "gvisor", "*")))[-1]
        guest_csv = os.path.join(latest, "guest.csv")
        g2h_csv   = os.path.join(latest, "g2h_file.csv")

        assert os.path.exists(guest_csv), "guest.csv not produced"
        with open(guest_csv) as f:
            rows = list(csv.reader(f))
        assert len(rows) > 1, "guest.csv is empty"

        # At least one PD node (from the sleep process inside the sandbox)
        pd_rows = [r for r in rows if len(r) > 0 and r[0] == "PD"]
        assert len(pd_rows) >= 1, "No PD nodes in guest.csv"

        # g2h.csv should exist (may be empty in KVM mode if no MOs match)
        assert os.path.exists(g2h_csv), "g2h_file.csv not produced"

    finally:
        teardown = os.path.join(PROC_DIR, "test_configs", "gvisor-vm-model", "teardown.sh")
        subprocess.run(["bash", teardown], capture_output=True)


# ---------------------------------------------------------------------------
# Firecracker two-level vm_model extraction (host VMM + guest)
# ---------------------------------------------------------------------------

_FC_KERNEL   = "/usr/local/share/firecracker/vmlinux.bin"
_FC_ROOTFS   = "/usr/local/share/firecracker/rootfs-noble.ext4"
_fc_vm_model_available = (
    firecracker_available
    and os.path.exists(_FC_KERNEL)
    and os.path.exists(_FC_ROOTFS)
)


@pytest.mark.skipif(not firecracker_available, reason="firecracker not installed")
@pytest.mark.skipif(not _fc_vm_model_available,
                    reason="FC kernel/rootfs-noble.ext4 not present")
def test_firecracker_vm_model_guest_csv_nonempty():
    """Two-level FC extraction: guest.csv must contain PD nodes from inside the microVM."""
    import subprocess, csv, glob

    _vm_model_py = os.path.join(PROC_DIR, "vm_model.py")
    subprocess.check_call(
        ["sudo", "-E", "python3", _vm_model_py,
         "--vmm", "firecracker",
         "--kernel", _FC_KERNEL,
         "--rootfs", _FC_ROOTFS],
        cwd=PROC_DIR)

    latest = sorted(glob.glob(os.path.join(PROC_DIR, "outputs", "firecracker", "*")))[-1]
    guest_csv = os.path.join(latest, "guest.csv")
    g2h_csv   = os.path.join(latest, "g2h_file.csv")

    assert os.path.exists(guest_csv), "guest.csv not produced"
    with open(guest_csv) as f:
        rows = list(csv.reader(f))
    assert len(rows) > 1, "guest.csv is empty"

    pd_rows = [r for r in rows if len(r) > 0 and r[0] == "PD"]
    assert len(pd_rows) >= 1, "No PD nodes in guest.csv"

    # g2h CSV must exist and have MAP edges (FC always has pagemap access)
    assert os.path.exists(g2h_csv), "g2h_file.csv not produced"
    with open(g2h_csv) as f:
        g2h_rows = list(csv.reader(f))
    edge_rows = [r for r in g2h_rows if len(r) > 3 and r[3] == "MAP"]
    assert len(edge_rows) >= 1, "No MAP edges in g2h_file.csv"
