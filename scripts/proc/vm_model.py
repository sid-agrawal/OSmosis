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
from utils import sizeof_fmt, compare_directories, is_root
import generic_model as gm
import pprint as pp
from qemu_expect import get_qemu_phandle

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


def get_vm_state(get_host: bool, guest_file: str, g2h_file: str, host_file: str):
    """
        Start Qemu based linux guest and get the :
        - model state of the hello process inside the guest
        - model state of the qemu process on the host
        - mappings between gpa --> hpa, and gpa --> hva
    """

    # Start Qemu
    qemu_cmd = (
        "/home/" + os.getlogin() + "/buildroot/qemu/buildroot-x86/start-qemu-kvm.sh"
    )
    qemu_phandle = get_qemu_phandle(qemu_cmd)
    qemu_phandle.sendline("python proc_model.py --csv ./hello.csv --id-offset 100000")
    qemu_phandle.expect("#")
    qemu_phandle.sendline("cat ./hello.csv")
    qemu_phandle.expect("#")
    hello_csv = qemu_phandle.before.decode()

    # Dump the model state of the guest (i.e. just hello process) 
    # guest_file
    with open(guest_file, "w") as out_file:
        for ln in hello_csv.splitlines():
            if "," in ln:
                print(ln, file=out_file)

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
        mapping_graph.add_map_edge_raw(g_mo_id, host_mo_id)
        mapping_graph.add_map_edge_raw(g_mo_id, host_vmr_id)
    
    end_time = time.time()
    print(f"Monitor Queries took:  {end_time - start_time} seconds")


    mapping_graph.to_csv(g2h_file)
    print (f"Generated {len(gPA_to_MO)*2} new mapping edges")

    # print the interactions with the child
    # process.
    # qemu_phandle.interact()



def main():
    parser = argparse.ArgumentParser(
        description="Extract the model state from the Qemu guest and merge it with the model state"
        "for the Qemu process from the host"
    )

    parser.add_argument(
        "--guest",
        type=str,
        default="./outputs/qemu-86/guest.csv",
        help="Output file with guest's OSmosis model state",
    )
    parser.add_argument(
        "--g2h",
        type=str,
        default="./outputs/qemu-86/g2h.csv",
        help="Output file with guest to host memory mappings",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="./outputs/qemu-86/host.csv",
        help="Output file with host's OSmosis model state",
    )
    args = parser.parse_args()

    get_vm_state(
        get_host=True, guest_file=args.guest, g2h_file=args.g2h, host_file=args.host
    )


def get_host_state(vm_pid: int, host_file: str):

    print (f"Get /proc state for PID: {vm_pid}")

    data = ProcFsData()
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


def is_buildroot_updated():
    """
    When getting state from inside the vm guest, we need to ensure that the python files
    inside buildroot are up to date.
    """
    dir1 = os.path.expanduser('~/OSmosis/scripts/proc')
    dir2 = os.path.expanduser('~/buildroot/qemu/buildroot-x86/output/target/root/proc')

    assert compare_directories(dir1, dir2, file_extension=".py", exceptions=["vm_model.py"])

if __name__ == "__main__":
    assert is_root()
    is_buildroot_updated()
    main()
