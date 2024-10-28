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
from proc_utils import convert_iomem_to_RAMranges
from utils import sizeof_fmt
import generic_model as gm

username = os.getlogin()
qemu_cmd = "sudo /home/" + username + "/buildroot/qemu/buildroot-x86/start-qemu-kvm.sh"


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
        get the host-VA, host-PA.

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
        for ln in output.splitlines():
            if f"address for 0x{addr:x}" in ln:
                ln = ln.split(" ")
                return int(ln[-1], 16)
            elif "No memory is mapped at" in ln:
                raise ValueError(f"No memory found at 0x{addr}, output : {ln}")

    return parse(output)

    # Get RAM Ranges of Guest
    # For each page in gPA get its hPA and hVA
    # ??


def get_vm_state(get_host: bool, guest_file: str, g2h_file: str, host_file: str):

    # spawn a child process.
    phandle = pexpect.spawn(qemu_cmd)
    print("CHILD PID: ", phandle.pid)
    
    # search for the Name pattern.
    phandle.expect("buildroot login:")
    phandle.sendline("root")
    phandle.expect("#")

    # send the username with sendline
    phandle.sendline("cd /root/proc")
    phandle.expect("#")

    # gpa2hva, gpa2hpa = get_guest_host_mappings(
    #     phandle=phandle, g2h_file=g2h_file
    # )

    # gpa2hva = dict(gpa2hva)
    # gpa2hpa = dict(gpa2hpa)
    gpa2hva = {}
    gpa2hpa = {}

    phandle.sendline("python proc_model.py --csv ./hello.csv")
    phandle.expect("#")

    phandle.sendline("cat ./hello.csv")
    phandle.expect("#")
    hello_csv = phandle.before.decode()
    with open(guest_file, "w") as out_file:
        for ln in hello_csv.splitlines():
            if "," in ln:
                print(ln, file=out_file)

    telnet_handle = pexpect.spawn(telnet_cmd)
    telnet_handle.expect("(qemu)")

    mapping_graph = gm.ModelGraph
    # Just look at the MOs
    with open(guest_file, mode='r', newline='') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            # Split the row by commas
            split_row = row
            if split_row[0] == "RESOURCE" and \
                split_row[1].startswith("MO_"):
                # Parse the last part as a JSON dictionary
                json_part = json.loads(split_row[-1])
                # Print the results
                gpa = json_part["pa"]
                hpa = get_guest_host_translation(
                    QemuMonitorCommand.GPA2HPA, gpa, telnet_handle
                )
                hva = get_guest_host_translation(
                    QemuMonitorCommand.GPA2HVA, gpa, telnet_handle
                )
                print(f"gPA: 0x{gpa:<16x}")
                print(f"   hVA: 0x{hva:<16x}")
                print(f"   hPA: 0x{hpa:<16x}")


                ## Create two MAP edges
                # mapping_graph.add_map_edge(
                #     gm.ResourceType.MO,  # type1
                #     gm.ResourceType.MO,  # typ2
                #     0x00,  # rs 1
                #     0x00,  # rs 2
                #     0x00,  # rs 1
                #     0x0,
                # )  # rs 2

        # Questions to answer
        #    -- What are the resource space IDs
        #    -- What are the resource IDs
        #    -- What are the types in guest Vs. host

    
    
    if get_host:
        get_host_state(phandle.pid, host_file=host_file)

    # Connect, for each gPA,
    # Add map:
    #        gPA --> hPA
    #        gPA --> hVA

    # Make a combined CSV
    # 1. Make sure we indentify every gPA in the hello.csv
    # Connect, for each gPA,
    # Add map:
    #        gPA --> hPA
    #        gPA --> hVA
    # 2. get Host qemu state,
    #         make sure the hVA and gPA node exists
    #         Upload its csv

    # print the interactions with the child
    # process.
    # child.interact()


def get_guest_host_mappings(
    phandle: pexpect.spawn, g2h_file: str
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:

    # Get host to guest to host mappings
    phandle.sendline("cat /proc/iomem")
    phandle.expect("#")
    iomem_output = phandle.before.decode()

    gpa2hpa = []
    gpa2hva = []
    page_size = os.sysconf("SC_PAGE_SIZE")
    assert page_size != 0, "cannot determine system page size"
    print(f"SC_PAGE_SIZE: {sizeof_fmt(page_size)} ")

    pexpect_handle = pexpect.spawn(telnet_cmd)
    pexpect_handle.expect("(qemu)")
    iommem_ranges = convert_iomem_to_RAMranges(iomem_output)

    start_time = time.time()
    ###########
    limit = 2000
    count = 0
    ###########

    for idx in range(len(iommem_ranges)):
        x = iommem_ranges[idx]
        print(
            f"START = IOMem Range [{idx}] {x.start:<16x} "
            f"{x.start + x.size:<16x} {x.size/page_size} Pages "
        )
        offset = 0

        while offset < x.size:
            gpa = x.start + offset
            hpa = get_guest_host_translation(
                QemuMonitorCommand.GPA2HPA, gpa, pexpect_handle
            )
            hva = get_guest_host_translation(
                QemuMonitorCommand.GPA2HVA, gpa, pexpect_handle
            )

            gpa2hpa.append((gpa, hpa))
            gpa2hva.append((gpa, hva))

            # with open("Output.txt", "a") as text_file:
            #     print(f"gPA : 0x{gpa:<16x} ---> hVA: 0x{hva:<16x}"
            #           f" hPA: 0x{hpa:<16x} ", file=text_file)

            page_offset = offset / page_size
            num_pages = int(x.size / page_size)

            if page_offset % 512 == 0:
                print(
                    f"\t{time.time() - start_time:4.2f} seconds:  "
                    f"{page_offset/num_pages * 100:.2f}%"
                )

            # Update offset
            offset += page_size

            if (count >= limit):
                break 
            else:
                count += 1

        print(
            f"END   = IOMem Range [{idx}] {x.start:<16x} {x.start + x.size:<16x} "
            f"{x.size/page_size} Pages "
        )

    with open(g2h_file, "w") as text_file:
        assert len(gpa2hpa) == len(gpa2hva)
        for idx in range(len(gpa2hpa)):
            print(
                f"gPA : 0x{gpa2hpa[idx][0]:<16x} --->"
                f" hVA: 0x{gpa2hva[idx][1]:<16x}"
                f" hPA: 0x{gpa2hpa[idx][1]:<16x} ",
                file=text_file,
            )
    print(f"{len(gpa2hva)} entries written to {g2h_file}")

    return gpa2hva, gpa2hpa


def main():
    parser = argparse.ArgumentParser(
        description="Extract the model state from the Qemu guest and merge it with the model state"
        "for the Qemu process from the host"
    )

    parser.add_argument(
        "--guest",
        type=str,
        required=True,
        help="Output file with guest's OSmosis model state",
    )
    parser.add_argument(
        "--g2h",
        type=str,
        required=False,
        help="Output file with guest to host memory mappings",
    )
    parser.add_argument(
        "--host",
        type=str,
        required=True,
        help="Output file with host's OSmosis model state",
    )
    args = parser.parse_args()

    get_vm_state(
        get_host=True, guest_file=args.guest, g2h_file=args.g2h, host_file=args.host
    )


def get_host_state(vm_pid: int, host_file: str):
    # # Create a copy of the current environment variables
    # custom_env = os.environ.copy()
    # # Modify the PATH environment variable

    # # Define the command to be executed
    # command = [ "python", "proc_model.py", "--pid", str(vm_pid), "--csv", "tmp.output"]

    # # Execute the command
    # process = subprocess.Popen(command, env=custom_env)
    # # Wait for the process to complete
    # process.wait()

    data = ProcFsData()
    try:
        extract_process_data(data, vm_pid, "qemu", should_print=False)
    except Exception as e:
        print("Error printing stats for QEMU")
        print(repr(e))
        traceback.print_exc()
        exit(1)

    data.to_generic_model(MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS).to_csv(
        host_file
    )


if __name__ == "__main__":
    main()
