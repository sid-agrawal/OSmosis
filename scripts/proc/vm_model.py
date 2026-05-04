#!/bin/python3

import pexpect
import csv
import os
import time
import json
import argparse
import traceback
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
            if len(row) < 2 or row[0] != "RESOURCE" or not row[-1]:
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


def _push_and_run_proc_model(container_name: str, guest_file: str):
    """Push proc_model.py + pypfs into a container, run it, copy guest CSV out."""
    import subprocess
    pfs_lib = _find_pfs_lib()
    proc_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.check_call(
        ["docker", "exec", container_name, "mkdir", "-p",
         "/tmp/lintool/pfs/lib", "/tmp/lintool"])
    subprocess.check_call(
        ["docker", "cp", pfs_lib + "/.", f"{container_name}:/tmp/lintool/pfs/lib/"])
    for f in ["proc_model.py", "procfs_data.py", "generic_model.py",
              "utils.py", "read_pagemap.py", "get_ns_info.py"]:
        src = os.path.join(proc_dir, f)
        if os.path.exists(src):
            subprocess.check_call(["docker", "cp", src,
                                   f"{container_name}:/tmp/lintool/{f}"])
    subprocess.check_call([
        "docker", "exec",
        "-e", "PYTHONPATH=/tmp/lintool/pfs/lib",
        container_name,
        "python3", "/tmp/lintool/proc_model.py",
        "--os", "linux", "--csv", "/tmp/guest.csv", "-g", "--pid", "0"
    ])
    subprocess.check_call(
        ["docker", "cp", f"{container_name}:/tmp/guest.csv", guest_file])


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
        text=True).strip()
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
        subprocess.check_output(["docker", "inspect", container_name], text=True))
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
        text=True).strip())
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
        choices=["qemu-x86", "cellulos", "kata", "gvisor"],
        required=True,
        help="Qemu, CellulOS(on Qemu), Kata, or gVisor as the VMM"
    )
    parser.add_argument(
        "--container",
        type=str,
        default=None,
        help="Container name for --vmm kata/gvisor (e.g. osmosis-kata-app)"
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
    else:
        raise ValueError("Invalid VMM")

    if args.load_csv:
        files = [guest_file, host_file, g2h_file]
        print(f"Uploading {files} to neo4j")
        upload_csv_import("neo4j", files)

if __name__ == "__main__":
    main()
