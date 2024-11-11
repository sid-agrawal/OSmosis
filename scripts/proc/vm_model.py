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
    dir2 = os.path.expanduser('~/buildroot/cellulos/qemu/buildroot-arm-cellulos-with-everything/output/target/root/proc')

    assert compare_directories(dir1, dir2, file_extension=".py", 
                               exceptions=["vm_model.py", "import_csv.py", "passthrough.py"])
    
    osm_rootfs = os.path.expanduser("~/OSmosis/projects/sel4-gpi/apps/vmm/board/qemu_arm_virt/rootfs.cpio.gz")
    built_rootfs = os.path.expanduser('~/buildroot/cellulos/qemu/buildroot-arm-cellulos-with-everything/output/images/rootfs.cpio.gz')
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
                               exceptions=["vm_model.py", "import_csv.py"])


def get_cellulos_vm_state(get_host: bool, guest_file: str, g2h_file: str, host_file: str):
    """
        Start Cellulos-VMM based linux guest and get the :
        - model state of the VM as seen from the host
        - model state of the hello process inside the guest
        - mappings between gpa --> hpa, and gpa --> hva
    """

    original_dir = os.getcwd()
    try: 
        os.chdir("/home/" + os.getlogin() + "/OSmosis/qemu-build/")
        # Build the OSM VM Test
        run(
            [
                "cmake",
                ".",
                "-DLibSel4TestPrinterRegex=GPIVM004",
                "-DGPIExtractModel=ON",
                "-DGPIVMMImplementation=osm-vmm",
            ]
        )
        run(["ninja"])

        # Run the VMM004 test
        sim_cmd = ("./simulate")
        sim_phandle, host_csv = get_cellulos_phandle(sim_cmd)

        # Run the process, inside the guest.
        sim_phandle.sendline("python proc_model.py --os linux --csv ./hello.csv -g")
        sim_phandle.expect("#", timeout=120)
        sim_phandle.sendline("cat ./hello.csv")
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

                # Super Hacky
                elif row_id.startswith("VMR_9"):
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
        host_mo_id = hPA_to_MO.get(hpa)

        # print(f"Adding Edges for 0x{gpa:<16x} || ", end = "")
        # print(f"\tHPA 0x{hpa:<16x} --> {host_mo_id} |||| ", end = "")
        # print(f"\tHVA 0x{hva:<16x} --> {host_vmr_id}")
        mapping_graph.add_map_edge_raw(g_mo_id, host_mo_id, "VMM PD")
        mapping_graph.add_map_edge_raw(g_mo_id, host_vmr_id, "VMM PD")
    print("\033[91mXXX: Add Resource Space Map Edge\033[0m")
    print("\033[95mXXX: Add Request Edge from guest to host kernel\033[0m")

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
        choices=["qemu-x86", "cellulos"],
        required=True,
        help="Qemu or CellulOS(on Qemu) as the VMM "
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
    elif  args.vmm == "cellulos":
        assert is_cellulos_aarch64_buildroot_osm_dir_updated()
        get_cellulos_vm_state(
            get_host=True, guest_file=guest_file, g2h_file=g2h_file, host_file=host_file
        )
    else: 
        raise ValueError("Invalid VMM")

    if args.load_csv:
        files = [guest_file, host_file, g2h_file]
        print(f"Uploading {files} to neo4j")
        upload_csv_import("neo4j", files)

if __name__ == "__main__":
    main()
