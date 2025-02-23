import os
import psutil
import signal
import json
import subprocess
from enum import Enum
import time
import traceback
from utils import (
    EasyDict,
    sizeof_fmt,
    insert_with_split,
    is_root,
    run,
    docker_cmd,
)
from read_pagemap import get_va_pa_mappings, PageMapObj
from get_ns_info import getNSInfo
from procfs_data import (
    ProcFsData,
    VMR,
    SubVMR,
    Device,
    PMR,
    Process,
    Namespace,
    NamespaceType,
    MappingType,
    str_to_namespace_type
)
import sys
import argparse
import pexpect

# PFS Setup
sys.path.append("pfs/lib")
import pypfs # type: ignore

pfs_obj = pypfs.procfs()  # Interface to the PFS library


### CONFIGURATION ###
print_logs = False


class ProcessStartType(Enum):
    """
    Different ways of starting a process for the configuration
    These types need to be supported by run_process
    """

    NORMAL = 1  # start the process in the default way
    NEW_PID_NS = 2  # start the process in a new PID namespace
                    # The mapping of the host pid to ns-pid can be found with
                    # cat /proc/PID/status| grep -i NSpid
    NEW_MNT_NS = 3  # start the process in a new PID namespace
                    # The mapping of the host path to ns-path can be found with
                    # ls -la /proc/PID/root
    DOCKER = 4      # Start a docker command


program_names: EasyDict = EasyDict(
    basic="hello",
    static1="hello_static_1",
    static2="hello_static_2",
    malloc="hello_malloc",
    mmap="hello_mmap",
    print_pid="hello_print_pid",
    hello_file = "hello_file",
    python_passthrough = "passthrough.py",
    docker_ubuntu_bash = "ubuntu"
)

run_configs = [
    # 0: Basic hello twice
    [
        (program_names.basic, ProcessStartType.NORMAL),
        (program_names.basic, ProcessStartType.NORMAL),
    ],
    # 1: Hello with malloc twice
    [
        (program_names.malloc, ProcessStartType.NORMAL),
        (program_names.malloc, ProcessStartType.NORMAL),
    ],
    # 2: Hello with shared mem via mmap twice
    [
        (program_names.mmap, ProcessStartType.NORMAL),
        (program_names.mmap, ProcessStartType.NORMAL),
    ],
    # 3: Hello linked statically twice
    [
        (program_names.static1, ProcessStartType.NORMAL),
        (program_names.static2, ProcessStartType.NORMAL),
    ],
    # 4: Hello linked statically twice
    [
        (program_names.static1, ProcessStartType.NORMAL),
        (program_names.static1, ProcessStartType.NORMAL),
    ],
    # 5: Hello in different PID namespaces twice
    [
        (program_names.print_pid, ProcessStartType.NEW_PID_NS),
        # (program_names.print_pid, ProcessStartType.NEW_PID_NS),
    ],
    # 6: Basic hello once
    [(program_names.basic, ProcessStartType.NORMAL)],
    # 7: Fuse File Systems. Order matters as python_passthrought sets up the files needed by hello_file
    [
        (program_names.python_passthrough, ProcessStartType.NORMAL),
        (program_names.hello_file, ProcessStartType.NORMAL),
    ],
    # 8: Docker bash
    [
        (
            program_names.docker_ubuntu_bash + " test-docker " + "bash",
            ProcessStartType.DOCKER,
        ),
    ],
]

to_run = run_configs[8]


def log(msg):
    if print_logs:
        print(msg)


### CONSTANTS ###
parent_pid_message = "Child PID in parent ns: "
child_pid_message = "Child PID in child ns: "
temp_output_file = "temp.txt"  # used to get output from some c programs


### RUNNING PROCESSES & EXTRACTING DATA ###


def run_process(name: str, start_type: ProcessStartType = False) -> tuple[int, int]:
    """
    Start a process from this directory (which should be the OSmosis/scripts/proc directory)
    Output will go to stdout

    :param name: The name of the program to run
    :param start_type: How to start the process
    :return: Tuple of the PID of the process in the global namespace, and in its own namespace
    """
    print(f'Starting process "{name}"')

    pid = None

    if start_type == ProcessStartType.NEW_PID_NS:

        # We need to use another program to start the process for us
        process = subprocess.Popen(
            ["sudo", "./hello_create_proc_in_ns", name, temp_output_file],
            stderr=subprocess.PIPE,
        )

        # The process will output the pid
        output_file_read = open(temp_output_file, "r")
        while True:
            # if something goes wrong, this might hang
            line = output_file_read.readline().strip()

            if line:
                log(line)

            if line.startswith(parent_pid_message):
                pid = int(line[len(parent_pid_message) :])
                log(f"PID in parent process: {pid}")
                break

            # This is not needed because we can get the child PID from /proc/pid/status
            # elif line.startswith(child_pid_message):
            #    pid_in_child = int(line[len(child_pid_message):])
            #    log(f"PID in child process: {pid_in_child}")

            elif not line:
                time.sleep(2)
    elif start_type == ProcessStartType.DOCKER:
        # start in docker
        args = name.split()
        assert len(args) == 3
        image = args[0]
        container_name = args[1]
        cmd = args[2]
        docker_cmd(cmd="rm", container_name=container_name)

        # Docker Run 
        docker_cmd(cmd="run", container_name=container_name, exec_cmd=cmd, image=image)
 
        # Docker Inspect to get the PID 
        inspect_output = docker_cmd("inspect", container_name)
        inspect_json_dict = json.loads(inspect_output)
        pid = inspect_json_dict[0]["State"]["Pid"]
        assert (pid != 0) and (pid is not None)

        return pid

    else:
        process = subprocess.Popen(f"./{name}", text=True)

        pid = process.pid

    time.sleep(2)  # Give the process time to get set up

    return pid


def read_maps_file(pid: int, should_print: bool = False) -> list[pypfs.task]:
    """
    Parse a /proc/pid/maps file

    :param pid: the pid of the process to read maps for
    :param should_print: if true, prints the raw and parsed file
    :return: a list of objects representing the parsed file
             the structure is defined in the pfs pybind module
    """

    task = pfs_obj.get_task(pid)
    maps = task.get_maps()

    if should_print:
        print("MAPS FILE")
        for map in maps:
            print(
                f"MAPS: [{map.start_address:16x}, {map.end_address:16x}] : {sizeof_fmt(map.end_address - map.start_address):10}",
                end="",
            )
            print(f": Device: {map.device:10}", end="")
            print(f": Pathname: {map.pathname:<30}")
        print("\n\n")

    return maps


def read_status_file(pid: int, should_print: bool = False) -> pypfs.task_status:
    """
    Parse a /proc/pid/status file

    :param pid: the pid of the process to read status for
    :param should_print: if true, prints the raw data
    :return: the task_status object
    """

    task = pfs_obj.get_task(pid)
    status = task.get_status(set())

    if should_print:
        print("STATUS FILE")
        print(f"- PID: {status.ns_pid}")
        print("\n\n")

    return status


def read_mountinfo_file(pid: int, should_print: bool = False) -> list[pypfs.mount]:
    """
    Parse a /proc/pid/mountinfo file

    :param pid: the pid of the process to read mountinfo for
    :param should_print: if true, prints the raw data
    :return: the list of mount objects
    """

    task = pfs_obj.get_task(pid)
    mounts = task.get_mountinfo()

    # See https://man7.org/linux/man-pages/man5/proc_pid_mountinfo.5.html
    # root: root: the pathname of the directory in the filesystem which forms the root of this mount.
    # mount point: the pathname of the mount point relative to the process's root directory.
    # mount source: filesystem-specific information or "none".
    # the device number seems to vary widely. I don't know what it means.

    if should_print:
        header = ["ID", "Parent", "Device", "FS_TYPE", "Point", "Source", "Root"]
        print(    "{:<8} {:<8} {:<12} {:<20} {:<40} {:<20} {:<20}".format(*header))
        ignored_fs_types = ["squashfs"]
        for mount in mounts:
            if mount.filesystem_type in ignored_fs_types:
                continue
            print(
            "{:<8} {:<8} {:<12} {:<20} {:<40} {:<20} {:<20}".format(
                mount.id,
                mount.parent_id,
                mount.device,
                mount.filesystem_type,
                mount.point,
                mount.source,
                mount.root,
            )
            )

    return mounts


def extract_mountinfo_for_pid(data: ProcFsData, pid: int, should_print: bool = False):
    """
    Show each mount point as a resource, which the mount_ns as the resource_space.
        - For overlayFS and ext4, show host dirs.
        - For other, show that it is some kernel-data resource. 
    
    1. What is the resource?
        A. It is the mount/dir
    2. What is the resource space ?
        A. It is the mnt namespace
    3. What does it map to? one of the following:
        A. Blocks
        A. Another path on the host
            - New NS
            - Host NS
        A. Or kernel internal state resource
            - Cannot say anything about psuedo FS
    4. What does the follwing map to:
        A. /proc/pid        --> PID resource 
        A. /proc/sys        --> Generic Kernel Resource
        A. /proc/sys/kernel --> Generic Kernel Resource
        A. /sys/kernel      --> Generic Kernel Resource
        A. /sys/firmware    --> Generic Kernel Resource
    5. What do we do for mount namespaces:
        A. Find dir on host.

    Helper Functions to write:
    - Get all mounts.
    - For an overlayFS get the paths.
    """

    data.procs[pid].pid_mounts = read_mountinfo_file(pid, True)

# Unsused
def extract_namespaces_for_pid(data: ProcFsData, pid: int, should_print: bool = False):
    """
    Find the namespaces this process belongs to
    Add to global data if not already present, and add to the process' list of namespaces

    :param pid: PID of the process to check for namespaces
    :param should_print: If true, print all of the namespaces found
    """

    task = pfs_obj.get_task(pid)
    task_ns_data = task.get_ns()

    # This only gets us the namespace type and handle
    # To find what the parent NS is, you can use ioctl, as shown in get_ns_info.c
    # I'm not sure if there is any other way to do this

    namespaces = []
    for path, handle in task_ns_data.items():
        namespace_type = str_to_namespace_type[path]

        if namespace_type == NamespaceType.NONE:
            # Ignore some namespace types
            continue

        if handle in data.namespaces:
            assert (
                data.namespaces[handle].type == namespace_type
            ), "duplicate handle for different ns"
            namespaces.append(data.namespaces[handle])
        else:
            namespace = Namespace(namespace_type, handle)
            namespaces.append(namespace)
            data.namespaces[handle] = namespace

    if should_print:
        print("NAMESPACES")
        for ns_info in namespaces:
            print(f"- NS: type {ns_info.type.name}, handle {ns_info.handle}")
        print("\n\n")

    data.procs[pid].namespaces = namespaces


def understanding_pagemap(results):
    assert_increasing_vaddrs(results)
    overlapping_mappings(results)


def overlapping_mappings(results):

    for idx1 in range(len(results)):
        pm1 = results[idx1]

        if pm1.paddr is None:
            continue

        start_va = pm1.vaddr
        end_va = pm1.vaddr + pm1.size

        start_pa = pm1.paddr
        end_pa = pm1.paddr + pm1.size

        for idx2 in range(len(results)):
            pm2 = results[idx2]

            if pm2.paddr is None:
                continue

            if idx1 == idx2:
                continue

            ## Does idx'1 PMR overlab with any other PMR

            assert pm2.paddr is not None
            # Check for start
            if pm2.paddr < start_pa and start_pa < (pm2.paddr + pm2.size):
                print("===Overlapping Detected at START")
                print(f"New Range: {pm1.paddr:16x}- {pm1.paddr+pm1.size:16x} ")
                print(f"Old Range: {pm2.paddr:16x}- {pm2.paddr+pm2.size:16x} ")

            # Check for end
            if pm2.paddr < end_pa and end_pa < (pm2.paddr + pm2.size):
                print("===Overlapping Detected at END")
                print(f"New Range: {pm1.paddr:16x}- {pm1.paddr+pm1.size:16x} ")
                print(f"Old Range: {pm2.paddr:16x}- {pm2.paddr+pm2.size:16x} ")


def assert_increasing_vaddrs(results):
    prev_va: int = 0
    curr_va: int = 0

    for pagemap in results:
        curr_va = pagemap.vaddr
        assert curr_va > prev_va
        prev_va = curr_va


def read_pagemap_file(pid: int, should_print: bool = False) -> list[PageMapObj]:
    """
    Parse a /proc/pid/pagemaps file

    :param process: a process returned from run_process
    :param should_print: if true, prints the raw and parsed file
    :return: a list of objects representing the VA and VA->PA regions in the process' address space
    """
    results = get_va_pa_mappings(pid)

    # understanding_pagemap(results)

    if should_print:
        print(
            f'{"VMR":<16} {"    VA_START":<16} {"     VA_END":<16} : {"SZ":<16}{" PA_START":<16}{"PA_END":<16}'
        )
        print("-" * 80)
        for pagemap in results:
            print(
                f'{"VMR":<16} {pagemap.vaddr:16x} {(pagemap.vaddr + pagemap.size):>16x} : {sizeof_fmt(pagemap.size):10}',
                end="",
            )
            if pagemap.mapped:
                print(f"{pagemap.paddr:16x} {(pagemap.paddr + pagemap.size):16x}")
            else:
                print()
        print("-" * 40)

    return results


def extract_memory_data(data: ProcFsData, pid: int, should_print=False):
    """
    Get the VMR, PMR, and Device data for a particular process

    :param data: the data object
    :param pid: the process to query about
    """

    print(f"Extract memory data for process {pid}")

    # Array where each element is a line in the /proc/[PID]/maps file
    maps = read_maps_file(pid, should_print)
    pagemaps = read_pagemap_file(pid, should_print)
    pagemap_iter = iter(pagemaps)
    next_pagemap = next(pagemap_iter, None)

    for map_entry in maps:
        vmr_info = VMR(map_entry.pathname, map_entry.perm)
        vmr_start_addr = map_entry.start_address
        vmr_end_addr = map_entry.end_address

        log(
            f"Checking VMR {vmr_start_addr:16x}-{vmr_end_addr:16x}, {vmr_info.pathname}"
        )

        # Could get permissions here

        # Find all PMRs for this VMR
        while next_pagemap is not None:
            pagemap = next_pagemap

            log(
                f"Checking sub-VMR {pagemap.vaddr:16x}-{pagemap.vaddr + pagemap.size:16x}"
            )

            # Check if we should move to the next VMR before processing this PMR
            if pagemap.vaddr >= vmr_end_addr:
                break

            next_pagemap = next(pagemap_iter, None)

            # Simple tracking of unmapped region
            if not pagemap.mapped:
                vmr_info.sub_vmrs.put(
                    pagemap.vaddr, pagemap.vaddr + pagemap.size, SubVMR(mapped=False)
                )
                continue

            # Insert the device, if not already tracked
            _, device_info = data.devices.get(pagemap.device_addr)

            if device_info is None:
                device_info = Device(size=pagemap.device_size)
                data.devices.put(
                    pagemap.device_addr,
                    pagemap.device_addr + pagemap.device_size,
                    device_info,
                )

            pmr_start_addr = pagemap.paddr
            pmr_end_addr = pagemap.paddr + pagemap.size
            vmr_info.sub_vmrs.put(
                pagemap.vaddr,
                pagemap.vaddr + pagemap.size,
                SubVMR(mapped=True, pmr=(pmr_start_addr, pmr_end_addr)),
            )

            log(f"Checking PMR {pagemap.paddr:16x}-{pagemap.paddr + pagemap.size:16x}")
            insert_with_split(data.pmrs, pmr_start_addr, pmr_end_addr, PMR(device_info))

        data.procs[pid].ads.vmrs.put(vmr_start_addr, vmr_end_addr, vmr_info)

    if print_logs:
        print(data.procs[pid].ads.vmrs)
        print(data.pmrs)
        print(data.devices)
        print("\n\n")


def extract_from_status(data: ProcFsData, pid: int, should_print=False):
    status = read_status_file(pid, should_print)
    assert (
        pid == status.ns_pid[0]
    ), "PID from status should have been the same as the given PID"
    # Assuming only 1 level of PID NS.
    # Then ns_pid[0] is for the root PID NS
    # and  ns_pid[1] is for the child PID NS
    data.procs[pid].pid_in_ns = status.ns_pid[1] if len(status.ns_pid) == 2 else pid


def extract_process_data(data: ProcFsData, pid: int, name: str, should_print=False):
    """
    Extract data from procfs for a particular process

    :param data: the data object
    :param pid_in_parent: PID of the process in the global namespace
    :param pid_in_child: PID of the process in the child namespace
    """
    process = Process(name)
    data.procs[pid] = process

    print(f"Extracting process {pid}: {data.procs[pid].name}")

    extract_from_status(data, pid, should_print)
    extract_memory_data(data, pid, should_print)
    extract_namespaces_for_pid(data, pid, should_print)
    #extract_mountinfo_for_pid(data, pid, should_print)

    if should_print:
        print(f"Extracted process {pid}: {data.procs[pid].name}")


def terminate_process(pid: int):
    """
    Terminate the process with the given pid
    """
    os.kill(pid, signal.SIGTERM)  # or signal.SIGKILL


# Get all namespaces in the systems YY
def extract_all_namespaces(data_main, should_print=False):
    """
    For each process in the system:
        - Find its NS and add it to data_main
        - For each NS track which PIDs are in it.
        - Additionally, track NS Type specific info in namespace.data which is a free form dict.
           - PID NS: For PID NS we track the following info in the dict
              - - key: PID as per the root PID NS
                - value: A tuple of PIDs and the PID NS in which the PID exists.
                  For example: If a bash is run as the first process in a docker container. The value would look like
                  [
                    (host_pid of the bash, ID of the root PID NS)
                    (1, ID of the child PID NS)
                  ]
    """

    # Helper function for PID NS
    def create_pid_ns_generic_data(pid):
        status = read_status_file(pid)
        ns_pid = status.ns_pid
        assert (pid == ns_pid[0])
        child_ns_id, parent_ns_id = getNSInfo(pid, "pid")
        if parent_ns_id == -1:
            return [
            (ns_pid[0], parent_ns_id)
        ]
        else:
            return [
            (ns_pid[0], parent_ns_id),
            (ns_pid[1], child_ns_id)
        ]
    
    # Helper function for Mount NS
    def create_mnt_ns_generic_data(pid):
        pass

    # get_processes returns a list of tasks
    processes = pfs_obj.get_processes()
    for task in processes:
        ns_pids = task.get_status(set()).ns_pid
        host_pid = ns_pids[0]
        # Out script only supports only 1 level of PID namespaces for now.
        # So that is:
        #     HOST: THE PID NS create by init
        #     Docker: the PID NS created by docker
        if len(ns_pids) > 2:
            print(f"Error: ns_pids length is greater than 2. ns_pids: {ns_pids} for PID{host_pid}")
            raise AssertionError("ns_pids length is greater than 2")


        generic_ns_data = []

        task_ns_data = task.get_ns()
        for path, handle in task_ns_data.items():
            namespace_type = str_to_namespace_type[path]
            match namespace_type:
                case NamespaceType.PID:
                    generic_ns_data = create_pid_ns_generic_data(host_pid)
                case NamespaceType.MNT:
                    generic_ns_data = create_mnt_ns_generic_data(host_pid)
                # Skip
                case NamespaceType.NONE:
                    continue
                case _:
                    generic_ns_data = []

            if handle in data_main.namespaces:
                assert (
                    data_main.namespaces[handle].type == namespace_type
                ), "duplicate handle for different ns"
                # Append the taskID
                namespace = data_main.namespaces[handle]
                namespace.host_pids.append(host_pid)
                # The the PIDs in all PID_NS for this host-PID
                namespace.generic_data[host_pid] = generic_ns_data

            else:
                namespace = Namespace(
                    type=namespace_type,
                    handle=handle,
                    host_pids=[host_pid],
                    generic_data={host_pid: generic_ns_data}
                )
                data_main.namespaces[handle] = namespace

    if should_print:
        print("NAMESPACES")
        for ns_info in data_main.namespaces.values():
            if ns_info.type != NamespaceType.PID:
                continue
            print(f"- NS: type {ns_info.type.name}, handle {ns_info.handle}", end="")
            print(f"PID Count: {len(ns_info.host_pids)}")
            # for v in ns_info.generic_data.values():
            #     print(f"DATA GENERIC: {v}")
        print("\n\n")


def do_proc_model(args):
    # PIDs when this script starts them
    pids = []

    data_main = ProcFsData()
    if args.guest:
        data_main.os_name = "Guest Linux"
    else:
        data_main.os_name = "Host Linux"

    #############################################
    # Get PID by either running or from args.
    #############################################
    if args.pid is not None:
        print(f"PID provided: {args.pid}")
    else:
        print("Starting processes from this script")
        pids = [run_process(name, start_type) for (name, start_type) in to_run]

    #############################################
    # Extract Info for all the PIDs
    #############################################
    # This is system Wide
    extract_all_namespaces(data_main, True)

    # This is for the processe of interest
    try:
        if args.pid:
            p = psutil.Process(args.pid)
            extract_process_data(data_main, args.pid, p.name(), False)
        else:
            # We add this delay so that the gettimeofday call in hello_static 
            # gets a chance to run
            time.sleep(2)
            for (name, _), pid in zip(to_run, pids):
                extract_process_data(data_main, pid, name, False)
    except Exception as e:
        print(repr(e))
        traceback.print_exc()
        exit(1)

    #############################################
    # Terminate the processes
    #############################################
    for pid in pids:
        print (f"Terminating PID {pid}")
        terminate_process(pid)


    #############################################
    # Convert to the model
    #############################################
    data_main.to_generic_model(
        MappingType.CONTIGUOUS,
        MappingType.CO_CONTIGUOUS,
        args.guest,
        # MappingType.PER_PAGE, MappingType.PER_PAGE, args.id_offset
    ).to_csv(args.csv)

    print(f"Output CSV is at {args.csv}")


def do_cellulos_model(args):

    # make -C /home/siagraw/sel4/seL4-CAmkES-L4v-dockerfiles user_run_l4v HOST_DIR=$(pwd) EXEC="sh -c 'cd /host/qemu-build && cmake . && ninja '"
    original_dir = os.getcwd()
    try:
        # Run cmake inside the container
        # We invoke the container using 'make'
        run(
            [
                "make",
                "-C",
                "/home/siagraw/sel4/seL4-CAmkES-L4v-dockerfiles",
                "user_run_l4v",
                "HOST_DIR=/home/siagraw/OSmosis",
                f"EXEC=sh -c 'cd /host/qemu-build && cmake . -DLibSel4TestPrinterRegex={args.testname} -DGPIExtractModel=ON'",
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

        # Run the simulation outside the container.
        simulate_cmd = "./simulate"
        os.chdir("/home/" + os.getlogin() + "/OSmosis/qemu-build/")
        print(f"Running CMD: {simulate_cmd} in {os.getcwd()}")
        phandle = pexpect.spawn(simulate_cmd)
        phandle.expect("BEGIN MODEL STATE")
        sim_output = phandle.before.decode()

        test_output = []
        for ln in sim_output.splitlines():
            if (
                ln.startswith("NODE_TYPE")
                or ln.startswith("PD")
                or ln.startswith("RESOURCE")
                or ln.startswith(",,")
            ):  # Edges
                test_output.append(ln)
    finally:
        os.chdir(original_dir)

    # Dump the model state to the file
    with open(args.csv, "w") as out_file:
        for ln in test_output:
            print(ln, file=out_file)


if __name__ == "__main__":

    # Define the argument parser
    parser = argparse.ArgumentParser(
        description="OSmosis Model state from multiple subsystems"
    )
    parser.add_argument(
        "--pid", type=int, help="PID of the process to extract data for"
    )
    parser.add_argument(
        "--csv", type=str, required=True, help="CSV to output the model state in"
    )
    parser.add_argument(
        "-g",
        "--guest",
        default=False,
        action="store_true",
        help="Change Kernel name in proc to guest something",
    )
    parser.add_argument(
        "--os",
        type=str,
        choices=["linux", "cellulos"],
        required=True,
        help="Linux or CellulOS(on Qemu) as the OS",
    )
    parser.add_argument(
        "-l",
        "--load-csv",
        default=False,
        action="store_true",
        help="Import to the neo4j running on the same machine",
    )
    parser.add_argument("--testname", type=str, help="CellulOS test to run")

    # Parse the arguments
    args = parser.parse_args()

    match args.os:
        case "linux":
            assert is_root()
            do_proc_model(args)
        case "cellulos":
            do_cellulos_model(args)
        case _:
            raise ValueError("Invalid platform")

    if args.load_csv:
        from import_csv import upload_csv_import
        files = [args.csv]
        print(f"Uploading {files} to neo4j")
        upload_csv_import("neo4j", files)
