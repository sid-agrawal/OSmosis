#!/bin/python3

import pexpect
import csv
import os
import time
import json
import argparse
import traceback
import socket
import http.client
import shutil as _shutil
from enum import Enum
from proc_model import extract_process_data, ProcFsData, MappingType
from proc_utils import getPIDByName
from utils import sizeof_fmt, compare_directories, is_root, run
import generic_model as gm
import pprint as pp
from expect_utils import get_qemu_phandle, get_cellulos_phandle
import filecmp
import datetime
import shutil
from import_csv import upload_csv_import

host = "localhost"
port = 45454
telnet_cmd = f"telnet {host} {port}"


class QemuMonitorCommand(Enum):
    GPA2HPA = 0
    GPA2HVA = 1


def get_guest_host_translation(
    cmd: QemuMonitorCommand, addr: int, pexpect_handle: pexpect.spawn
) -> int:
    """
        Query Qemu using the monitor and given a guest-PA,
        get the host-VA, host-PA based on the cmd arg.

        cmd: Qemu Monitor Command 
        addr: guest PA
        pexpect_handle: pexpect handle for the telnet command

        return: hPA or hVA depending on the cmd.
    """

    if cmd == QemuMonitorCommand.GPA2HPA:
        monitor_cmd = f"gpa2hpa 0x{addr:x}"
    elif cmd == QemuMonitorCommand.GPA2HVA:
        monitor_cmd = f"gpa2hva 0x{addr:x}"
    else:
        raise ValueError("Invalid Qemu Monitor Command")

    pexpect_handle.sendline(monitor_cmd)
    pexpect_handle.expect("(qemu)")
    output = pexpect_handle.before.decode()

    def parse(output: str):
        """
        parse the o/p of the gpa2hva/gpa2hpa commands
        """
        for ln in output.splitlines():
            if f"address for 0x{addr:x}" in ln:
                ln = ln.split(" ")
                return int(ln[-1], 16)
            elif "No memory is mapped at" in ln:
                raise ValueError(f"No memory found at 0x{addr:x}, output : {ln}")

    return parse(output)


def get_qemu_vm_state(get_host: bool, guest_file: str, g2h_file: str, host_file: str):
    """
        Start Qemu based linux guest and get the :
        - model state of the hello process inside the guest
        - model state of the qemu process on the host
        - mappings between gpa --> hpa, and gpa --> hva
    """
    
    qemu_pids = getPIDByName("qemu-system-x86_64")
    assert len(qemu_pids) == 0

    # Start Qemu
    qemu_cmd = (
        "/home/" + os.getlogin() + "/buildroot/qemu/buildroot-x86/start-qemu-kvm.sh"
    )
    qemu_phandle = get_qemu_phandle(qemu_cmd)
    host_state = qemu_phandle.before.decode()
    with open(host_file, "w") as out_file:
        for ln in host_state.splitlines():
            if "," in ln:
                print(ln, file=out_file)

    qemu_phandle.sendline("python proc_model.py --os linux --csv ./hello.csv -g")
    qemu_phandle.expect("#")
    qemu_phandle.sendline("cat ./hello.csv")
    qemu_phandle.expect("#")
    hello_csv = qemu_phandle.before.decode()

    # Dump the model state of the guest (i.e. just hello process) 
    # guest_file
    count = 0
    with open(guest_file, "w") as out_file:
        for ln in hello_csv.splitlines():
            if "," in ln:
                count += 1
                print(ln, file=out_file)
    # Guest should have alteast a few edges and nodes
    assert (count > 100)

    # Since the node-ids are by MO-ID, create a mapping from 
    # gPA to MO-ID
    # The format of the CSV is:
    #  [0]         [1]                                    [-1]
    # NODE_TYPE,NODE_ID,DATA,EDGE_TYPE,EDGE_FROM,EDGE_TO,EXTRA
    #
    gPA_to_MO = {}
    with open(guest_file, mode='r', newline='') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            # Split the row by commas
            split_row = row
            row_type = split_row[0]
            row_id = split_row[1]
            extra_dict_str = split_row[-1]

            # Only look at the rows where a MOD node is created
            if row_type == "RESOURCE" and \
                row_id.startswith("MO_"):
                # Parse the last part as a JSON dictionary
                extra_dict = json.loads(extra_dict_str)

                # Print the results
                gpa_hex_str = extra_dict["pa"]
                gpa = int(gpa_hex_str, 16)
                # print (f"---- {gpa_hex_str}:str  {gpa:x}:int")

                # Populate reverse map
                if gpa in gPA_to_MO:
                    raise KeyError(f"Key {gpa} already exists in gPA_to_MO")
                gPA_to_MO[gpa] = row_id

    # for x, y in gPA_to_MO.items(): print(f"gPA --> MO == 0x{x:<16x} --> {y}")

    # Get HOST Qemu State
    qemu_pids = getPIDByName("qemu-system-x86_64")
    assert len(qemu_pids) == 1
    get_host_state(qemu_pids[0], host_file=host_file)
    hPA_to_MO = {}
    hVA_to_VMR = {}

    # Make the rev maps
    with open(host_file, mode='r', newline='') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            # Split the row by commas
            split_row = row
            row_type = split_row[0]
            row_id = split_row[1]
            extra_dict_str = split_row[-1]

            if row_type == "RESOURCE":
                extra_dict = json.loads(extra_dict_str)

                if (row_id.startswith("MO_")):
                    hpa_hex_str = extra_dict["pa"]
                    hpa = int(hpa_hex_str, 16)
                    if hpa in hPA_to_MO:
                        raise KeyError(f"Key {hpa} already exists in hPA_to_MO")
                    hPA_to_MO[hpa] = row_id

                elif row_id.startswith("VMR_"):
                    hva_hex_str = extra_dict["va"]
                    hva = int(hva_hex_str, 16)
                    if hva in hVA_to_VMR:
                        raise KeyError(f"Key {hva} already exists in hVA_to_VMR")
                    hVA_to_VMR[hva] = row_id
    # for x, y in hPA_to_MO.items() : print(f"hPA -->  MO == 0x{x:<16x} --> {y}")
    # for x, y in hVA_to_VMR.items(): print(f"hVA --> VMR == 0x{x:<16x} --> {y}")

    print (f"hPA_to_MO has {len(hPA_to_MO)} entries")
    print (f"hVA_to_VMR has {len(hVA_to_VMR)} entries")
    # This is the model state of the new map edges
    mapping_graph = gm.ModelGraph(id_offset=10000*10000)
    telnet_handle = pexpect.spawn(telnet_cmd)
    telnet_handle.expect("(qemu)")

    start_time = time.time()
    for gpa, g_mo_id in gPA_to_MO.items():
        hpa = get_guest_host_translation(QemuMonitorCommand.GPA2HPA, gpa, telnet_handle)
        hva = get_guest_host_translation(QemuMonitorCommand.GPA2HVA, gpa, telnet_handle)
        host_vmr_id = hVA_to_VMR.get(hva)
        host_mo_id = hPA_to_MO.get(hpa)

        # print(f"Adding Edges for 0x{gpa:<16x} || ", end = "")
        # print(f"\tHPA 0x{hpa:<16x} --> {host_mo_id} |||| ", end = "")
        # print(f"\tHVA 0x{hva:<16x} --> {host_vmr_id}")
        mapping_graph.add_map_edge_raw(g_mo_id, host_mo_id, "QEMU_PD")
        mapping_graph.add_map_edge_raw(g_mo_id, host_vmr_id, "QEMU_PD")
    print("\033[91mXXX: Add Resource Space Map Edge\033[0m")
    print("\033[95mXXX: Add Request Edge from guest to host kernel\033[0m")

    end_time = time.time()
    print(f"Monitor Queries took:  {end_time - start_time} seconds")


    mapping_graph.to_csv(g2h_file, only_edge=True)
    print (f"Generated {len(gPA_to_MO)*2} new mapping edges")
    

    # print the interactions with the child
    # process.
    # qemu_phandle.interact()


def get_host_state(vm_pid: int, host_file: str):

    print (f"Get /proc state for PID: {vm_pid}")

    data = ProcFsData()
    data.os_name = "Linux Kernel"
    try:
        extract_process_data(data, vm_pid, "qemu", should_print=False)
    except Exception as e:
        print("Error printing stats for QEMU")
        print(repr(e))
        traceback.print_exc()
        exit(1)

    data.to_generic_model(
        #MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS
        MappingType.PER_PAGE, MappingType.PER_PAGE
        ).to_csv(
        host_file
    )


def is_cellulos_aarch64_buildroot_osm_dir_updated() -> bool:
    """
    When getting state from inside the vm guest, we need to ensure that the python files
    inside buildroot are up to date.
    """
    dir1 = os.path.expanduser('~/OSmosis/scripts/proc')
    dir2 = os.path.expanduser(
        "~/buildroot/cellulos/qemu/buildroot-arm-cellulos-with-everything/output/target/root/proc"
    )

    assert compare_directories(dir1, dir2, file_extension=".py", 
                               exceptions=["vm_model.py", "import_csv.py", "passthrough.py", "cgroups.py"])

    osm_rootfs = os.path.expanduser(
        "~/OSmosis/projects/sel4-gpi/apps/vmm/board/qemu_arm_virt/rootfs.cpio.gz"
    )
    built_rootfs = os.path.expanduser(
        "~/buildroot/cellulos/qemu/buildroot-arm-cellulos-with-everything/output/images/rootfs.cpio.gz"
    )
    if not filecmp.cmp(osm_rootfs, built_rootfs):
        print (f"CPI files {osm_rootfs} and {built_rootfs} are not the same")
        print (f"Copy from builtroot to cellulos dir")
        return False

    return True


def is_qemu_x86_buildroot_updated() -> bool:
    """
    When getting state from inside the vm guest, we need to ensure that the python files
    inside buildroot are up to date.
    """
    dir1 = os.path.expanduser('~/OSmosis/scripts/proc')
    dir2 = os.path.expanduser('~/buildroot/qemu/buildroot-x86/output/target/root/proc')

    return compare_directories(dir1, dir2, file_extension=".py", 
                               exceptions=["vm_model.py", "import_csv.py", "queries.py"])


def get_cellulos_vm_state(get_host: bool, guest_file: str, g2h_file: str, host_file: str):
    """
        Start Cellulos-VMM based linux guest and get the :
        - model state of the VM as seen from the host
        - model state of the hello process inside the guest
        - mappings between gpa --> hpa, and gpa --> hva
    """
    testname = "GPIKV009"

    original_dir = os.getcwd()
    try: 
        os.chdir("/home/" + os.getlogin() + "/OSmosis/qemu-build/")
        # Build the OSM VM Test

        # Run cmake inside the container
        # We invoke the container using 'make'
        run(
            [
                "make",
                "-C",
                "/home/siagraw/sel4/seL4-CAmkES-L4v-dockerfiles",
                "user_run_l4v",
                "HOST_DIR=/home/siagraw/OSmosis",
                f"EXEC=sh -c 'cd /host/qemu-build && cmake . " +
                f"-DLibSel4TestPrinterRegex={testname} -DGPIExtractModel=ON'" +
                f"-DGPIVMMImplementation=osm-vmm",
            ]
        )
        
        # Make the image
        run(
            [
                "make",
                "-C",
                "/home/siagraw/sel4/seL4-CAmkES-L4v-dockerfiles",
                "user_run_l4v",
                "HOST_DIR=/home/siagraw/OSmosis",
                f"EXEC=sh -c 'cd /host/qemu-build && ninja'"
            ]
        )

        # Run the VMM004 test
        sim_cmd = ("./simulate")
        sim_phandle, host_csv = get_cellulos_phandle(sim_cmd)

        # Run the process, inside the guest.
        sim_phandle.sendline("python proc_model.py --os linux --csv ./data.csv -g")
        sim_phandle.expect("#", timeout=120)
        sim_phandle.sendline("cat ./data.csv")
        sim_phandle.expect("#")
        hello_csv = sim_phandle.before.decode()

    finally:
        os.chdir(original_dir)

    # Dump the model state of the VM-PD
    with open(host_file, "w") as out_file:
        for ln in host_csv:
            print(ln, file=out_file)

    # Dump the model state of the guest (i.e. just hello process)
    with open(guest_file, "w") as out_file:
        for ln in hello_csv.splitlines():
            if "," in ln:
                print(ln, file=out_file)

    # Make the rev mappings for guest
    gPA_to_MO = {}
    with open(guest_file, mode='r', newline='') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            # Split the row by commas
            split_row = row
            row_type = split_row[0]
            row_id = split_row[1]
            extra_dict_str = split_row[-1]

            # Only look at the rows where a MO node is created
            if row_type == "RESOURCE" and \
                row_id.startswith("MO_"):
                # Parse the last part as a JSON dictionary
                extra_dict = json.loads(extra_dict_str)

                # Print the results
                gpa_hex_str = extra_dict["pa"]
                gpa = int(gpa_hex_str, 16)
                # print (f"---- {gpa_hex_str}:str  {gpa:x}:int")

                # Populate reverse map
                if gpa in gPA_to_MO:
                    raise KeyError(f"Key {gpa} already exists in gPA_to_MO")
                gPA_to_MO[gpa] = row_id
    # for x, y in gPA_to_MO.items(): print(f"gPA --> MO == 0x{x:<16x} --> {y}")

    # Make the rev maps for the host file
    hPA_to_MO = {}
    hVA_to_VMR = {}
    with open(host_file, mode='r', newline='') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            # Split the row by commas
            split_row = row
            row_type = split_row[0]
            row_id = split_row[1]
            extra_dict_str = split_row[-1]

            if extra_dict_str == "":
                continue

            if row_type == "RESOURCE":
                extra_dict = json.loads(extra_dict_str)

                if (row_id.startswith("MO_")):
                    if extra_dict["num_pages"] == "0":
                        continue

                    hpa_hex_str = extra_dict["pa"]
                    hpa = int(hpa_hex_str, 16)
                    if hpa in hPA_to_MO:
                        raise KeyError(f"Key {hpa:x} already exists in hPA_to_MO")
                    hPA_to_MO[hpa] = row_id

                # Super Hacky. 
                # This is the prefix of the VM's pages
                elif row_id.startswith("VMR_f"):
                    if extra_dict["num_pages"] == "0":
                        continue

                    hva_hex_str = extra_dict["va"]
                    hva = int(hva_hex_str, 16)
                    if hva in hVA_to_VMR:
                        raise KeyError(f"Key {hva:x} already exists in hVA_to_VMR")
                    hVA_to_VMR[hva] = row_id

    # for x, y in hPA_to_MO.items() : print(f"hPA -->  MO == 0x{x:<16x} --> {y}")
    # for x, y in hVA_to_VMR.items(): print(f"hVA --> VMR == 0x{x:<16x} --> {y}")

    def get_cellulos_gpa_to_hpa(gpa: int) -> int :
        return 0x8040000

    def get_cellulos_gpa_to_hva(gpa: int) -> int :
        return 0x40000000

    mapping_graph = gm.ModelGraph(id_offset=10000*10000)
    for gpa, g_mo_id in gPA_to_MO.items():
        hpa = get_cellulos_gpa_to_hpa(gpa)
        hva = get_cellulos_gpa_to_hva(gpa)
        host_vmr_id = hVA_to_VMR.get(hva)
        assert (host_vmr_id)
        host_mo_id = hPA_to_MO.get(hpa)
        assert (host_mo_id)

        # print(f"Adding Edges for 0x{gpa:<16x} || ", end = "")
        # print(f"\tHPA 0x{hpa:<16x} --> {host_mo_id} |||| ", end = "")
        # print(f"\tHVA 0x{hva:<16x} --> {host_vmr_id}")
        mapping_graph.add_map_edge_raw(g_mo_id, host_mo_id, "VMM PD")
        mapping_graph.add_map_edge_raw(g_mo_id, host_vmr_id, "VMM PD")
    print("\033[91mXXX: Add Resource Space Map Edge\033[0m")
    print("\033[95mXXX: Add Request Edge from guest to host kernel\033[0m")


    # Add a Request Fault edge Guest Linux to VMM
    mapping_graph.add_request_edge_raw("PD_10001", "PD_1", "PD_1")
    mapping_graph.to_csv(g2h_file, only_edge=True)

# Force rootful Docker daemon for all vm_model docker calls (avoids rootless context
# being picked up when sudo -E preserves HOME pointing to the user's docker config).
_DOCKER_ENV = {**os.environ, "DOCKER_HOST": "unix:///var/run/docker.sock"}


def _find_pfs_lib() -> str:
    """Search for the pypfs .so library directory."""
    candidates = [
        os.path.expanduser("~/proc/pfs/lib"),
        os.path.join(os.path.dirname(__file__), "pfs", "lib"),
    ]
    for c in candidates:
        if os.path.isdir(c) and any(f.endswith(".so") for f in os.listdir(c)):
            return c
    raise FileNotFoundError("pypfs library not found; set PYTHONPATH or place it under ~/proc/pfs/lib")


# ---------------------------------------------------------------------------
# Shared CSV helpers
# ---------------------------------------------------------------------------

def _build_gpa_to_mo(guest_file: str) -> dict:
    """Parse guest CSV: return mapping of GPA (int) → guest MO node ID (str)."""
    gPA_to_MO = {}
    with open(guest_file, mode='r', newline='') as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            if row[0] == "RESOURCE" and row[1].startswith("MO_") and row[-1]:
                extra = json.loads(row[-1])
                gpa = int(extra["pa"], 16)
                if gpa in gPA_to_MO:
                    raise KeyError(f"Duplicate GPA key 0x{gpa:x} in guest CSV")
                gPA_to_MO[gpa] = row[1]
    return gPA_to_MO


def _build_host_maps(host_file: str) -> tuple:
    """Parse host CSV: return (hPA_to_MO, hVA_to_VMR) lookup dicts."""
    hPA_to_MO = {}
    hVA_to_VMR = {}
    with open(host_file, mode='r', newline='') as f:
        for row in csv.reader(f):
            if len(row) < 2 or row[0] != "RESOURCE":
                continue
            if not (row[1].startswith("MO_") or row[1].startswith("VMR_")):
                continue
            if not row[-1] or not row[-1].startswith("{"):
                continue
            extra = json.loads(row[-1])
            if row[1].startswith("MO_") and extra.get("num_pages", "0") != "0":
                hpa = int(extra["pa"], 16)
                if hpa in hPA_to_MO:
                    raise KeyError(f"Duplicate HPA key 0x{hpa:x} in host CSV")
                hPA_to_MO[hpa] = row[1]
            elif row[1].startswith("VMR_") and extra.get("num_pages", "0") != "0":
                hva = int(extra["va"], 16)
                if hva in hVA_to_VMR:
                    raise KeyError(f"Duplicate HVA key 0x{hva:x} in host CSV")
                hVA_to_VMR[hva] = row[1]
    print(f"hPA_to_MO has {len(hPA_to_MO)} entries")
    print(f"hVA_to_VMR has {len(hVA_to_VMR)} entries")
    return hPA_to_MO, hVA_to_VMR


def _docker_tar_push(container_name: str, src_dir: str, dest_dir: str):
    """Push a directory into a container via tar pipe (works with gVisor, docker cp does not)."""
    import subprocess
    # -h: dereference symlinks so that symlinked .so files arrive as real files
    tar_out = subprocess.Popen(
        ["tar", "-hC", src_dir, "-cf", "-", "."],
        stdout=subprocess.PIPE)
    tar_in = subprocess.Popen(
        ["docker", "exec", "-i", container_name,
         "tar", "-C", dest_dir, "-xf", "-"],
        stdin=tar_out.stdout, env=_DOCKER_ENV)
    tar_out.stdout.close()
    tar_in.communicate()
    tar_out.wait()
    if tar_in.returncode != 0:
        raise RuntimeError(f"tar push into {container_name}:{dest_dir} failed")


def _docker_tar_pull(container_name: str, src_path: str, dest_path: str):
    """Pull a single file out of a container via tar pipe (works with gVisor)."""
    import subprocess, tempfile, shutil
    dest_dir = os.path.dirname(dest_path)
    fname = os.path.basename(src_path)
    src_dir = os.path.dirname(src_path)
    tar_out = subprocess.Popen(
        ["docker", "exec", "-i", container_name,
         "tar", "-C", src_dir, "-cf", "-", fname],
        stdout=subprocess.PIPE, env=_DOCKER_ENV)
    with tempfile.TemporaryDirectory() as tmp:
        tar_in = subprocess.Popen(
            ["tar", "-C", tmp, "-xf", "-"],
            stdin=tar_out.stdout)
        tar_out.stdout.close()
        tar_in.communicate()
        tar_out.wait()
        if tar_in.returncode != 0:
            raise RuntimeError(f"tar pull of {container_name}:{src_path} failed")
        shutil.copy(os.path.join(tmp, fname), dest_path)


def _push_and_run_proc_model(container_name: str, guest_file: str):
    """Push proc_model.py + pypfs into a container, run it, pull guest CSV out.

    Uses tar pipes instead of docker cp — docker cp bypasses the Sentry and
    fails for gVisor containers; tar-via-docker-exec works for all runtimes.
    """
    import subprocess, tempfile, re, shutil
    pfs_lib = _find_pfs_lib()
    proc_dir = os.path.dirname(os.path.abspath(__file__))

    # Detect the Python version required by the pypfs .so (e.g. cpython-312 → "python3.12")
    so_files = [f for f in os.listdir(pfs_lib) if f.endswith(".so")]
    m = re.search(r"cpython-(\d)(\d+)", so_files[0]) if so_files else None
    if m:
        py_maj, py_min = m.group(1), m.group(2)
        py_cmd = f"python{py_maj}.{py_min}"   # e.g. "python3.12"
        py_ver = f"{py_maj}.{py_min}"
    else:
        py_cmd, py_ver = "python3", None

    # Create destination dirs inside the container
    subprocess.check_call(
        ["docker", "exec", container_name, "mkdir", "-p",
         "/tmp/lintool/pfs/lib", "/tmp/lintool"], env=_DOCKER_ENV)

    # Push pypfs .so library
    _docker_tar_push(container_name, pfs_lib, "/tmp/lintool/pfs/lib")

    # Push proc_model.py and supporting modules
    py_files = ["proc_model.py", "procfs_data.py", "generic_model.py",
                "utils.py", "read_pagemap.py", "get_ns_info.py"]
    with tempfile.TemporaryDirectory() as staging:
        for f in py_files:
            src = os.path.join(proc_dir, f)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(staging, f))
        _docker_tar_push(container_name, staging, "/tmp/lintool")

    # Ensure the right Python version + required packages are available.
    # The pypfs .so encodes the ABI version (e.g. cpython-312); we must run
    # proc_model.py with that exact interpreter version.
    # Install packages to /tmp/py-pkgs (--target) to isolate from system
    # site-packages — avoids ABI conflicts when the container has an older Python.
    pkgs_dir = f"/tmp/py{py_ver.replace('.', '')}-pkgs" if py_ver else "/tmp/py-pkgs"
    r = subprocess.run(
        ["docker", "exec", container_name, "sh", "-c",
         f"PYTHONPATH={pkgs_dir} {py_cmd} -c 'import networkx, psutil, pexpect'"],
        env=_DOCKER_ENV, capture_output=True)
    if r.returncode != 0:
        print(f"[vm_model] Installing {py_cmd} + deps in {container_name}...")
        if py_ver and py_ver != "3":
            # Strategy: try system repos first (works on ubuntu:24.04 where python3.12
            # is in main); fall back to deadsnakes PPA only if needed (ubuntu:22.04).
            # libstdc++6 upgrade: pypfs requires GLIBCXX_3.4.32; ubuntu:22.04 ships
            # GCC 12 (3.4.30) so we upgrade via toolchain PPA if available.
            # DEBIAN_FRONTEND=noninteractive: prevents tzdata interactive prompt.
            install_script = (
                "export DEBIAN_FRONTEND=noninteractive && "
                # apt-get update: retry and tolerate partial mirror failures (e.g. in gVisor)
                "( apt-get -o Acquire::Retries=3 update -qq 2>/dev/null || true ) && "
                # curl: best-effort only (fallback for pip bootstrap; ubuntu:24.04 has ensurepip)
                "( apt-get install -y -qq --fix-missing curl 2>/dev/null || true ) && "
                # Try system repos; if python3.X is not there, add deadsnakes PPA
                f"( apt-get install -y -qq --fix-missing python{py_ver} 2>/dev/null || "
                f"  ( apt-get install -y -qq --fix-missing software-properties-common && "
                f"    add-apt-repository -y ppa:deadsnakes/ppa && "
                f"    ( apt-get -o Acquire::Retries=3 update -qq 2>/dev/null || true ) && "
                f"    apt-get install -y -qq python{py_ver} ) ) && "
                # Upgrade libstdc++ if the toolchain PPA is reachable (best-effort)
                "( apt-get install -y -qq software-properties-common 2>/dev/null && "
                "  add-apt-repository -y ppa:ubuntu-toolchain-r/test 2>/dev/null && "
                "  ( apt-get -o Acquire::Retries=3 update -qq 2>/dev/null || true ) && "
                "  apt-get install -y -qq libstdc++6 2>/dev/null ) || true && "
                # Bootstrap pip if not present, then install packages to isolated dir
                f"( python{py_ver} -m ensurepip --upgrade 2>/dev/null || "
                f"  ( curl -s https://bootstrap.pypa.io/get-pip.py | python{py_ver} ) ) && "
                f"python{py_ver} -m pip install --target {pkgs_dir} --break-system-packages --quiet networkx psutil pexpect"
            )
        else:
            install_script = (
                "export DEBIAN_FRONTEND=noninteractive && "
                "apt-get update -qq && "
                "apt-get install -y -qq python3 python3-networkx python3-psutil"
            )
        subprocess.check_call(
            ["docker", "exec", container_name, "sh", "-c", install_script],
            env=_DOCKER_ENV)

    # Run proc_model.py inside the container
    subprocess.check_call([
        "docker", "exec",
        "-e", f"PYTHONPATH={pkgs_dir}:/tmp/lintool/pfs/lib",
        container_name,
        py_cmd, "/tmp/lintool/proc_model.py",
        "--os", "linux", "--csv", "/tmp/guest.csv", "-g", "--pid", "0"
    ], env=_DOCKER_ENV)

    # Pull the CSV back out via tar
    _docker_tar_pull(container_name, "/tmp/guest.csv", guest_file)


# ---------------------------------------------------------------------------
# QMP client helpers (for Kata)
# ---------------------------------------------------------------------------

def _qmp_connect(sock_path: str):
    """Open QMP Unix socket, perform capabilities handshake, return connected socket."""
    import socket as _socket
    s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    s.connect(sock_path)
    s.settimeout(10.0)
    greeting = json.loads(s.recv(4096))
    assert "QMP" in greeting, f"Unexpected QMP greeting: {greeting}"
    s.sendall(b'{"execute": "qmp_capabilities"}\n')
    json.loads(s.recv(4096))  # expect {"return": {}}
    return s


def _qmp_hmp_command(s, cmd: str) -> str:
    """Send a Human Monitor Protocol (HMP) command via QMP; return the text response."""
    payload = json.dumps({
        "execute": "human-monitor-command",
        "arguments": {"command-line": cmd}
    }) + "\n"
    s.sendall(payload.encode())
    return json.loads(s.recv(4096)).get("return", "")


def _qmp_translate_gpa(s, gpa: int) -> tuple:
    """Translate GPA → (HPA, HVA) via QMP gpa2hpa/gpa2hva. Returns (None, None) on failure."""
    def _parse(text):
        for ln in text.splitlines():
            if f"address for 0x{gpa:x}" in ln:
                return int(ln.split()[-1], 16)
        return None
    hpa = _parse(_qmp_hmp_command(s, f"gpa2hpa 0x{gpa:x}"))
    hva = _parse(_qmp_hmp_command(s, f"gpa2hva 0x{gpa:x}"))
    return hpa, hva


def _kata_qmp_sock(container_name: str) -> str | None:
    """Return the QMP socket path for the kata container, or None if not found."""
    import subprocess, glob
    full_id = subprocess.check_output(
        ["docker", "inspect", "--format", "{{.Id}}", container_name],
        text=True, env=_DOCKER_ENV).strip()
    direct = f"/run/vc/vm/{full_id}/qmp.sock"
    if os.path.exists(direct):
        return direct
    for sock in glob.glob("/run/vc/vm/*/qmp.sock"):
        sandbox_id = os.path.basename(os.path.dirname(sock))
        if full_id.startswith(sandbox_id) or sandbox_id.startswith(full_id[:12]):
            return sock
    return None


def _try_kata_g2h_mapping(container_name: str, guest_file: str,
                           host_file: str, g2h_file: str):
    """
    GPA→HPA translation using kata's QEMU QMP socket at /run/vc/vm/<sandbox_id>/qmp.sock.
    Writes empty g2h_file if QMP socket is not accessible.
    """
    mapping_graph = gm.ModelGraph(id_offset=10000*10000)

    sock_path = _kata_qmp_sock(container_name)
    if sock_path is None:
        print(f"[kata] QMP socket not found for container '{container_name}'; writing empty g2h")
        mapping_graph.to_csv(g2h_file, only_edge=True)
        return

    gPA_to_MO = _build_gpa_to_mo(guest_file)
    hPA_to_MO, hVA_to_VMR = _build_host_maps(host_file)

    print(f"[kata] Connecting to QMP socket: {sock_path}")
    s = _qmp_connect(sock_path)
    start_time = time.time()
    matched = 0
    for gpa, g_mo_id in gPA_to_MO.items():
        hpa, hva = _qmp_translate_gpa(s, gpa)
        host_mo_id  = hPA_to_MO.get(hpa)  if hpa is not None else None
        host_vmr_id = hVA_to_VMR.get(hva) if hva is not None else None
        if host_mo_id:
            mapping_graph.add_map_edge_raw(g_mo_id, host_mo_id,  "QEMU_PD")
            matched += 1
        if host_vmr_id:
            mapping_graph.add_map_edge_raw(g_mo_id, host_vmr_id, "QEMU_PD")
    s.close()
    print(f"[kata] QMP translation: {time.time() - start_time:.1f}s; "
          f"{matched}/{len(gPA_to_MO)} GPAs matched to host MOs")
    mapping_graph.to_csv(g2h_file, only_edge=True)


def get_kata_vm_state(container_name: str, guest_file: str,
                      host_file: str, g2h_file: str):
    """
    Extract two-level model state for a running kata container.
    - guest_file: proc_model output from INSIDE the kata VM (via docker exec)
    - host_file:  proc_model output of the QEMU process on the host
    - g2h_file:   GPA→HPA mapping edges via kata's QMP socket
    """
    import subprocess

    # 1. Get the QEMU PID on the host
    inspect = json.loads(
        subprocess.check_output(["docker", "inspect", container_name],
                                text=True, env=_DOCKER_ENV))
    qemu_pid = inspect[0]["State"]["Pid"]
    assert qemu_pid != 0, "kata container QEMU PID is 0 — container not running?"

    # 2. Extract host QEMU state
    get_host_state(qemu_pid, host_file=host_file)

    # 3. Push proc_model.py into the kata VM and run it
    _push_and_run_proc_model(container_name, guest_file)

    # 4. Memory address translation via QMP
    _try_kata_g2h_mapping(container_name, guest_file, host_file, g2h_file)


# ---------------------------------------------------------------------------
# gVisor helpers
# ---------------------------------------------------------------------------

def _gvisor_is_kvm_mode(sentry_pid: int) -> bool:
    """Return True if the gVisor Sentry is running in KVM mode (has kvm-vm fd)."""
    with open(f"/proc/{sentry_pid}/maps") as f:
        return any("anon_inode:kvm-vm" in line for line in f)


def _gvisor_memfd_base(sentry_pid: int) -> int:
    """Return the host VA of the start of memfd:runsc-memory in the Sentry's address space."""
    with open(f"/proc/{sentry_pid}/maps") as f:
        for line in f:
            if "/memfd:runsc-memory" in line:
                return int(line.split("-")[0], 16)
    raise RuntimeError(f"memfd:runsc-memory not found in /proc/{sentry_pid}/maps")


def _hva_to_hpa(pid: int, hva: int):
    """Translate a host virtual address to a host physical address via /proc/pid/pagemap."""
    from read_pagemap import PAMap
    try:
        return PAMap(pid=str(pid)).pa(hva)
    except Exception:
        return None


def get_gvisor_vm_state(container_name: str, guest_file: str,
                         host_file: str, g2h_file: str):
    """
    Extract two-level model state for a running gVisor container.

    gVisor backs guest physical memory with a single memfd:runsc-memory mapping.
    Translation is arithmetic: host_VA = memfd_base_VA + guest_PA. No QMP needed.

    - guest_file: proc_model output from INSIDE the gVisor sandbox (via docker exec)
    - host_file:  proc_model output of the Sentry process on the host
    - g2h_file:   bridge MAP edges from guest MOs to host MOs/VMRs
    """
    import subprocess

    # 1. Get the Sentry PID
    sentry_pid = int(subprocess.check_output(
        ["docker", "inspect", "--format", "{{.State.Pid}}", container_name],
        text=True, env=_DOCKER_ENV).strip())
    assert sentry_pid != 0, "gVisor Sentry PID is 0 — container not running?"
    print(f"[gVisor] Sentry PID: {sentry_pid}")

    # 2. Extract host Sentry state
    get_host_state(sentry_pid, host_file=host_file)

    # 3. Push proc_model.py into the gVisor sandbox and run it
    _push_and_run_proc_model(container_name, guest_file)

    # 4. Parse both CSVs
    gPA_to_MO = _build_gpa_to_mo(guest_file)
    hPA_to_MO, hVA_to_VMR = _build_host_maps(host_file)

    # 5. Bridge edges via memfd offset arithmetic
    mapping_graph = gm.ModelGraph(id_offset=10000*10000)
    memfd_base = _gvisor_memfd_base(sentry_pid)
    kvm_mode = _gvisor_is_kvm_mode(sentry_pid)
    mode_str = "KVM" if kvm_mode else "ptrace"
    print(f"[gVisor] {mode_str} mode; memfd base VA: 0x{memfd_base:x}")

    start_time = time.time()
    for gpa, g_mo_id in gPA_to_MO.items():
        hva = memfd_base + gpa
        host_vmr_id = hVA_to_VMR.get(hva)
        # Per-page MO matching via host pagemap (skip in KVM mode to avoid ---p hang
        # if the pagemap fix is not yet applied, or if the Sentry maps huge regions)
        host_mo_id = None
        if not kvm_mode:
            hpa = _hva_to_hpa(sentry_pid, hva)
            host_mo_id = hPA_to_MO.get(hpa) if hpa is not None else None
        if host_vmr_id:
            mapping_graph.add_map_edge_raw(g_mo_id, host_vmr_id, "gVisor_Sentry")
        if host_mo_id:
            mapping_graph.add_map_edge_raw(g_mo_id, host_mo_id,  "gVisor_Sentry")

    print(f"[gVisor] address translation took {time.time() - start_time:.1f}s "
          f"({len(gPA_to_MO)} guest MOs)")
    mapping_graph.to_csv(g2h_file, only_edge=True)


# ---------------------------------------------------------------------------
# Firecracker two-level extraction
# ---------------------------------------------------------------------------

class _UnixSocketHTTP(http.client.HTTPConnection):
    """HTTPConnection that connects over a Unix-domain socket."""
    def __init__(self, sock_path: str):
        super().__init__("localhost")
        self._sock_path = sock_path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self._sock_path)
        self.sock = s


def _fc_api_put(sock_path: str, path: str, body: dict) -> dict:
    """PUT a JSON body to Firecracker's REST API via a unix socket."""
    conn = _UnixSocketHTTP(sock_path)
    payload = json.dumps(body).encode()
    conn.request("PUT", path, body=payload,
                 headers={"Content-Type": "application/json",
                          "Accept": "application/json"})
    resp = conn.getresponse()
    text = resp.read().decode()
    if resp.status not in (200, 204):
        raise RuntimeError(f"FC API PUT {path} → {resp.status}: {text}")
    return json.loads(text) if text.strip() else {}


def _fc_guest_ram_base(fc_pid: int, mem_mib: int) -> int:
    """Find host VA of guest physical address 0 inside a running FC process.

    FC maps guest RAM as a single anonymous rw-p mmap of exactly mem_mib MiB.
    In /proc/maps this appears as a 5-field line (no pathname) with inode 0.
    """
    target_size = mem_mib * 1024 * 1024
    with open(f"/proc/{fc_pid}/maps") as f:
        for line in f:
            parts = line.split()
            # Anonymous mappings have 5 fields: addr-range perms offset dev inode
            if len(parts) != 5:
                continue
            start, end = [int(x, 16) for x in parts[0].split("-")]
            perms, offset, inode = parts[1], parts[2], parts[4]
            if (end - start == target_size and perms == "rw-p"
                    and offset == "00000000" and inode == "0"):
                return start
    raise RuntimeError(
        f"FC guest RAM ({mem_mib} MiB) anonymous mmap not found in "
        f"/proc/{fc_pid}/maps")


def get_firecracker_vm_state(
    kernel: str, rootfs: str,
    guest_file: str, host_file: str, g2h_file: str,
    mem_mib: int = 256, vcpus: int = 2,
    mount_point: str = "/mnt/fc-guest-extract",
) -> None:
    """
    Two-level extraction for a Firecracker microVM.

    Steps:
      1. Launch FC via pexpect (pty = serial console).
      2. Configure + boot via REST API.
      3. Wait for login on serial console (--autologin root).
      4. Extract host FC process state.
      5. Run proc_model.py inside the guest via serial console.
      6. Graceful shutdown; mount rootfs; extract guest.csv.
      7. Build GPA→HPA bridge (anonymous mmap arithmetic).
    """
    import subprocess

    sock_path = f"/tmp/osmosis-fc-{os.getpid()}.sock"

    # --- Step 1: launch FC (pty becomes serial console) ---
    fc = pexpect.spawn(
        f"firecracker --api-sock {sock_path}",
        timeout=60, encoding="utf-8",
        codec_errors="replace",
    )
    time.sleep(0.3)  # let FC open the API socket

    # --- Step 2: configure via REST API ---
    _fc_api_put(sock_path, "/boot-source", {
        "kernel_image_path": kernel,
        "boot_args": (
            "console=ttyS0 reboot=k panic=1 pci=off nomodules "
            "root=/dev/vda rw"
        ),
    })
    _fc_api_put(sock_path, "/machine-config",
                {"vcpu_count": vcpus, "mem_size_mib": mem_mib})
    _fc_api_put(sock_path, "/drives/rootfs", {
        "drive_id": "rootfs",
        "path_on_host": rootfs,
        "is_root_device": True,
        "is_read_only": False,
    })
    _fc_api_put(sock_path, "/actions", {"action_type": "InstanceStart"})

    # --- Step 3: wait for login prompt (autologin or manual login) ---
    idx = fc.expect(["# ", r"\$ ", "login:", "Password:"], timeout=60)
    if idx == 2:  # "login:" prompt
        fc.sendline("root")
        idx2 = fc.expect(["# ", r"\$ ", "Password:"], timeout=15)
        if idx2 == 2:  # password prompt
            fc.sendline("root")
            fc.expect(["# ", r"\$ "], timeout=15)
    elif idx == 3:  # autologin sent password prompt directly
        fc.sendline("root")
        fc.expect(["# ", r"\$ "], timeout=15)

    # --- Step 4: host FC state (while FC process is still alive) ---
    fc_pid = fc.pid
    print(f"[FC] VMM PID: {fc_pid}")
    get_host_state(fc_pid, host_file=host_file)

    # Read guest RAM base VA from host process maps while FC is still running
    ram_base = _fc_guest_ram_base(fc_pid, mem_mib)
    print(f"[FC] guest RAM base VA: 0x{ram_base:x}")

    # --- Step 5: run proc_model.py inside the guest ---
    guest_csv_in_vm = "/root/guest.csv"
    py_cmd = "PYTHONPATH=/root/lintool-pkgs:/root/lintool/pfs/lib python3.12"
    fc.sendline(
        f"{py_cmd} /root/lintool/proc_model.py "
        f"--os linux --csv {guest_csv_in_vm} -g --pid 0"
    )
    fc.expect("# ", timeout=300)

    # --- Step 6: graceful shutdown, mount rootfs, extract CSV ---
    fc.sendline("reboot")
    try:
        fc.expect(pexpect.EOF, timeout=20)
    except pexpect.TIMEOUT:
        fc.terminate(force=True)

    os.makedirs(mount_point, exist_ok=True)
    subprocess.check_call(
        ["mount", "-o", "loop,rw", rootfs, mount_point])
    try:
        src = os.path.join(mount_point, guest_csv_in_vm.lstrip("/"))
        _shutil.copy2(src, guest_file)
    finally:
        subprocess.check_call(["umount", mount_point])

    # --- Step 7: GPA→HPA bridge via anonymous mmap arithmetic ---
    gPA_to_MO = _build_gpa_to_mo(guest_file)
    hPA_to_MO, hVA_to_VMR = _build_host_maps(host_file)

    mapping_graph = gm.ModelGraph(id_offset=10000 * 10000)
    start_time = time.time()
    matched = 0
    for gpa, g_mo_id in gPA_to_MO.items():
        hva = ram_base + gpa
        host_vmr_id = hVA_to_VMR.get(hva)
        host_mo_id  = hPA_to_MO.get(_hva_to_hpa(fc_pid, hva))
        if host_vmr_id:
            mapping_graph.add_map_edge_raw(g_mo_id, host_vmr_id, "FC_mmap")
            matched += 1
        if host_mo_id:
            mapping_graph.add_map_edge_raw(g_mo_id, host_mo_id, "FC_mmap")

    print(f"[FC] address translation took {time.time()-start_time:.1f}s "
          f"({matched}/{len(gPA_to_MO)} guest MOs matched)")
    mapping_graph.to_csv(g2h_file, only_edge=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extract the model state from the Qemu guest and merge it with the model state"
        "for the Qemu process from the host"
    )

    # parser.add_argument(
    #     "--guest",
    #     type=str,
    #     default="./outputs/qemu-86/guest.csv",
    #     help="Output file with guest's OSmosis model state",
    # )
    # parser.add_argument(
    #     "--g2h",
    #     type=str,
    #     default="./outputs/qemu-86/g2h.csv",
    #     help="Output file with guest to host memory mappings",
    # )
    # parser.add_argument(
    #     "--host",
    #     type=str,
    #     default="./outputs/qemu-86/host.csv",
    #     help="Output file with host's OSmosis model state",
    # )
    parser.add_argument(
        "--vmm",
        type=str,
        choices=["qemu-x86", "cellulos", "kata", "gvisor", "firecracker"],
        required=True,
        help="Qemu, CellulOS(on Qemu), Kata, gVisor, or Firecracker as the VMM"
    )
    parser.add_argument(
        "--container",
        type=str,
        default=None,
        help="Container name for --vmm kata/gvisor (e.g. osmosis-kata-app)"
    )
    parser.add_argument(
        "--kernel",
        type=str,
        default="/usr/local/share/firecracker/vmlinux.bin",
        help="Path to vmlinux kernel image (for --vmm firecracker)",
    )
    parser.add_argument(
        "--rootfs",
        type=str,
        default="/usr/local/share/firecracker/rootfs-noble.ext4",
        help="Path to ext4 rootfs image (for --vmm firecracker)",
    )
    parser.add_argument(
        "--clean",
        action='store_true',
        default=False,
        help="Clean old data of that vmm time"
    )
    parser.add_argument(
        "-l",
        "--load-csv",
        default=False,
        action='store_true',
        help="Import to the neo4j running on the same machine",
    )
    args = parser.parse_args()

    target_dir = f"./outputs/{args.vmm}/"
    if args.clean:
        print(f"Deleteing old data in {target_dir}", end ="")
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print (item_path, end="")
        print("")


    new_dir = os.path.join(target_dir,
                           datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S"))
    os.makedirs(new_dir)
    host_file = f"{new_dir}/host.csv"
    guest_file = f"{new_dir}/guest.csv"
    g2h_file = f"{new_dir}/g2h_file.csv"

    if args.vmm == "qemu-x86":
        assert is_root()
        assert is_qemu_x86_buildroot_updated()
        get_qemu_vm_state(
            get_host=True, guest_file=guest_file, g2h_file=g2h_file, host_file=host_file
        )
    elif args.vmm == "cellulos":
        assert is_cellulos_aarch64_buildroot_osm_dir_updated()
        get_cellulos_vm_state(
            get_host=True, guest_file=guest_file, g2h_file=g2h_file, host_file=host_file
        )
    elif args.vmm == "kata":
        assert is_root(), "kata extraction requires root"
        assert args.container, "--container required for --vmm kata"
        get_kata_vm_state(args.container, guest_file, host_file, g2h_file)
    elif args.vmm == "gvisor":
        assert is_root(), "gVisor extraction requires root"
        assert args.container, "--container required for --vmm gvisor"
        get_gvisor_vm_state(args.container, guest_file, host_file, g2h_file)
    elif args.vmm == "firecracker":
        assert is_root(), "Firecracker extraction requires root"
        get_firecracker_vm_state(
            kernel=args.kernel,
            rootfs=args.rootfs,
            guest_file=guest_file,
            host_file=host_file,
            g2h_file=g2h_file,
        )
    else:
        raise ValueError("Invalid VMM")

    if args.load_csv:
        files = [guest_file, host_file, g2h_file]
        print(f"Uploading {files} to neo4j")
        upload_csv_import("neo4j", files)

if __name__ == "__main__":
    main()
