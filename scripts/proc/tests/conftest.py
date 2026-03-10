"""
conftest.py — pytest fixtures for proc lintool tests.

All graph analysis uses NetworkX (no Neo4j). The fixtures cover:
  - two_same_uid_procs: two hello processes with the same UID
  - loaded_graph:       extracts model for those procs, returns nx.MultiDiGraph
  - scenario_graph:     runs a test_configs/*/setup.sh, extracts all PIDs, returns graph
"""

import subprocess
import signal
import os
import time
import sys
import pytest
import networkx as nx

# Make the proc/ directory importable from tests/
PROC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROC_DIR)
sys.path.insert(0, os.path.join(PROC_DIR, "submarine"))
# pfs/lib: try the shared path first, then fall back to the VM-local built path
_pfs_lib_candidates = [
    os.path.join(PROC_DIR, "pfs", "lib"),                     # shared path (if .so copied)
    os.path.expanduser("~/proc/pfs/lib"),                      # VM-local build
    os.path.join(os.path.expanduser("~"), "proc", "pfs", "lib"),
]
for _candidate in _pfs_lib_candidates:
    if os.path.isdir(_candidate) and any(f.endswith(".so") for f in os.listdir(_candidate)):
        sys.path.insert(0, _candidate)
        break
else:
    sys.path.insert(0, _pfs_lib_candidates[0])  # Insert anyway so error is clear

from metrics import read_csv_to_graph

# Test programs may be compiled in a separate writable directory (e.g. on VM)
# when the source tree is on a read-only shared mount.
_TEST_PROGRAMS_CANDIDATES = [
    os.path.join(PROC_DIR, "test_programs"),                  # source tree (Mac or writable)
    os.path.expanduser("~/proc/test_programs"),               # VM-local compiled copy
]
TEST_PROGRAMS_DIR = next(
    (d for d in _TEST_PROGRAMS_CANDIDATES
     if os.path.isdir(d) and os.path.exists(os.path.join(d, "hello"))),
    _TEST_PROGRAMS_CANDIDATES[0]  # fallback
)


# ---------------------------------------------------------------------------
# Basic process fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def two_same_uid_procs(tmp_path):
    """
    Launch two hello processes as the current user, yield (pid1, pid2, csv_path),
    then clean up.
    """
    hello_bin = os.path.join(TEST_PROGRAMS_DIR, "hello")
    if not os.path.exists(hello_bin):
        pytest.skip(f"hello binary not found at {hello_bin}; run 'make -C test_programs all' first")

    p1 = subprocess.Popen([hello_bin])
    p2 = subprocess.Popen([hello_bin])
    time.sleep(1)  # Let processes stabilize

    csv = str(tmp_path / "model.csv")
    yield p1.pid, p2.pid, csv

    for p in (p1, p2):
        try:
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=2)
        except Exception:
            pass


@pytest.fixture
def two_static_procs(tmp_path):
    """Launch two hello_static processes, yield (pid1, pid2, csv_path)."""
    hello_bin = os.path.join(TEST_PROGRAMS_DIR, "hello_static")
    if not os.path.exists(hello_bin):
        pytest.skip(f"hello_static binary not found; run 'make -C test_programs all' first")

    p1 = subprocess.Popen([hello_bin])
    p2 = subprocess.Popen([hello_bin])
    time.sleep(1)

    csv = str(tmp_path / "model_static.csv")
    yield p1.pid, p2.pid, csv

    for p in (p1, p2):
        try:
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=2)
        except Exception:
            pass


@pytest.fixture
def loaded_graph(two_same_uid_procs):
    """
    Extract model for two_same_uid_procs, write CSV, return nx.MultiDiGraph.
    Requires root for /proc/PID/pagemap access.
    """
    pid1, pid2, csv = two_same_uid_procs

    try:
        import pypfs  # noqa: F401
    except ImportError:
        pytest.skip("pypfs not available (run on Linux with pfs/lib compiled)")

    from procfs_data import ProcFsData, MappingType
    import proc_model

    data = ProcFsData()
    data.os_name = "Host Linux"
    proc_model.extract_process_data(data, pid1, "hello")
    proc_model.extract_process_data(data, pid2, "hello")
    model = data.to_generic_model(MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS)
    model.to_csv(csv)
    return read_csv_to_graph(csv)


@pytest.fixture
def loaded_graph_static(two_static_procs):
    """
    Extract model for two static hello processes, return nx.MultiDiGraph.
    """
    pid1, pid2, csv = two_static_procs

    try:
        import pypfs  # noqa: F401
    except ImportError:
        pytest.skip("pypfs not available")

    from procfs_data import ProcFsData, MappingType
    import proc_model

    data = ProcFsData()
    data.os_name = "Host Linux"
    proc_model.extract_process_data(data, pid1, "hello_static")
    proc_model.extract_process_data(data, pid2, "hello_static")
    model = data.to_generic_model(MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS)
    model.to_csv(csv)
    return read_csv_to_graph(csv)


# ---------------------------------------------------------------------------
# Scenario fixture (integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def scenario_graph(tmp_path, request):
    """
    Run a test_configs/<name>/setup.sh, extract all PIDs via proc_model.py,
    return (nx.MultiDiGraph, list_of_pids).

    Usage:
        @pytest.mark.parametrize('scenario_graph', ['docker-regular'], indirect=True)
        def test_foo(scenario_graph):
            G, pids = scenario_graph
    """
    config_name = request.param
    setup_script = os.path.join(PROC_DIR, "test_configs", config_name, "setup.sh")
    teardown_script = os.path.join(PROC_DIR, "test_configs", config_name, "teardown.sh")

    if not os.path.exists(setup_script):
        pytest.skip(f"No setup script for scenario '{config_name}'")

    # setup.sh outputs either:
    #   CONFIG=<n>          → let proc_model.py start/extract/kill via run_configs[n]
    #   APP_PID=<n> KVS_PID=<n>  → external processes; extract by PID
    out = subprocess.check_output(["bash", setup_script], text=True)
    lines = {k: v for k, v in
             (line.split("=", 1) for line in out.splitlines() if "=" in line)}

    csv_path = str(tmp_path / f"{config_name}.csv")
    proc_model_py = os.path.join(PROC_DIR, "proc_model.py")
    python_bin = os.path.join(PROC_DIR, "pyenv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable
    env = os.environ.copy()
    # Use SUDO_USER's home to find the pfs lib, not root's home
    real_home = os.path.expanduser(f"~{os.environ.get('SUDO_USER', os.environ.get('USER', 'siagraw'))}")
    pfs_lib = os.path.join(real_home, "proc", "pfs", "lib")
    env["PYTHONPATH"] = pfs_lib

    # proc_model.py launches binaries via './name' relative to CWD.
    # Run it from the test_programs directory so binaries are found.
    bindir = os.path.join(real_home, "proc", "test_programs")
    sudo_cmd = ["sudo", f"PYTHONPATH={pfs_lib}", python_bin, proc_model_py,
                "--os", "linux", "--csv", csv_path]

    if "CONFIG" in lines:
        # proc_model.py starts, extracts, and kills the processes itself.
        # Capture stdout to extract the PIDs it started.
        out2 = subprocess.check_output(sudo_cmd + ["--config", lines["CONFIG"]],
                                       cwd=bindir, stderr=subprocess.STDOUT, text=True)
        # proc_model.py prints "Extracting process <PID>: <name>" for each PID it handles
        pids = [int(m.split()[2].rstrip(":"))
                for m in out2.splitlines() if m.startswith("Extracting process")]
    else:
        # External processes already running; extract by PID list
        pids = [int(v) for k, v in lines.items() if k.endswith("PID")]
        pids_str = ",".join(str(p) for p in pids)
        subprocess.check_call(sudo_cmd + ["--pids", pids_str])

    G = read_csv_to_graph(csv_path)
    yield G, pids

    if os.path.exists(teardown_script):
        subprocess.call(["bash", teardown_script])
