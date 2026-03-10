"""
test_extraction.py — Unit tests for each procfs extractor.
Most tests require root (for /proc/PID/pagemap) and Linux.
Run with: sudo python -m pytest tests/test_extraction.py -v
"""

import os
import sys
import time
import signal
import subprocess
import pytest

PROC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROC_DIR)

# pfs/lib: try shared path first, then VM-local build
for _pfs_candidate in [os.path.join(PROC_DIR, "pfs", "lib"),
                        os.path.expanduser("~/proc/pfs/lib")]:
    if os.path.isdir(_pfs_candidate) and any(f.endswith(".so") for f in os.listdir(_pfs_candidate)):
        sys.path.insert(0, _pfs_candidate)
        break

# test_programs: find the directory with compiled binaries
TEST_PROGRAMS_DIR = next(
    (d for d in [os.path.join(PROC_DIR, "test_programs"),
                 os.path.expanduser("~/proc/test_programs")]
     if os.path.isdir(d) and os.path.exists(os.path.join(d, "hello"))),
    os.path.join(PROC_DIR, "test_programs")
)


# ---------------------------------------------------------------------------
# Skip guard: these tests only run on Linux with pypfs available
# ---------------------------------------------------------------------------
try:
    import pypfs  # type: ignore
    HAVE_PYPFS = True
except ImportError:
    HAVE_PYPFS = False

pytestmark = pytest.mark.skipif(not HAVE_PYPFS, reason="pypfs not available (Linux only)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start_hello(name="hello"):
    binary = os.path.join(TEST_PROGRAMS_DIR, name)
    if not os.path.exists(binary):
        pytest.skip(f"Binary '{name}' not built at {binary}; run 'make -C test_programs all'")
    p = subprocess.Popen([binary])
    time.sleep(0.5)
    return p


def _kill(p):
    try:
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# VMR / maps extraction tests
# ---------------------------------------------------------------------------

def test_read_maps_file_basic():
    """VMR list has entries for heap, stack, [vdso]."""
    import proc_model
    p = _start_hello()
    try:
        maps = proc_model.read_maps_file(p.pid)
        pathnames = [m.pathname for m in maps]
        assert any(pn == "[heap]" for pn in pathnames), "heap VMR missing"
        assert any(pn == "[stack]" for pn in pathnames), "stack VMR missing"
        assert any(pn == "[vdso]" for pn in pathnames), "vdso VMR missing"
    finally:
        _kill(p)


def test_read_maps_file_static():
    """Static binary has no shared libraries in its maps."""
    import proc_model
    p = _start_hello("hello_static")
    try:
        maps = proc_model.read_maps_file(p.pid)
        so_entries = [m.pathname for m in maps if ".so" in (m.pathname or "")]
        assert len(so_entries) == 0, f"Static binary should have no .so entries, got {so_entries}"
    finally:
        _kill(p)


def test_vdso_always_present():
    """Even a statically linked process has a [vdso] VMR."""
    import proc_model
    p = _start_hello("hello_static")
    try:
        maps = proc_model.read_maps_file(p.pid)
        assert any(m.pathname == "[vdso]" for m in maps), "[vdso] missing in static binary"
    finally:
        _kill(p)


def test_read_pagemap_heap_mapped():
    """Heap VMR has at least one SubVMR with mapped=True."""
    from procfs_data import ProcFsData, MappingType
    import proc_model
    p = _start_hello()
    try:
        data = ProcFsData()
        data.os_name = "Host Linux"
        proc_model.extract_process_data(data, p.pid, "hello")
        proc_info = data.procs[p.pid]
        heap_vmr = None
        for (_, __), vmr in proc_info.ads.vmrs.items():
            if vmr.pathname == "[heap]":
                heap_vmr = vmr
                break
        assert heap_vmr is not None, "No heap VMR found"
        mapped_subs = [sv for (_, __), sv in heap_vmr.sub_vmrs.items() if sv.mapped]
        assert len(mapped_subs) > 0, "Heap VMR has no mapped sub-VMRs"
    finally:
        _kill(p)


# ---------------------------------------------------------------------------
# Status extraction tests
# ---------------------------------------------------------------------------

def test_extract_status_uid():
    """uid_effective matches the current process UID."""
    from procfs_data import ProcFsData
    import proc_model
    p = _start_hello()
    try:
        data = ProcFsData()
        data.os_name = "Host Linux"
        proc_model.extract_process_data(data, p.pid, "hello")
        assert data.procs[p.pid].uid_effective == os.getuid(), \
            "uid_effective should match current user's UID"
    finally:
        _kill(p)


# ---------------------------------------------------------------------------
# Namespace extraction tests
# ---------------------------------------------------------------------------

def test_extract_namespaces_pid():
    """PID namespace handle is a non-zero integer after extraction."""
    from procfs_data import ProcFsData, NamespaceType
    import proc_model
    p = _start_hello()
    try:
        data = ProcFsData()
        data.os_name = "Host Linux"
        proc_model.extract_process_data(data, p.pid, "hello")
        ns_map = data.procs[p.pid].namespaces
        assert NamespaceType.PID in ns_map, "PID namespace not extracted"
        assert ns_map[NamespaceType.PID].handle > 0, "PID namespace handle must be > 0"
    finally:
        _kill(p)


def test_extract_namespaces_mnt():
    """MNT namespace handle is a non-zero integer after extraction."""
    from procfs_data import ProcFsData, NamespaceType
    import proc_model
    p = _start_hello()
    try:
        data = ProcFsData()
        data.os_name = "Host Linux"
        proc_model.extract_process_data(data, p.pid, "hello")
        ns_map = data.procs[p.pid].namespaces
        assert NamespaceType.MNT in ns_map, "MNT namespace not extracted"
        assert ns_map[NamespaceType.MNT].handle > 0, "MNT namespace handle must be > 0"
    finally:
        _kill(p)


# ---------------------------------------------------------------------------
# Mountinfo extraction tests
# ---------------------------------------------------------------------------

def test_extract_mountinfo_count():
    """pid_mounts has more than 5 entries for a normal process."""
    from procfs_data import ProcFsData
    import proc_model
    p = _start_hello()
    try:
        data = ProcFsData()
        data.os_name = "Host Linux"
        proc_model.extract_process_data(data, p.pid, "hello")
        mounts = data.procs[p.pid].pid_mounts
        assert len(mounts) > 5, f"Expected >5 mounts, got {len(mounts)}"
    finally:
        _kill(p)


# ---------------------------------------------------------------------------
# Cgroup extraction tests
# ---------------------------------------------------------------------------

def test_extract_cgroups_path():
    """cgroup_path is a non-empty string starting with '/'."""
    from procfs_data import ProcFsData
    import proc_model
    p = _start_hello()
    try:
        data = ProcFsData()
        data.os_name = "Host Linux"
        proc_model.extract_process_data(data, p.pid, "hello")
        cpath = data.procs[p.pid].cgroup_path
        assert cpath, "cgroup_path is empty"
        assert cpath.startswith("/"), f"cgroup_path should start with '/', got '{cpath}'"
    finally:
        _kill(p)


# ---------------------------------------------------------------------------
# Model graph edge tests
# ---------------------------------------------------------------------------

def test_hold_edge_same_uid(loaded_graph):
    """ModelGraph has a HOLD edge between two same-uid PDs."""
    G = loaded_graph
    hold_pd_edges = [
        (u, v) for u, v, d in G.edges(data=True)
        if d.get("type") == "HOLD"
        and G.nodes[u].get("type") == "PD"
        and G.nodes[v].get("type") == "PD"
    ]
    assert len(hold_pd_edges) > 0, "No inter-PD HOLD edges found for same-uid processes"


def test_file_resource_created(loaded_graph):
    """At least one FILE resource node exists in the graph."""
    G = loaded_graph
    file_nodes = [n for n, d in G.nodes(data=True)
                  if d.get("type") == "RESOURCE" and d.get("data") == "FILE"]
    assert len(file_nodes) > 0, "No FILE resource nodes found; check mountinfo extraction"


def test_cgroup_space_created(loaded_graph):
    """At least one PAGE_QUOTA resource space exists in the graph."""
    G = loaded_graph
    cgroup_spaces = [n for n, d in G.nodes(data=True)
                     if d.get("type") == "RESOURCE_SPACE" and d.get("data") == "PAGE_QUOTA"]
    assert len(cgroup_spaces) > 0, "No PAGE_QUOTA resource spaces found; check cgroup extraction"


def test_root_holds_all(tmp_path):
    """Root PD (uid 0) has a HOLD edge to every non-root PD."""
    if os.getuid() != 0:
        pytest.skip("This test must run as root to create a uid-0 process")

    from procfs_data import ProcFsData, MappingType
    import proc_model
    from metrics import read_csv_to_graph

    root_hello = os.path.join(TEST_PROGRAMS_DIR, "hello")
    if not os.path.exists(root_hello):
        pytest.skip("hello binary not built")

    # Start a non-root process by dropping privileges via sudo -u
    try:
        nonroot_user = subprocess.check_output(
            ["awk", "-F:", "$3==1000{print $1; exit}", "/etc/passwd"], text=True
        ).strip()
    except Exception:
        pytest.skip("Could not find uid=1000 user for non-root process")

    root_p = subprocess.Popen([root_hello])
    time.sleep(0.3)
    nonroot_p = subprocess.Popen(["sudo", "-u", nonroot_user, root_hello])
    time.sleep(0.3)

    try:
        data = ProcFsData()
        data.os_name = "Host Linux"
        proc_model.extract_process_data(data, root_p.pid, "hello")
        proc_model.extract_process_data(data, nonroot_p.pid, "hello")
        csv = str(tmp_path / "root_test.csv")
        data.to_generic_model(MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS).to_csv(csv)
        G = read_csv_to_graph(csv)

        root_pd = f"PD_{root_p.pid}"
        target_pd = f"PD_{nonroot_p.pid}"
        hold_edges = [(u, v) for u, v, d in G.edges(data=True)
                      if d.get("type") == "HOLD"
                      and u == root_pd and v == target_pd]
        assert len(hold_edges) > 0, "Root PD should hold non-root PD"
    finally:
        _kill(root_p)
        _kill(nonroot_p)
