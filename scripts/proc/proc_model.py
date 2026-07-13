import os
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
    str_to_namespace_type,
    load_seccomp_profile,
)
import sys
import argparse
import pexpect
import functools

# PFS Setup
sys.path.append("pfs/lib")
import pypfs # type: ignore

pfs_obj = pypfs.procfs()  # Interface to the PFS library


### CONFIGURATION ###
print_logs = False

def timeit(func):
    """
    Decorator to measure the time taken by a function.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"Function '{func.__name__}' took {end - start:.4f} seconds")
        return result

    return wrapper

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
    PODMAN = 5      # Start a podman container
    APPTAINER = 6   # Start an Apptainer (SingularityCE) instance
    KATA = 7        # Start a Docker container with the Kata runtime


program_names: EasyDict = EasyDict(
    basic="hello",
    static1="hello_static_1",
    static2="hello_static_2",
    malloc="hello_malloc",
    mmap="hello_mmap",
    print_pid="hello_print_pid",
    hello_file = "hello_file",
    python_passthrough = "passthrough.py",
    docker_ubuntu_bash = "ubuntu",
    podman_ubuntu_bash = "ubuntu",
    kv_app_in_vm = "kv_app_in_vm"
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
        (
            program_names.docker_ubuntu_bash + " test-docker2 " + "bash",
            ProcessStartType.DOCKER,
        ),
    ],
    # 9: KV Store App in the VM
    [
        (program_names.kv_app_in_vm, ProcessStartType.NORMAL),
    ],
    # 10: Podman ubuntu bash (two containers)
    [
        (program_names.podman_ubuntu_bash + " osmosis-podman-app " + "bash",
         ProcessStartType.PODMAN),
        (program_names.podman_ubuntu_bash + " osmosis-podman-kvs " + "bash",
         ProcessStartType.PODMAN),
    ],
    # 11: Two Apptainer instances (SIF image path set via APPTAINER_SIF env or default)
    [
        ("/tmp/ubuntu22.sif osmosis-app", ProcessStartType.APPTAINER),
        ("/tmp/ubuntu22.sif osmosis-kvs", ProcessStartType.APPTAINER),
    ],
    # 12: Reserved (gRPC Docker — use test_configs/grpc-docker/setup.sh with APP_PID= instead)
    [],
    # 13: Two Kata Containers (same image/cmd as Docker but with kata runtime)
    [
        ("ubuntu osmosis-kata-app bash", ProcessStartType.KATA),
        ("ubuntu osmosis-kata-kvs bash", ProcessStartType.KATA),
    ],
]

to_run = run_configs[3]  # default; overridden by --config at runtime


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

    elif start_type == ProcessStartType.PODMAN:
        args_list = name.split()
        assert len(args_list) == 3
        image = args_list[0]
        container_name = args_list[1]
        cmd = args_list[2]

        subprocess.run(["podman", "rm", "-f", container_name],
                       capture_output=True)
        subprocess.run(["podman", "run", "--rm", "-id",
                        "--name", container_name, image, cmd],
                       capture_output=True)
        inspect_output = subprocess.check_output(
            ["podman", "inspect", container_name], text=True)
        inspect_json_dict = json.loads(inspect_output)
        pid = inspect_json_dict[0]["State"]["Pid"]
        assert (pid != 0) and (pid is not None)

        return pid

    elif start_type == ProcessStartType.APPTAINER:
        args_list = name.split()
        assert len(args_list) == 2
        image, instance_name = args_list[0], args_list[1]
        subprocess.run(["apptainer", "instance", "stop", instance_name], capture_output=True)
        subprocess.run(["apptainer", "instance", "start", image, instance_name],
                       capture_output=True)
        time.sleep(2)
        list_output = subprocess.check_output(["apptainer", "instance", "list"], text=True)
        for line in list_output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == instance_name:
                pid = int(parts[1])
                break
        assert pid is not None and pid != 0
        return pid

    elif start_type == ProcessStartType.KATA:
        # Launched through containerd, not Docker. Docker + Kata 3.x fails with
        # "failed to create shim task: invalid namespace type": Docker hands the shim a
        # namespace type it rejects. containerd drives the same shim successfully.
        #
        # The host-visible process for a Kata sandbox is its QEMU, which is what we want
        # to model: it is the process that holds /dev/kvm. Its cmdline carries
        # "-name sandbox-<container>", so we find it by that.
        args_list = name.split()
        assert len(args_list) == 3
        image, container_name, cmd = args_list[0], args_list[1], args_list[2]
        ref = image if "/" in image else f"docker.io/library/{image}:22.04"

        subprocess.run(["ctr", "-n", "default", "task", "kill", "-s", "SIGKILL",
                        container_name], capture_output=True)
        time.sleep(1)
        subprocess.run(["ctr", "-n", "default", "container", "rm", container_name],
                       capture_output=True)
        subprocess.run(["ctr", "-n", "default", "images", "pull", ref],
                       capture_output=True)
        subprocess.run(["ctr", "-n", "default", "run", "-d",
                        "--runtime", "io.containerd.run.kata.v2",
                        ref, container_name, "sleep", "3600"],
                       capture_output=True)

        pid = None
        for _ in range(30):
            out = subprocess.run(["pgrep", "-f", f"sandbox-{container_name}"],
                                 capture_output=True, text=True)
            cands = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
            for c in cands:
                try:
                    with open(f"/proc/{c}/comm") as f:
                        if "qemu" in f.read():
                            pid = c
                            break
                except OSError:
                    continue
            if pid:
                break
            time.sleep(1)

        assert pid is not None and pid != 0, (
            f"no QEMU process found for Kata sandbox {container_name}")
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

def extract_cgroups_for_pid(data: ProcFsData, pid: int, should_print: bool = False):
    """
    Extract the cgroup v2 path for a process and store it in data.procs[pid].cgroup_path.
    Falls back to cgroup v1 memory controller path if unified hierarchy is not available.
    Handles non-standard cgroup paths (e.g. kata-containers qemu processes use
    '0::/system.slice:docker:{id}' with colon-separated path components).
    """
    cgroup_path = ""
    try:
        task = pfs_obj.get_task(pid)
        cgroups = task.get_cgroups()
        for cg in cgroups:
            # Unified cgroup v2 hierarchy has hierarchy id == 0
            if cg.hierarchy == 0:
                cgroup_path = cg.pathname
                break
            # Fallback: use the memory controller path from cgroup v1
            if "memory" in (cg.controllers if hasattr(cg, 'controllers') else []):
                cgroup_path = cg.pathname
    except RuntimeError:
        # pypfs can't parse non-standard cgroup paths (e.g. kata-containers uses colons
        # in the path: '0::/system.slice:docker:{id}'). Fall back to reading directly.
        try:
            with open(f"/proc/{pid}/cgroup") as f:
                for line in f:
                    parts = line.strip().split(":", 2)  # split at most twice
                    if len(parts) == 3 and parts[0] == "0":
                        cgroup_path = parts[2]
                        break
        except OSError:
            pass

    data.procs[pid].cgroup_path = cgroup_path

    if should_print:
        print(f"PID {pid} cgroup: {cgroup_path}")

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

    namespaces = {}
    for path, handle in task_ns_data.items():
        namespace_type = str_to_namespace_type[path]

        if namespace_type == NamespaceType.NONE:
            # Ignore some namespace types
            continue

        if handle in data.namespaces:
            assert (
                data.namespaces[handle].type == namespace_type
            ), "duplicate handle for different ns"
            ns_obj = data.namespaces[handle]
            if pid not in ns_obj.host_pids:
                ns_obj.host_pids.append(pid)
            namespaces[namespace_type] = ns_obj
        else:
            namespace = Namespace(
                type=namespace_type, handle=handle, host_pids=[pid],
                generic_data={}
            )
            namespaces[namespace_type] = namespace
            data.namespaces[handle] = namespace

    if should_print:
        print("NAMESPACES")
        for ns_info in namespaces.values():
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


@timeit
def read_pagemap_file(pid: int, should_print: bool = False) -> list[PageMapObj]:
    """
    Parse a /proc/pid/pagemaps file

    :param process: a process returned from run_process
    :param should_print: if true, prints the raw and parsed file
    :return: a list of objects representing the VA and VA->PA regions in the process' address space
    """
    try:
        results = get_va_pa_mappings(pid)
    except FileNotFoundError:
        # gVisor's virtual /proc does not expose pagemap
        return []

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

@timeit
def extract_memory_data(data: ProcFsData, pid: int, should_print=False):
    """
    Get the VMR, PMR, and Device data for a particular process

    :param data: the data object
    :param pid: the process to query about
    """

    print(f"Extract memory data for process {pid}")

    # Array where each element is a line in the /proc/[PID]/maps file
    maps = read_maps_file(pid, should_print)
    pagemaps = read_pagemap_file(pid, should_print=False)
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


def extract_host_uid(pid: int) -> int:
    """Return host-level effective UID, accounting for user namespace mapping."""
    try:
        with open(f"/proc/{pid}/uid_map") as f:
            parts = f.readline().split()
            if len(parts) < 3:
                raise ValueError("unexpected uid_map format")
            in_start, host_start, count = int(parts[0]), int(parts[1]), int(parts[2])
        with open(f"/proc/{pid}/status") as f:
            uid = next(int(ln.split()[1]) for ln in f if ln.startswith("Uid:"))
        if in_start <= uid < in_start + count:
            return host_start + (uid - in_start)
    except (FileNotFoundError, StopIteration, ValueError):
        pass
    return uid  # fallback: no mapping, uid is already host-level


def collect_ancestor_pids(pid: int) -> list:
    """Walk /proc/<pid>/status PPid: chain up to PID 1, returning ancestor PIDs."""
    ancestors, current, seen = [], pid, set()
    while True:
        if current in seen:
            break
        seen.add(current)
        try:
            with open(f"/proc/{current}/status") as f:
                ppid = next(int(ln.split()[1]) for ln in f if ln.startswith("PPid:"))
        except (FileNotFoundError, StopIteration):
            break
        if ppid <= 1:
            break
        ancestors.append(ppid)
        current = ppid
    return ancestors


def extract_from_status(data: ProcFsData, pid: int, should_print=False):
    status = read_status_file(pid, should_print)
    ns_pid = status.ns_pid if status.ns_pid else [pid]
    assert (
        pid == ns_pid[0]
    ), "PID from status should have been the same as the given PID"
    # Assuming only 1 level of PID NS.
    # Then ns_pid[0] is for the root PID NS
    # and  ns_pid[1] is for the child PID NS
    data.procs[pid].pid_in_ns = ns_pid[1] if len(ns_pid) == 2 else pid
    data.procs[pid].pid_in_host = pid

    data.procs[pid].uid_effective = status.uid.effective
    data.procs[pid].gid_effective = status.gid.effective

    data.procs[pid].cap_eff = status.cap_eff.raw

    # Host-level UID (accounts for user namespace mapping)
    data.procs[pid].uid_host = extract_host_uid(pid)

    # Seccomp mode and PPid: read from /proc/PID/status
    try:
        with open(f"/proc/{pid}/status") as f:
            for ln in f:
                if ln.startswith("Seccomp:"):
                    data.procs[pid].seccomp_mode = int(ln.split()[1])
                elif ln.startswith("PPid:"):
                    data.procs[pid].ppid = int(ln.split()[1])
    except (FileNotFoundError, StopIteration, ValueError):
        pass

    # LSM label (AppArmor/SELinux) from /proc/PID/attr/current
    try:
        with open(f"/proc/{pid}/attr/current") as f:
            data.procs[pid].lsm_label = f.read().strip()
    except (FileNotFoundError, PermissionError):
        data.procs[pid].lsm_label = ""

    print(data.procs[pid].pid_in_ns)
    print(data.procs[pid].uid_effective)
    print(data.procs[pid].gid_effective)
    print(data.procs[pid].cap_inh)
    print(data.procs[pid].cap_prm)
    print(data.procs[pid].cap_eff)
    print(data.procs[pid].cap_bnd)
    print(data.procs[pid].cap_amb)

def get_host_pid(task, fallback_pid: int = None) -> int:
    ns_pids = task.get_status(set()).ns_pid
    if not ns_pids:
        if fallback_pid is not None:
            ns_pids = [fallback_pid]
        else:
            raise IndexError("ns_pid is empty and no fallback_pid provided")
    host_pid = ns_pids[0]
    # Out script only supports only 1 level of PID namespaces for now.
    # So that is:
    #     HOST: THE PID NS create by init
    #     Docker: the PID NS created by docker
    if len(ns_pids) == 2:
        print(f"HOST PID = {ns_pids[0]} PID_NS PID = {ns_pids[1]}")

    if len(ns_pids) > 2:
        print(f"Error: ns_pids length is greater than 2. ns_pids: {ns_pids} for PID{host_pid}")
        raise AssertionError("ns_pids length is greater than 2")
    return host_pid

ignore_process_names = {
   "code": False,
   "node": False,
}

def extract_all_process_data(data: ProcFsData, should_print=False):
    proc_pids = sorted(int(d) for d in os.listdir('/proc') if d.isdigit())
    for idx, pid in enumerate(proc_pids):
        try:
            task = pfs_obj.get_task(pid)
            host_pid = get_host_pid(task, fallback_pid=pid)
        except Exception as e:
            print(f"\033[91mError getting host PID for {pid}: {e}\033[0m")
            continue
        p = psutil.Process(host_pid)
        if p.name() in ignore_process_names:
            print(f"\033[93mSkipping process {p.name()} with PID {host_pid}\033[0m")
            continue

        time_histogram = {}
        start_time = time.time()
        extract_process_data(data, host_pid, p.name(), should_print)
        end_time = time.time()
        elapsed_time = end_time - start_time

        if p.name() not in time_histogram:
            time_histogram[p.name()] = []

        time_histogram[p.name()].append(elapsed_time)
        if should_print:
            print(f"\033[92m---- Extracted process{idx} {host_pid}\033[0m")

        # Print the time histogram
        if should_print:
            print("\nTime Histogram:")
            for process_name, times in time_histogram.items():
                print(f"{process_name}: {'#' * int(sum(times))} ({sum(times):.2f}s)")

        if should_print:
            print(f"\033[92m---- Extracted process{idx} {host_pid}\033[0m")



def _meaningful_process_name(p) -> str:
    """Return a descriptive process name, falling back to cmdline[0] when /proc/comm
    is the generic 'exe' (as seen with gVisor's memfd-mapped Sentry binary)."""
    name = p.name()
    if name == "exe":
        try:
            cmd = p.cmdline()
            if cmd:
                return os.path.basename(cmd[0])
        except Exception:
            pass
    return name


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
    extract_cgroups_for_pid(data, pid, should_print)
    extract_namespaces_for_pid(data, pid, should_print)
    extract_mountinfo_for_pid(data, pid, should_print)
    extract_vm_device_for_pid(data, pid, should_print)


def extract_vm_device_for_pid(data: ProcFsData, pid: int, should_print: bool = False):
    """
    Record whether this process holds the hardware-virtualization device (/dev/kvm).

    Must run while the process is alive: to_generic_model() builds the graph after the
    processes have been terminated, so /proc/<pid>/fd no longer exists by then. Same
    constraint as TCP and FUSE connection detection.

    A process holds /dev/kvm exactly when it has asked the kernel for a virtualization
    context, which is what a VM boundary actually is. Detecting it by process name instead
    (calling anything named "qemu" or "firecracker" a VM) is wrong in both directions: an
    idle Firecracker waiting on its API socket has not opened the device, and gVisor on its
    default systrap platform never opens it at all.
    """
    fd_dir = f"/proc/{pid}/fd"
    holds = False
    try:
        for fd in os.listdir(fd_dir):
            try:
                if os.readlink(os.path.join(fd_dir, fd)) == "/dev/kvm":
                    holds = True
                    break
            except OSError:
                continue
    except (PermissionError, FileNotFoundError, ProcessLookupError):
        holds = False

    data.procs[pid].holds_vm_device = holds
    if should_print and holds:
        print(f"  PID {pid} holds /dev/kvm (VM boundary)")


def terminate_process(pid: int):
    """
    Terminate the process with the given pid
    """
    os.kill(pid, signal.SIGTERM)  # or signal.SIGKILL

def extract_all_users(data_main, should_print=False):
    """
    Extract all users and their UIDs from the system and add them to data_main.

    :param data_main: The main data object to store the extracted information.
    :param should_print: If true, prints the extracted information.
    """
    try:
        with open("/etc/passwd", "r") as passwd_file:
            for line in passwd_file:
                parts = line.split(":")
                if len(parts) > 2:
                    username = parts[0]
                    uid = int(parts[2])
                    data_main.users[username] = uid
                    if should_print:
                        print(f"User: {username}, UID: {uid}")
    except Exception as e:
        print(f"Error extracting UIDs: {e}")

def extract_all_groups(data_main, should_print=False):
    """
    Extract all groups and their GIDs from the system and add them to data_main.

    :param data_main: The main data object to store the extracted information.
    :param should_print: If true, prints the extracted information.
    """
    try:
        with open("/etc/group", "r") as group_file:
            for line in group_file:
                parts = line.split(":")
                if len(parts) > 2:
                    groupname = parts[0]
                    gid = int(parts[2])
                    data_main.groups[groupname] = gid
                    if should_print:
                        print(f"Group: {groupname}, GID: {gid}")
    except Exception as e:
        print(f"Error extracting GIDs: {e}")

def extract_all_user_groups(data_main, should_print=False):

    for username in data_main.users:
        extract_user_groups(data_main, username, True)
        if should_print:
           print(f"User: {username}, Group: {data_main.user_groups[username]}")

def extract_user_groups(data_main, username, should_print=False):
    """
    Extract all groups to which a user belongs and add them to data_main.

    :param data_main: The main data object to store the extracted information.
    :param username: The username to find groups for.
    :param should_print: If true, prints the extracted information.
    """
    try:
        user_groups = []
        with open("/etc/group", "r") as group_file:
            for line in group_file:
                parts = line.split(":")
                if len(parts) > 3:
                    groupname = parts[0]
                    members = parts[3].strip().split(",")
                    if username in members:
                        user_groups.append(groupname)
        data_main.user_groups[username] = user_groups
    except Exception as e:
        print(f"Error extracting groups for user {username}: {e}")

def detect_network_providers(data_main: ProcFsData) -> dict:
    """
    Detect which process provides networking for each NET namespace.
    Returns a map: net_ns_handle -> provider_pid
      - kernel (None) for host-network or regular containers
      - slirp4netns/passt/pasta PID for rootless containers
    """
    NETWORK_DAEMONS = {"slirp4netns", "pasta", "passt", "rootlesskit"}
    net_ns_to_provider = {}  # net_ns_handle -> pid (None means kernel)

    # First pass: find known network daemon processes
    for pid, proc_info in data_main.procs.items():
        if proc_info.name in NETWORK_DAEMONS:
            net_ns_handle = None
            if proc_info.namespaces:
                ns = proc_info.namespaces.get(NamespaceType.NET)
                if ns is not None:
                    net_ns_handle = ns.handle
            if net_ns_handle is not None:
                net_ns_to_provider[net_ns_handle] = pid

    # Second pass: for processes not served by a daemon, default to kernel (None)
    for pid, proc_info in data_main.procs.items():
        net_ns_handle = None
        if proc_info.namespaces:
            ns = proc_info.namespaces.get(NamespaceType.NET)
            if ns is not None:
                net_ns_handle = ns.handle
        if net_ns_handle is not None and net_ns_handle not in net_ns_to_provider:
            net_ns_to_provider[net_ns_handle] = None  # kernel provides

    return net_ns_to_provider


def detect_fuse_connections(data_main: ProcFsData) -> list:
    """
    Detect FUSE filesystem relationships between server and client processes.

    A FUSE server opens /dev/fuse and serves filesystem requests in user space.
    A FUSE client accesses files on a FUSE-mounted filesystem.

    Detection:
      1. For each known process, scan its pid_mounts for fuse* entries (not fusectl).
         Extract the minor device number from the "major:minor" device field (always 0:N for FUSE).
         Build: minor → set(pids that have this FUSE mount visible)
      2. For each known process, scan /proc/<pid>/fd/ for symlinks to /dev/fuse.
         Such processes are FUSE server candidates.
      3. For each server candidate, intersect its own visible FUSE mounts (from step 1)
         with the full minor→clients map to find which clients it serves.
      4. Emit (client_pid, server_pid, minor) tuples.

    Limitation: only detects connections where the server can see its own FUSE mount
    (typical for sshfs, rclone, s3fs run directly). Containers mounting FUSE via
    a separate fusermount helper may not be detected.

    Returns list of (client_pid, server_pid, minor) tuples.
    """
    import os as _os

    # Step 1: build minor → set(pids) and pid → set(fuse_minors) from pid_mounts
    minor_to_pids = {}    # fuse minor (int) → set of pids that see this mount
    pid_to_fuse_minors = {}  # pid → set of fuse minors visible in its mountinfo

    for pid, proc_info in data_main.procs.items():
        for mount in proc_info.pid_mounts:
            fstype = (getattr(mount, 'filesystem_type', '') or '').lower()
            if not fstype.startswith('fuse') or fstype == 'fusectl':
                continue
            device = getattr(mount, 'device', None)
            try:
                if isinstance(device, int):
                    # pypfs stores FUSE device as the kernel device number.
                    # For FUSE, major is always 0, so device == minor directly.
                    minor = device
                else:
                    major_str, minor_str = str(device).split(':')
                    if int(major_str) != 0:
                        continue
                    minor = int(minor_str)
            except (ValueError, AttributeError, TypeError):
                continue
            minor_to_pids.setdefault(minor, set()).add(pid)
            pid_to_fuse_minors.setdefault(pid, set()).add(minor)

    if not minor_to_pids:
        return []

    # Step 2: find FUSE server candidates — processes with /dev/fuse open
    server_pids = set()
    for pid in data_main.procs:
        fd_dir = f"/proc/{pid}/fd"
        try:
            fds = _os.listdir(fd_dir)
        except (FileNotFoundError, PermissionError):
            continue
        for fd in fds:
            try:
                target = _os.readlink(f"{fd_dir}/{fd}")
                if target == '/dev/fuse':
                    server_pids.add(pid)
                    break
            except (FileNotFoundError, PermissionError, OSError):
                continue

    # Step 3 & 4: match servers to clients via shared minor numbers
    connections = []
    seen = set()
    for server_pid in server_pids:
        owned_minors = pid_to_fuse_minors.get(server_pid, set())
        for minor in owned_minors:
            for client_pid in minor_to_pids.get(minor, set()):
                if client_pid == server_pid:
                    continue
                triple = (client_pid, server_pid, minor)
                if triple not in seen:
                    connections.append(triple)
                    seen.add(triple)
    return connections


def detect_tcp_connections(data_main: ProcFsData) -> list:
    """
    Detect ESTABLISHED TCP connections between known processes.
    Reads /proc/pid/net/tcp and /proc/pid/net/tcp6 for each PID.
    Matches by server listening port: if a process listens on port P and another
    process has an ESTABLISHED outbound connection to port P, they are connected.
    Returns list of (client_pid, server_pid) tuples.
    """
    listening_by_port = {}   # port_hex -> server_pid
    established_by_pid = {}  # pid -> set of remote_port_hex

    for pid in data_main.procs:
        for tcp_file in (f"/proc/{pid}/net/tcp", f"/proc/{pid}/net/tcp6"):
            try:
                with open(tcp_file) as f:
                    lines = f.readlines()[1:]  # skip header
            except (FileNotFoundError, PermissionError):
                continue
            for line in lines:
                parts = line.split()
                if len(parts) < 4:
                    continue
                local = parts[1]
                state = parts[3]
                local_port = local.rsplit(":", 1)[-1]
                if state == '0A':  # LISTEN
                    listening_by_port[local_port] = pid
                elif state == '01':  # ESTABLISHED
                    remote = parts[2]
                    remote_port = remote.rsplit(":", 1)[-1]
                    established_by_pid.setdefault(pid, set()).add(remote_port)

    connections = []
    seen = set()
    for client_pid, remote_ports in established_by_pid.items():
        for port in remote_ports:
            if port in listening_by_port:
                server_pid = listening_by_port[port]
                if server_pid != client_pid:
                    pair = (client_pid, server_pid)
                    if pair not in seen:
                        connections.append(pair)
                        seen.add(pair)
    return connections


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
        if not ns_pid:
            # gVisor's virtual /proc omits NSpid; treat as single-level PID NS
            ns_pid = [pid]
        assert (pid == ns_pid[0])
        try:
            child_ns_id, parent_ns_id = getNSInfo(pid, "pid")
        except OSError:
            # gVisor's virtual kernel doesn't support NS_GET_PARENT ioctl
            return [(ns_pid[0], -1)]
        if parent_ns_id == -1 or len(ns_pid) < 2:
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

    # Enumerate PIDs from /proc directly so we always have the numeric PID
    # available as fallback (gVisor's virtual /proc omits NSpid from status).
    proc_pids = sorted(int(d) for d in os.listdir('/proc') if d.isdigit())
    for pid in proc_pids:
        try:
            task = pfs_obj.get_task(pid)
        except Exception:
            continue
        ns_pids = task.get_status(set()).ns_pid
        if not ns_pids:
            ns_pids = [pid]
        host_pid = ns_pids[0]
        # Out script only supports only 1 level of PID namespaces for now.
        # So that is:
        #     HOST: THE PID NS create by init
        #     Docker: the PID NS created by docker
        if len(ns_pids) > 2:
            print(f"Error: ns_pids length is greater than 2. ns_pids: {ns_pids} for PID{host_pid}")
            raise AssertionError("ns_pids length is greater than 2")


        generic_ns_data = []

        try:
            task_ns_data = task.get_ns()
        except Exception as e:
            print(f"\033[93mError getting namespace data for PID {host_pid}: {e}\033[0m")
            continue
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


def run_queries(G, query_type: str):
    """
    Run a set of graph queries on the extracted model graph G (nx.MultiDiGraph).
    Called automatically when --query is passed.

    query_type: 'hold-edges' | 'shared-files' | 'shared-cgroups' |
                'shared-vmr'  | 'can-control'  | 'all'
    """
    from graph_queries import (
        get_pds, shared_resources, shared_resource_spaces, can_control, controlled_by
    )

    pds = get_pds(G)
    pd_names = {pd: G.nodes[pd].get('data', pd) for pd in pds}

    def header(title):
        print(f"\n{'='*60}")
        print(f"  {title}")
        print('='*60)

    run_all = (query_type == 'all')

    if run_all or query_type == 'hold-edges':
        header("Inter-PD HOLD Edges (can signal/terminate)")
        found = False
        for pd in pds:
            targets = can_control(G, pd)
            if targets:
                found = True
                for t in sorted(targets):
                    print(f"  {pd_names[pd]:30s} -> {pd_names.get(t, t)}")
        if not found:
            print("  (none)")

    if run_all or query_type == 'can-control':
        header("TCB: Processes that can terminate each PD")
        for pd in pds:
            holders = controlled_by(G, pd)
            if holders:
                names = [pd_names.get(h, h) for h in sorted(holders)]
                print(f"  {pd_names[pd]:30s} controlled by: {names}")

    if run_all or query_type == 'shared-files':
        header("Shared FILE Resources Between PD Pairs")
        found = False
        for i, pd1 in enumerate(pds):
            for pd2 in pds[i+1:]:
                shared = shared_resources(G, pd1, pd2, 'FILE')
                if shared:
                    found = True
                    extras = [G.nodes[r].get('extra', r) for r in sorted(shared)]
                    print(f"  {pd_names[pd1]:25s} <-> {pd_names[pd2]:25s}: {len(shared)} FILE(s)")
                    for e in extras[:5]:
                        print(f"    {e}")
        if not found:
            print("  (no shared FILE resources)")

    if run_all or query_type == 'shared-cgroups':
        header("Shared PAGE_QUOTA (Cgroup) Spaces Between PD Pairs")
        found = False
        for i, pd1 in enumerate(pds):
            for pd2 in pds[i+1:]:
                shared = shared_resource_spaces(G, pd1, pd2, 'PAGE_QUOTA')
                if shared:
                    found = True
                    print(f"  {pd_names[pd1]:25s} <-> {pd_names[pd2]:25s}: {len(shared)} cgroup(s)")
        if not found:
            print("  (no shared cgroup spaces)")

    if run_all or query_type == 'shared-vmr':
        header("Shared VMR/MO Resources Between PD Pairs")
        found = False
        for i, pd1 in enumerate(pds):
            for pd2 in pds[i+1:]:
                vmr = shared_resources(G, pd1, pd2, 'VMR')
                mo  = shared_resources(G, pd1, pd2, 'MO')
                if vmr or mo:
                    found = True
                    print(f"  {pd_names[pd1]:25s} <-> {pd_names[pd2]:25s}: "
                          f"{len(vmr)} VMR(s), {len(mo)} MO(s)")
        if not found:
            print("  (no shared VMR/MO resources)")

    if run_all or query_type == 'service-deps':
        header("Service Dependencies (TCP-detected REQUEST edges between PDs)")
        found = False
        for pd in pds:
            for _, target, data in G.out_edges(pd, data=True):
                if (data.get("type") == "REQUEST"
                        and G.nodes.get(target, {}).get("type") == "PD"):
                    found = True
                    print(f"  {pd_names[pd]:30s} -> {pd_names.get(target, target)}")
        if not found:
            print("  (no service-dependency REQUEST edges detected)")


def do_proc_model(args):
    # PIDs when this script starts them
    pids = []

    x = pfs_obj.get_cgroups()
    for y in x:
        print(f"{y.subsys_name} {y.hierarchy} . {y.num_cgroups}  {y.enabled}")



    data_main = ProcFsData()
    if args.guest:
        data_main.os_name = "Guest Linux"
    else:
        data_main.os_name = "Host Linux"

    #############################################
    # Get PID by either running or from args.
    #############################################
    if getattr(args, 'config', None) is not None:
        # --config: select a run_config, start its processes, extract, then kill
        selected = run_configs[args.config]
        print(f"Using run_config[{args.config}]: {selected}")
        pids = [run_process(name, start_type) for (name, start_type) in selected]
    elif getattr(args, 'pids', None):
        print(f"PIDs provided: {args.pids}")
    elif args.pid is not None:
        print(f"PID provided: {args.pid}")
    else:
        print("Starting processes from this script")
        pids = [run_process(name, start_type) for (name, start_type) in to_run]

    #############################################
    # Extract Info for all the PIDs
    #############################################
    # This is system Wide — only needed when extracting all PIDs
    if args.pid == 0:
        extract_all_namespaces(data_main)
    # extract_all_users(data_main, True)
    # extract_all_groups(data_main, True)
    # extract_all_user_groups(data_main, True)

    # This is for the processe of interest
    try:
        if getattr(args, 'pids', None):
            pid_list = [int(p.strip()) for p in args.pids.split(',') if p.strip()]
            if getattr(args, 'with_ancestors', False):
                extra_ancestors = []
                for pid in pid_list:
                    extra_ancestors.extend(collect_ancestor_pids(pid))
                # dedup, preserve order (explicit PIDs first, then ancestors)
                seen_pids = set()
                merged = []
                for pid in pid_list + extra_ancestors:
                    if pid not in seen_pids:
                        seen_pids.add(pid)
                        merged.append(pid)
                pid_list = merged
                print(f"With ancestors: {pid_list}")
            print(f"Extracting specific PIDs: {pid_list}")
            for pid in pid_list:
                try:
                    p = psutil.Process(pid)
                    name = _meaningful_process_name(p)
                    extract_process_data(data_main, pid, name, False)
                except psutil.NoSuchProcess:
                    print(f"Warning: PID {pid} no longer exists; skipping")
        elif args.pid == 0:
            print("Extracing info for all PIDs")
            extract_all_process_data(data_main, False)
        elif args.pid is not None and args.pid > 0:
            p = psutil.Process(args.pid)
            extract_process_data(data_main, args.pid, _meaningful_process_name(p), False)
        elif getattr(args, 'config', None) is not None:
            # processes were started above; pids list is populated
            time.sleep(2)
            selected = run_configs[args.config]
            for (_, start_type), pid in zip(selected, pids):
                # Use actual binary name so _is_hypervisor() can detect QEMU for kata.
                try:
                    actual_name = psutil.Process(pid).name()
                except psutil.NoSuchProcess:
                    actual_name = f"pid_{pid}"
                extract_process_data(data_main, pid, actual_name, False)
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
    # Detect TCP connections between known processes
    # (must run BEFORE terminating processes so /proc/<pid>/ is still accessible)
    #############################################
    connections = detect_tcp_connections(data_main)
    if connections:
        print(f"Detected {len(connections)} TCP connection(s) between known processes")

    #############################################
    # Detect FUSE connections between known processes
    # (must run BEFORE terminating processes so /proc/<pid>/fd/ is still accessible)
    #############################################
    fuse_connections = detect_fuse_connections(data_main)
    if fuse_connections:
        print(f"Detected {len(fuse_connections)} FUSE connection(s) between known processes")

    #############################################
    # Terminate the processes (after all live /proc queries are done)
    #############################################
    for pid in pids:
        print (f"Terminating PID {pid}")
        terminate_process(pid)

    #############################################
    # Convert to the model
    #############################################
    model = data_main.to_generic_model(
        MappingType.CONTIGUOUS,
        MappingType.CO_CONTIGUOUS,
        args.guest,
        connections=connections,
        fuse_connections=fuse_connections,
        seccomp_profile=getattr(args, "seccomp_profile", None),
    )
    model.to_csv(args.csv)
    print(f"Output CSV is at {args.csv}")

    #############################################
    # Run queries on the model graph (optional)
    #############################################
    if getattr(args, 'query', None):
        run_queries(model.g, args.query)


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
        "--pid", type=int, help="PID of the process to extract data for (0 = all)"
    )
    parser.add_argument(
        "--pids", type=str, help="Comma-separated list of PIDs to extract (e.g. 1234,5678)"
    )
    parser.add_argument(
        "--with-ancestors", action="store_true", default=False,
        help="Also extract all ancestor processes (parent chain up to PID 1) for each given PID"
    )
    parser.add_argument(
        "--config", type=int, default=None,
        help=f"run_configs index to start+extract+kill (0=two hello, 8=docker, etc). "
             f"Overrides --pid. Available: 0..{len(run_configs)-1}"
    )
    parser.add_argument(
        "--query", type=str, default=None,
        choices=["hold-edges", "shared-files", "shared-cgroups", "shared-vmr",
                 "can-control", "service-deps", "all"],
        help="Run graph queries after extraction and print results"
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
        "--seccomp-profile",
        type=str,
        default=None,
        help="Path to a seccomp profile JSON file. If not provided, the Docker default "
             "profile is applied automatically to processes with AppArmor label 'docker-default'.",
    )
    parser.add_argument(
        "-l",
        "--load-csv",
        default=False,
        action="store_true",
        help="Import to the neo4j running on the same machine",
    )
    parser.add_argument("--testname", type=str, help="CellulOS test to run. Doesn't apply to Linux")

    # Parse the arguments
    args = parser.parse_args()

    match args.os:
        case "linux":
            import psutil
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
