from enum import Enum
import math
from dataclasses import dataclass, field
from utils import (
    EasyDict,
    IntervalDict,
)
import generic_model as gm
import sys

# PFS Setup
sys.path.append("pfs/lib")
import pypfs # type: ignore

### MODEL HELPER FUNCTIONS ###
def pathname_to_vmr_type(pathname: str):
    """
    Convert a pathname to a VMR reservation type

    :param pathname: pathname of a VMR, as read from the /proc/pid/maps file
    """
    global program_names

    if pathname is None or len(pathname) == 0:
        return gm.VmrType.NONE
    if pathname == "[heap]":
        return gm.VmrType.HEAP
    elif pathname == "[stack]":
        return gm.VmrType.STACK
    elif pathname == "[vvar]":  # what is this?
        return gm.VmrType.VVAR
    elif pathname == "[vdso]":  # what is this?
        return gm.VmrType.VDSO
    elif pathname == "[vsyscall]":  # what is this?
        return gm.VmrType.VSYSCALL
    elif (
        pathname.startswith("OSmosis/scripts/proc")
        or "/host/bin" in pathname
        or pathname.startswith("/root/proc")
        or pathname.startswith("/usr/bin")
    ):
        return gm.VmrType.PROGRAM  # I don't think code and data are separated
    elif pathname.startswith("/dev/shm"):
        return gm.VmrType.SHM
    elif pathname.startswith("/dev/"):
        return gm.VmrType.DEV
    elif ":kvm-vcpu" in pathname:
        return gm.VmrType.KVM
    elif (
        pathname.startswith("/usr/lib/")
        or pathname.endswith(".a")
        or pathname.endswith(".so")
        or pathname.startswith("/usr/libexec")
        or pathname.startswith("/lib/")
        or "/lib/" in pathname
        or ".so." in pathname
    ):
        return gm.VmrType.LIB
    else:
        print(f"Warning: unknown pathname '{pathname}' for VMR")
        return gm.VmrType.UNKNOWN


def perms_to_model_perms(perm: pypfs.mem_perm):
    """
    Convert a set of permissions from PFS to the generic model's Permissions object
    """
    perm_set = set()

    if perm.can_read:
        perm_set.add(gm.Permission.R)
    if perm.can_write:
        perm_set.add(gm.Permission.W)
    if perm.can_execute:
        perm_set.add(gm.Permission.X)
    if perm.is_private:
        perm_set.add(gm.Permission.P)
    if perm.is_shared:
        perm_set.add(gm.Permission.S)

    return gm.Permissions(perm_set)


def size_to_pages(size: int) -> int:
    """
    Convert the size of a region to the number of pages, assuming 4k pages

    :return: the number of pages
    """

    n_pages = size / gm.page_size
    assert n_pages % 1 == 0
    return math.ceil(n_pages)


### DATA STORAGE CLASSES ###


@dataclass
class SubVMR:
    """Tracks a single contiguous mapping of a VMR to a contiguous PMR, or an unmapped VMR"""

    mapped: bool = False  # Whether or not this VMR is mapped to a PMR
    pmr: tuple[int, int] = None  # The PMR range that this VMR maps to


@dataclass
class VMR:
    """Tracks a VMR in an address space."""

    pathname: str  # What this VMR is for - a file, or a marker like '[heap]'
    perms: pypfs.mem_perm  # Store of permissions for the VMR as given by pfs
    sub_vmrs: IntervalDict = field(
        default_factory=lambda: IntervalDict()
    )  # Dict of contiguous mappings within this VMR
    # Address range is tracked by the IntervalDict
    model_id: list[int] = field(
        default_factory=list
    )  # The ID(s) of this node in the model state, once added


@dataclass
class ProcAddressSpace:
    """Tracks a process' address space."""

    vmrs: IntervalDict = field(
        default_factory=lambda: IntervalDict()
    )  # list of VMR in the address space
    model_id: int = 0  # The ID of this node in the model state, once added



    def get_processes_in_same_pid_namespace(pid: int) -> list[int]:
        """
        Get a list of process IDs in the same PID namespace as the given process ID

        :param pid: Process ID
        :return: List of process IDs in the same PID namespace
        """
        try:
            with open(f"/proc/{pid}/ns/pid", "r") as ns_file:
                pid_ns_inode = ns_file.read()
            
            processes_in_same_ns = []
            for proc in os.listdir("/proc"):
                if proc.isdigit():
                    try:
                        with open(f"/proc/{proc}/ns/pid", "r") as other_ns_file:
                            if other_ns_file.read() == pid_ns_inode:
                                processes_in_same_ns.append(int(proc))
                    except FileNotFoundError:
                        continue
                    except Exception as e:
                        print(f"Error reading namespace for PID {proc}: {e}")
            
            return processes_in_same_ns
        except FileNotFoundError:
            print(f"Process with PID {pid} not found.")
        except Exception as e:
            print(f"Error reading namespace for PID {pid}: {e}")
        
        return []


class CGroupType(Enum):
    CPU = 1
    CPUACCT = 2
    MEMORY = 4
    DEVICES = 5
    FREEZER = 6
    NET_CLS = 7
    PERF_EVENT = 8
    NET_PRIO = 9
    HUGETLB = 10
    PIDS = 11
    RDMA = 12
    MISC = 13


# Use to convert a namespace type as string to NamespaceType
str_to_cgroup_type = {
    "cpu": CGroupType.CPU,
    "cpuacct": CGroupType.CPUACCT,
    "memory": CGroupType.MEMORY,
    "devices": CGroupType.DEVICES,
    "freezer": CGroupType.FREEZER,
    "net_cls": CGroupType.NET_CLS,
    "perf_event": CGroupType.PERF_EVENT,
    "net_prio": CGroupType.NET_PRIO,
    "hugetlb": CGroupType.HUGETLB,
    "pids": CGroupType.PIDS,
    "rdma": CGroupType.RDMA,
    "misc": CGroupType.MISC,
}

class CapabilityType(Enum):
    CAP_CHOWN = 1
    CAP_DAC_OVERRIDE = 2
    CAP_DAC_READ_SEARCH = 3
    CAP_FOWNER = 4
    CAP_FSETID = 5
    CAP_KILL = 6
    CAP_SETGID = 7
    CAP_SETUID = 8
    CAP_SETPCAP = 9
    CAP_LINUX_IMMUTABLE = 10
    CAP_NET_BIND_SERVICE = 11
    CAP_NET_BROADCAST = 12
    CAP_NET_ADMIN = 13
    CAP_NET_RAW = 14
    CAP_IPC_LOCK = 15
    CAP_IPC_OWNER = 16
    CAP_SYS_MODULE = 17
    CAP_SYS_RAWIO = 18
    CAP_SYS_CHROOT = 19
    CAP_SYS_PTRACE = 20
    CAP_SYS_PACCT = 21
    CAP_SYS_ADMIN = 22
    CAP_SYS_BOOT = 23
    CAP_SYS_NICE = 24
    CAP_SYS_RESOURCE = 25
    CAP_SYS_TIME = 26
    CAP_SYS_TTY_CONFIG = 27
    CAP_MKNOD = 28
    CAP_LEASE = 29
    CAP_AUDIT_WRITE = 30
    CAP_AUDIT_CONTROL = 31
    CAP_SETFCAP = 32
    CAP_MAC_OVERRIDE = 33
    CAP_MAC_ADMIN = 34
    CAP_SYSLOG = 35
    CAP_WAKE_ALARM = 36
    CAP_BLOCK_SUSPEND = 37
    CAP_AUDIT_READ = 38

# Map of CapabilityType to system calls they control
capability_to_syscalls = {
    CapabilityType.CAP_CHOWN: ["chown", "fchown", "lchown"],
    CapabilityType.CAP_DAC_OVERRIDE: ["open", "read", "write", "execve"],
    CapabilityType.CAP_DAC_READ_SEARCH: ["open", "read", "execve"],
    CapabilityType.CAP_FOWNER: ["chown", "chmod", "kill"],
    CapabilityType.CAP_FSETID: ["setuid", "setgid"],
    CapabilityType.CAP_KILL: ["kill"],
    CapabilityType.CAP_SETGID: ["setgid", "setgroups"],
    CapabilityType.CAP_SETUID: ["setuid", "setreuid", "setresuid"],
    CapabilityType.CAP_SETPCAP: ["capset"],
    CapabilityType.CAP_LINUX_IMMUTABLE: ["ioctl"],
    CapabilityType.CAP_NET_BIND_SERVICE: ["bind"],
    CapabilityType.CAP_NET_BROADCAST: ["setsockopt"],
    CapabilityType.CAP_NET_ADMIN: ["setsockopt", "getsockopt", "ioctl"],
    CapabilityType.CAP_NET_RAW: ["socket"],
    CapabilityType.CAP_IPC_LOCK: ["mlock", "mlockall"],
    CapabilityType.CAP_IPC_OWNER: ["msgctl", "semctl", "shmctl"],
    CapabilityType.CAP_SYS_MODULE: ["init_module", "delete_module"],
    CapabilityType.CAP_SYS_RAWIO: ["iopl", "ioperm"],
    CapabilityType.CAP_SYS_CHROOT: ["chroot"],
    CapabilityType.CAP_SYS_PTRACE: ["ptrace"],
    CapabilityType.CAP_SYS_PACCT: ["acct"],
    CapabilityType.CAP_SYS_ADMIN: ["mount", "umount", "swapon", "swapoff"],
    CapabilityType.CAP_SYS_BOOT: ["reboot"],
    CapabilityType.CAP_SYS_NICE: ["setpriority", "sched_setscheduler"],
    CapabilityType.CAP_SYS_RESOURCE: ["setrlimit", "prlimit"],
    CapabilityType.CAP_SYS_TIME: ["settimeofday", "stime", "adjtimex"],
    CapabilityType.CAP_SYS_TTY_CONFIG: ["vhangup"],
    CapabilityType.CAP_MKNOD: ["mknod"],
    CapabilityType.CAP_LEASE: ["fcntl"],
    CapabilityType.CAP_AUDIT_WRITE: ["audit_write"],
    CapabilityType.CAP_AUDIT_CONTROL: ["audit_control"],
    CapabilityType.CAP_SETFCAP: ["setxattr"],
    CapabilityType.CAP_MAC_OVERRIDE: ["mac_override"],
    CapabilityType.CAP_MAC_ADMIN: ["mac_admin"],
    CapabilityType.CAP_SYSLOG: ["syslog"],
    CapabilityType.CAP_WAKE_ALARM: ["alarm"],
    CapabilityType.CAP_BLOCK_SUSPEND: ["block_suspend"],
    CapabilityType.CAP_AUDIT_READ: ["audit_read"],
}

def get_cgroup_v2_path(pid: int) -> str:
    """
    Get the cgroup v2 path for a given process ID

    :param pid: Process ID
    :return: cgroup v2 path
    """
    try:
        with open(f"/proc/{pid}/cgroup", "r") as cgroup_file:
            for line in cgroup_file:
                if line.startswith("0::"):
                    return line.split(":")[2].strip()
    except FileNotFoundError:
        print(f"Process with PID {pid} not found.")
    except Exception as e:
        print(f"Error reading cgroup for PID {pid}: {e}")

    return ""

def get_parent_cgroup(cgroup_path: str) -> str:
    """
    Get the parent cgroup path for a given cgroup path

    :param cgroup_path: cgroup path
    :return: parent cgroup path
    """
    return "/".join(cgroup_path.strip("/").split("/")[:-1])

def processes_share_parent_cgroup(pid1: int, pid2: int) -> bool:
    """
    Check if two processes share the same parent cgroup v2

    :param pid1: First process ID
    :param pid2: Second process ID
    :return: True if both processes share the same parent cgroup v2, False otherwise
    """
    cgroup1 = get_cgroup_v2_path(pid1)
    cgroup2 = get_cgroup_v2_path(pid2)

    parent_cgroup1 = get_parent_cgroup(cgroup1)
    parent_cgroup2 = get_parent_cgroup(cgroup2)

    return parent_cgroup1 == parent_cgroup2



    # List of syscalls blocked by Docker's default seccomp profile
    docker_seccomp_blocked_syscalls = [
        "acct",
        "add_key",
        "adjtimex",
        "bpf",
        "clock_adjtime",
        "clock_settime",
        "create_module",
        "delete_module",
        "finit_module",
        "get_kernel_syms",
        "get_mempolicy",
        "init_module",
        "ioperm",
        "iopl",
        "kcmp",
        "kexec_file_load",
        "kexec_load",
        "keyctl",
        "lookup_dcookie",
        "mbind",
        "mount",
        "move_pages",
        "name_to_handle_at",
        "nfsservctl",
        "open_by_handle_at",
        "perf_event_open",
        "personality",
        "pivot_root",
        "process_vm_readv",
        "process_vm_writev",
        "ptrace",
        "query_module",
        "quotactl",
        "reboot",
        "request_key",
        "set_mempolicy",
        "setns",
        "settimeofday",
        "stime",
        "swapoff",
        "swapon",
        "sysfs",
        "syslog",
        "umount2",
        "unshare",
        "uselib",
        "userfaultfd",
        "ustat",
        "vm86",
        "vm86old",
    ]


def get_process_capabilities(pid: int) -> list[CapabilityType]:
    """
    Get the list of capabilities available to a process by reading /proc/pid/status

    :param pid: Process ID
    :return: List of capabilities available to the process
    """
    capabilities = []
    try:
        with open(f"/proc/{pid}/status", "r") as status_file:
            for line in status_file:
                if line.startswith("CapEff:"):
                    cap_eff = int(line.split()[1], 16)
                    for cap in CapabilityType:
                        if cap_eff & (1 << (cap.value - 1)):
                            capabilities.append(cap)
                    break
    except FileNotFoundError:
        print(f"Process with PID {pid} not found.")
    except Exception as e:
        print(f"Error reading capabilities for PID {pid}: {e}")

    return capabilities

def get_disallowed_syscalls(capabilities: list[CapabilityType]) -> list[str]:
    """
    Get the list of system calls not allowed based on the given capabilities

    :param capabilities: List of capabilities available to the process
    :return: List of system calls not allowed
    """
    allowed_syscalls = set()
    for cap in capabilities:
        if cap in capability_to_syscalls:
            allowed_syscalls.update(capability_to_syscalls[cap])

    all_syscalls = set(syscall for syscalls in capability_to_syscalls.values() for syscall in syscalls)
    disallowed_syscalls = all_syscalls - allowed_syscalls

    return list(disallowed_syscalls)

# Use to convert a capability type as string to CapabilityType
str_to_capability_type = {
    "CAP_CHOWN": CapabilityType.CAP_CHOWN,
    "CAP_DAC_OVERRIDE": CapabilityType.CAP_DAC_OVERRIDE,
    "CAP_DAC_READ_SEARCH": CapabilityType.CAP_DAC_READ_SEARCH,
    "CAP_FOWNER": CapabilityType.CAP_FOWNER,
    "CAP_FSETID": CapabilityType.CAP_FSETID,
    "CAP_KILL": CapabilityType.CAP_KILL,
    "CAP_SETGID": CapabilityType.CAP_SETGID,
    "CAP_SETUID": CapabilityType.CAP_SETUID,
    "CAP_SETPCAP": CapabilityType.CAP_SETPCAP,
    "CAP_LINUX_IMMUTABLE": CapabilityType.CAP_LINUX_IMMUTABLE,
    "CAP_NET_BIND_SERVICE": CapabilityType.CAP_NET_BIND_SERVICE,
    "CAP_NET_BROADCAST": CapabilityType.CAP_NET_BROADCAST,
    "CAP_NET_ADMIN": CapabilityType.CAP_NET_ADMIN,
    "CAP_NET_RAW": CapabilityType.CAP_NET_RAW,
    "CAP_IPC_LOCK": CapabilityType.CAP_IPC_LOCK,
    "CAP_IPC_OWNER": CapabilityType.CAP_IPC_OWNER,
    "CAP_SYS_MODULE": CapabilityType.CAP_SYS_MODULE,
    "CAP_SYS_RAWIO": CapabilityType.CAP_SYS_RAWIO,
    "CAP_SYS_CHROOT": CapabilityType.CAP_SYS_CHROOT,
    "CAP_SYS_PTRACE": CapabilityType.CAP_SYS_PTRACE,
    "CAP_SYS_PACCT": CapabilityType.CAP_SYS_PACCT,
    "CAP_SYS_ADMIN": CapabilityType.CAP_SYS_ADMIN,
    "CAP_SYS_BOOT": CapabilityType.CAP_SYS_BOOT,
    "CAP_SYS_NICE": CapabilityType.CAP_SYS_NICE,
    "CAP_SYS_RESOURCE": CapabilityType.CAP_SYS_RESOURCE,
    "CAP_SYS_TIME": CapabilityType.CAP_SYS_TIME,
    "CAP_SYS_TTY_CONFIG": CapabilityType.CAP_SYS_TTY_CONFIG,
    "CAP_MKNOD": CapabilityType.CAP_MKNOD,
    "CAP_LEASE": CapabilityType.CAP_LEASE,
    "CAP_AUDIT_WRITE": CapabilityType.CAP_AUDIT_WRITE,
    "CAP_AUDIT_CONTROL": CapabilityType.CAP_AUDIT_CONTROL,
    "CAP_SETFCAP": CapabilityType.CAP_SETFCAP,
    "CAP_MAC_OVERRIDE": CapabilityType.CAP_MAC_OVERRIDE,
    "CAP_MAC_ADMIN": CapabilityType.CAP_MAC_ADMIN,
    "CAP_SYSLOG": CapabilityType.CAP_SYSLOG,
    "CAP_WAKE_ALARM": CapabilityType.CAP_WAKE_ALARM,
    "CAP_BLOCK_SUSPEND": CapabilityType.CAP_BLOCK_SUSPEND,
    "CAP_AUDIT_READ": CapabilityType.CAP_AUDIT_READ,
}


class NamespaceType(Enum):
    UTS = 1
    USER = 2
    PID = 3
    NET = 4
    MNT = 5
    IPC = 6
    CGROUP = 7
    TIME = 8
    NONE = 9  # we choose to ignore some namespace types: pid_for_children and time_for_children


# Use to convert a namespace type as string to NamespaceType
str_to_namespace_type = {
    "uts": NamespaceType.UTS,
    "user": NamespaceType.USER,
    "pid_for_children": NamespaceType.NONE,
    "pid": NamespaceType.PID,
    "net": NamespaceType.NET,
    "time_for_children": NamespaceType.NONE,
    "mnt": NamespaceType.MNT,
    "ipc": NamespaceType.IPC,
    "cgroup": NamespaceType.CGROUP,
    "time": NamespaceType.TIME,
}

class FileSystemType(Enum):
    EXT4 = 1
    OVERLAY = 2
    SQUASHFS = 3
    FUSE = 4
    # THESE GO TO KERNEL
    BINFMT_MISC = 5
    BPF = 6
    CGROUP2 = 7
    CONFIGFS = 8
    DEBUGFS = 9
    DEVPTS = 10
    EFIVARFS = 11
    FUSECTL = 12
    HUGETLBFS = 13
    MQUEUE = 14
    NSFS = 15
    PROC = 16
    PSTORE = 17
    RAMFS = 18
    SECURITYFS = 19
    SYSFS = 20
    SYSTEMD_1 = 21
    TMPFS = 22
    TRACEFS = 23
    UDEV = 24


# Use to convert a namespace type as string to NamespaceType
str_to_filesystem_type = {

    "ext4" : FileSystemType.EXT4,
    "overlay" : FileSystemType.OVERLAY,
    "squashfs" : FileSystemType.SQUASHFS,
    "fuse" : FileSystemType.FUSE,
    "binfmt_misc" : FileSystemType.BINFMT_MISC,
    "bpf" : FileSystemType.BPF,
    "cgroup2" : FileSystemType.CGROUP2,
    "configfs" : FileSystemType.CONFIGFS,
    "debugfs" : FileSystemType.DEBUGFS,
    "devpts" : FileSystemType.DEVPTS,
    "efivarfs" : FileSystemType.EFIVARFS,
    "fusectl" : FileSystemType.FUSECTL,
    "hugetlbfs" : FileSystemType.HUGETLBFS,
    "mqueue" : FileSystemType.MQUEUE,
    "nsfs" : FileSystemType.NSFS,
    "proc" : FileSystemType.PROC,
    "pstore" : FileSystemType.PSTORE,
    "ramfs" : FileSystemType.RAMFS,
    "securityfs" : FileSystemType.SECURITYFS,
    "sysfs" : FileSystemType.SYSFS,
    "systemd-1" : FileSystemType.SYSTEMD_1,
    "tmpfs" : FileSystemType.TMPFS,
    "tracefs" : FileSystemType.TRACEFS,
    "udev" : FileSystemType.UDEV,
}

kernel_interface_file_systems = [
    FileSystemType.BINFMT_MISC,
    FileSystemType.BPF,
    FileSystemType.CGROUP2,
    FileSystemType.CONFIGFS,
    FileSystemType.DEBUGFS,
    FileSystemType.DEVPTS,
    FileSystemType.EFIVARFS,
    FileSystemType.FUSECTL,
    FileSystemType.HUGETLBFS,
    FileSystemType.MQUEUE,
    FileSystemType.NSFS,
    FileSystemType.OVERLAY,
    FileSystemType.PROC,
    FileSystemType.PSTORE,
    FileSystemType.RAMFS,
    FileSystemType.SECURITYFS,
    FileSystemType.SYSFS,
    FileSystemType.SYSTEMD_1,
    FileSystemType.TMPFS,
    FileSystemType.TRACEFS,
    FileSystemType.UDEV,
]

@dataclass
class Namespace:
    type: NamespaceType
    handle: int # Assumed unique ID
    host_pids: set[int] # PIDs (in host PID namespace) of all processes in that namespace
    generic_data:  EasyDict = EasyDict() # NS specific data.
             #   For PID_NS, we store the mapping from pid_in_host to pid_in child NS, for now we only support two levels.
             #   { "pid_host" : [
             #                      (pid_host, root_PID NS ID),
             #                      (pid_in_ns, child PID NS ID)
             #                   ] 
             #   }


@dataclass
class Process:
    """Tracks a process"""

    name: str  # Name of the process

    uid_effective: int = 0
    gid_effective: int = 0

    cap_inh: int = 0
    cap_prm: int = 0
    cap_eff: int = 0
    cap_bnd: int = 0
    cap_amb: int = 0

    ads: ProcAddressSpace = field(
        default_factory=lambda: ProcAddressSpace()
    )  # The process' address space
    namespaces = {} # Key: NS Type, Value: Namespace DS
                                       # Assume that one PID can only be part of one NS of a type
    model_id: int = 0  # The ID of this node in the model state, once added
    pid_in_ns: int = 0  # PID of the process according to its own PID namespace
    pid_in_host: int = 0  # PID of the process according to host (default) PID namespace
    # The PID (in global PID namespace) will be the key of the dict this is in
    pid_mounts: list[pypfs.mount] = field(default_factory=lambda: list())
    cgroup_path: str = ""  # cgroup v2 path for this process


@dataclass
class Device:
    """Tracks a physical memory device in the system"""

    size: int  # Size of the device, in bytes
    # Address range is tracked by the IntervalDict
    model_id: int = 0  # The ID of this node in the model state, once added


@dataclass
class PMR:
    """Tracks a PMR in the system"""

    device: Device  # The Device this PMR is from
    # Address range is tracked by the IntervalDict
    model_id: list[int] = field(
        default_factory=list
    )  # The ID(s) of this node in the model state, once added

    # Define copy for when PMRs get split
    def __copy__(self):
        result = PMR(self.device)

        return result


# Different ways to display VA / PA nodes in the graph
class MappingType(Enum):
    PER_PAGE = 1  # Every node is exactly one page
    CO_CONTIGUOUS = 2  # Show co-contiguous mapped regions as one VA / PA node
    CONTIGUOUS = 3  # Show contiguous regions as one node


class ProcFsData:
    """
    Intermediate repository for the relevant data from /proc for multiple processes
    This object can be converted to the generic ModelGraph
    """

    def __init__(self):
        self.namespaces = {}  # dict from namespace handle to Namespace
        self.users = {}  # dict from username to uid
        self.groups = {}  # dict from groupname to gid
        self.user_groups = {}  # dict from username to list of groups
        self.procs = {}  # dict from PID to Process
        self.pmrs = IntervalDict()  # list of PMR
        self.devices = IntervalDict()  # list of physical memory devices, ProcDev
        self.os_name = ""

    def __map_vmr_to_pmrs(
        self,
        mapped_devices: set,
        ads_id: int,
        vmr_node_id: int,
        pmr_range_start: int,
        pmr_range_end: int,
    ):
        """
        Helper function during conversion to generic model
        Maps a VMR node to the co-contiguous PMRs within a range

        :param mapped_devices: set of devices to update
        :param ads_id: ID of the VMR's address space in the model
        :param vmr_node_id: ID of the VMR's node in the model
        :param pmr_range_start: start of the PMR range to map to
        :param pmr_range_end: end of the PMR range to map to
        """

        # Iterate through all PMR regions (may have been split)
        pmrs = self.pmrs.get_interval(pmr_range_start, pmr_range_end)

        for (pmr_start, pmr_end), pmr_info in pmrs:
            mapped_devices.add(pmr_info.device.model_id)
            self.model.add_map_edge(
                gm.ResourceType.VMR,
                gm.ResourceType.MO,
                ads_id,
                pmr_info.device.model_id,
                vmr_node_id,
                pmr_info.model_id[0],
                pd_incharge=self.os_name
            )

    def __has_cap_kill(self, process_info) -> bool:
        """Check if a process has CAP_KILL set in its effective capability bitmask."""
        CAP_KILL_BIT = 5  # CAP_KILL is bit 5 (0-indexed) in the capability bitmask
        return bool(process_info.cap_eff & (1 << CAP_KILL_BIT))

    def __add_inter_process_hold_edges(self):
        """
        Add hold edges between processes based on Linux signal-sending rules:
          - Same effective UID in same/child PID namespace, OR
          - Root (uid_eff == 0), OR
          - CAP_KILL set in effective capabilities

        A hold edge from PD_x to PD_y means x can send SIGKILL to y.
        """
        namespaces_available = all(
            hasattr(p, 'namespaces') and p.namespaces
            for p in self.procs.values()
        )

        # Find the default (root) PID namespace: the one containing PID 1
        default_pid_ns = None
        if namespaces_available and 1 in self.procs:
            ns_map = self.procs[1].namespaces
            default_pid_ns = ns_map.get(NamespaceType.PID)

        for from_node in self.procs.values():
            from_uid = from_node.uid_effective

            from_pid_ns = None
            if namespaces_available:
                from_pid_ns = from_node.namespaces.get(NamespaceType.PID)

            for to_node in self.procs.values():
                if from_node is to_node:
                    continue

                # Namespace scope check: if namespaces are known, enforce PID-NS scoping
                if namespaces_available and from_pid_ns is not None and default_pid_ns is not None:
                    to_pid_ns = to_node.namespaces.get(NamespaceType.PID)
                    # A process in a non-root PID NS can only signal within its own NS
                    if from_pid_ns != default_pid_ns and from_pid_ns != to_pid_ns:
                        continue

                add_edge = (
                    from_uid == to_node.uid_effective
                    or from_uid == 0
                    or self.__has_cap_kill(from_node)
                )

                if add_edge:
                    print(f"\033[92mAdding hold edge from {from_node.model_id} to {to_node.model_id}\033[0m")
                    self.model.add_inter_pd_hold_edge(
                        gm.perms_all, from_node.model_id, to_node.model_id
                    )
    def __add_file_resources(self, kernel_id: int):
        """
        Model mount points as FILE resources with mount namespaces as resource spaces.
        Processes sharing the same source path (real filesystems) share the resource node.
        """
        # Pseudo-filesystems and read-only image layers — skip as FILE resources.
        # These are either kernel-internal interfaces or read-only shared layers
        # that don't represent user-writable shared data (and appear in the model
        # as shared MO resources instead, which the VMR/MO analysis covers).
        pseudo_fs = {
            FileSystemType.BINFMT_MISC, FileSystemType.BPF, FileSystemType.CGROUP2,
            FileSystemType.CONFIGFS, FileSystemType.DEBUGFS, FileSystemType.DEVPTS,
            FileSystemType.EFIVARFS, FileSystemType.FUSECTL, FileSystemType.HUGETLBFS,
            FileSystemType.MQUEUE, FileSystemType.NSFS, FileSystemType.PROC,
            FileSystemType.PSTORE, FileSystemType.RAMFS, FileSystemType.SECURITYFS,
            FileSystemType.SQUASHFS,  # read-only container image layers (Docker/Podman base images)
            FileSystemType.SYSFS, FileSystemType.SYSTEMD_1, FileSystemType.TMPFS,
            FileSystemType.TRACEFS, FileSystemType.UDEV,
        }

        # mnt_ns_handle -> resource space ID in the model
        mnt_ns_to_space_id = {}
        # (source_path, fs_type) -> resource node ID in the model
        source_to_file_id = {}

        for pid, proc_info in self.procs.items():
            if not proc_info.pid_mounts:
                continue

            # Determine MNT namespace handle for this process
            mnt_ns_handle = None
            if proc_info.namespaces:
                ns = proc_info.namespaces.get(NamespaceType.MNT)
                if ns is not None:
                    mnt_ns_handle = ns.handle


            # Create resource space for this mount namespace (if not already done)
            if mnt_ns_handle is not None and mnt_ns_handle not in mnt_ns_to_space_id:
                space_id = self.model.add_resource_space_node(gm.ResourceType.FILE, mnt_ns_handle)
                mnt_ns_to_space_id[mnt_ns_handle] = space_id
                self.model.add_hold_edge(
                    gm.perms_all, kernel_id, gm.ResourceType.FILE, mnt_ns_handle,
                    pd_incharge=self.os_name
                )

            space_id = mnt_ns_to_space_id.get(mnt_ns_handle)
            if space_id is None:
                # No MNT namespace info; use a generic shared space (space_id=0)
                if 0 not in mnt_ns_to_space_id:
                    sid = self.model.add_resource_space_node(gm.ResourceType.FILE)
                    mnt_ns_to_space_id[0] = sid
                    self.model.add_hold_edge(
                        gm.perms_all, kernel_id, gm.ResourceType.FILE, sid,
                        pd_incharge=self.os_name
                    )
                space_id = mnt_ns_to_space_id[0]

            for mount in proc_info.pid_mounts:
                fs_type_str = mount.filesystem_type.lower() if hasattr(mount, 'filesystem_type') else ""
                fs_type = str_to_filesystem_type.get(fs_type_str)

                if fs_type in pseudo_fs:
                    continue

                source = mount.source if hasattr(mount, 'source') else ""
                point  = mount.point  if hasattr(mount, 'point')  else ""
                root   = mount.root   if hasattr(mount, 'root')   else ""

                # Key identifies a shared physical resource across processes.
                # Two mounts are the same resource iff they expose the same data:
                # - real FS (ext4): same block device + same sub-directory (root) within it.
                #   Both containers bind-mounting DIFFERENT paths on the same device are NOT shared.
                # - overlayFS: same upper+lower layer directories exposed at same point.
                #   Each container has a unique overlay, so scope by MNT namespace handle.
                # - All keys are scoped by MNT namespace handle so that intra-NS
                #   sharing is detected but inter-NS coincidences (both have "/") are not.
                effective_source = source if source and source != "none" else point
                if fs_type == FileSystemType.OVERLAY:
                    key = (mnt_ns_handle, point, fs_type_str)
                else:
                    key = (mnt_ns_handle, effective_source, root, fs_type_str)

                if key not in source_to_file_id:
                    res_id = self.model.add_resource_node(
                        gm.ResourceType.FILE, space_id, extra=point
                    )
                    source_to_file_id[key] = (space_id, res_id)

                file_space_id, file_res_id = source_to_file_id[key]

                # Hold edge: process -> file resource (R/W based on mount flags)
                self.model.add_hold_edge(
                    gm.perms_all, proc_info.model_id,
                    gm.ResourceType.FILE, file_space_id, file_res_id,
                    pd_incharge=self.os_name
                )

    def __add_cgroup_resource_spaces(self, kernel_id: int):
        """
        Model cgroups as PAGE_QUOTA resource spaces.
        Processes in the same cgroup share a resource space and can exhaust each other's quota.
        """
        # cgroup_path -> resource space ID
        cgroup_to_space = {}

        for proc_info in self.procs.values():
            cpath = proc_info.cgroup_path
            if not cpath:
                continue

            if cpath not in cgroup_to_space:
                space_id = self.model.add_resource_space_node(gm.ResourceType.PAGE_QUOTA)
                cgroup_to_space[cpath] = space_id
                # Kernel holds (manages) the cgroup resource space
                self.model.add_hold_edge(
                    gm.perms_all, kernel_id, gm.ResourceType.PAGE_QUOTA, space_id,
                    pd_incharge=self.os_name
                )

            space_id = cgroup_to_space[cpath]
            # Process is subject to this cgroup's quota
            self.model.add_hold_edge(
                gm.perms_all, proc_info.model_id, gm.ResourceType.PAGE_QUOTA, space_id,
                pd_incharge=self.os_name
            )

    # Add the devices
    def __add_devices(self, kernel_id: int ):
        for (start, end), device_info in self.devices.items():
            device_info.model_id = self.model.add_resource_space_node(
                gm.ResourceType.MO
            )
            self.model.add_hold_edge(
                gm.perms_all,
                kernel_id,
                gm.ResourceType.MO,
                device_info.model_id,
                pd_incharge=self.os_name,
            )
    def __add_PMRS(self, pmr_mapping_type: MappingType, kernel_id: int):
        # Add the PMRs
        for (start, end), pmr_info in self.pmrs.items():
            n_pages = size_to_pages(end - start)

            if pmr_mapping_type is MappingType.CO_CONTIGUOUS:
                # The region is a node
                # PMR regions have already been split to be co-contiguous
                pmr_node_id = self.model.add_mo_node(
                    pmr_info.device.model_id, start, n_pages
                )
                pmr_info.model_id.append(pmr_node_id)
                self.model.add_hold_edge(
                    gm.perms_all,
                    kernel_id,
                    gm.ResourceType.MO,
                    pmr_info.device.model_id,
                    pmr_node_id,
                    pd_incharge=self.os_name,
                )
            elif pmr_mapping_type is MappingType.CONTIGUOUS:
                assert 0, "Contiguous mapping type for PMR is not currently supported"
            elif pmr_mapping_type is MappingType.PER_PAGE:
                # Every page is a node
                for i in range(n_pages):
                    pmr_info.model_id.append(
                        self.model.add_mo_node(
                            pmr_info.device.model_id, start + gm.page_size * i, 1
                        )
                    )

    # Add the processes
    def __add_processes(self, 
                        pmr_mapping_type: MappingType, 
                        vmr_mapping_type: MappingType, 
                        kernel_id: int):

        for process_info in self.procs.values():
            # Add the PD
            pd_id = self.model.add_pd_node(process_info.name, process_info.pid_in_host)
            process_info.model_id = pd_id

            # Add the address space
            process_info.ads.model_id = self.model.add_resource_space_node(
                gm.ResourceType.VMR
            )
            self.model.add_hold_edge(
                gm.perms_all,
                kernel_id,
                gm.ResourceType.VMR,
                process_info.ads.model_id,
                pd_incharge=self.os_name,
            )

            ads_id = process_info.ads.model_id
            mapped_devices = set()

            # PD can request from its address space
            self.model.add_request_edge(
                pd_id, kernel_id, gm.ResourceType.VMR, ads_id, 
                pd_incharge=self.os_name
            )

            # Add the VMRs
            for (start, end), vmr_info in process_info.ads.vmrs.items():
                n_pages = size_to_pages(end - start)
                perms = perms_to_model_perms(vmr_info.perms)

                vmr_node_id = 0

                # Contiguous VMR level
                if vmr_mapping_type is MappingType.CONTIGUOUS:
                    vmr_node_id = self.model.add_vmr_node(
                        ads_id, pathname_to_vmr_type(vmr_info.pathname), n_pages, start
                    )
                    self.model.add_hold_edge(
                        gm.perms_all,
                        kernel_id,
                        gm.ResourceType.VMR,
                        ads_id,
                        vmr_node_id,
                        pd_incharge=self.os_name,
                    )
                    self.model.add_hold_edge(
                        perms,
                        pd_id,
                        gm.ResourceType.VMR,
                        ads_id,
                        vmr_node_id,
                        pd_incharge=self.os_name,
                    )
                    vmr_info.model_id.append(vmr_node_id)

                for (sub_start, sub_end), sub_vmr_info in vmr_info.sub_vmrs.items():
                    sub_n_pages = size_to_pages(sub_end - sub_start)

                    # Co-contiguous VMR level
                    if vmr_mapping_type is MappingType.CO_CONTIGUOUS:
                        vmr_node_id = self.model.add_vmr_node(
                            ads_id,
                            pathname_to_vmr_type(vmr_info.pathname),
                            sub_n_pages,
                            sub_start,
                        )
                        self.model.add_hold_edge(
                            gm.perms_all,
                            kernel_id,
                            gm.ResourceType.VMR,
                            ads_id,
                            vmr_node_id,
                            pd_incharge=self.os_name,
                        )
                        self.model.add_hold_edge(
                            perms,
                            pd_id,
                            gm.ResourceType.VMR,
                            ads_id,
                            vmr_node_id,
                            pd_incharge=self.os_name,
                        )
                        vmr_info.model_id.append(vmr_node_id)

                    if (
                        vmr_mapping_type is MappingType.PER_PAGE
                        or pmr_mapping_type is MappingType.PER_PAGE
                    ):
                        # Need to iterate through all the pages
                        for i in range(sub_n_pages):
                            page_vaddr = sub_start + gm.page_size * i

                            if vmr_mapping_type is MappingType.PER_PAGE:
                                vmr_node_id = self.model.add_vmr_node(
                                    ads_id,
                                    pathname_to_vmr_type(vmr_info.pathname),
                                    1,
                                    page_vaddr,
                                )
                                self.model.add_hold_edge(
                                    gm.perms_all,
                                    kernel_id,
                                    gm.ResourceType.VMR,
                                    ads_id,
                                    vmr_node_id,
                                    pd_incharge=self.os_name,
                                )
                                self.model.add_hold_edge(
                                    perms,
                                    pd_id,
                                    gm.ResourceType.VMR,
                                    ads_id,
                                    vmr_node_id,
                                )
                                vmr_info.model_id.append(vmr_node_id)

                            if sub_vmr_info.mapped:
                                if pmr_mapping_type is MappingType.PER_PAGE:
                                    sub_pmr_start = sub_vmr_info.pmr[0]
                                    page_paddr = sub_pmr_start + gm.page_size * i

                                    # Fetch the pmr every time, since the PMR may have been split
                                    (pmr_start, pmr_end), pmr_info = self.pmrs.get(
                                        page_paddr
                                    )
                                    mapped_devices.add(pmr_info.device.model_id)

                                    # Maps to one page
                                    pmr_page_idx = size_to_pages(page_paddr - pmr_start)
                                    pmr_node_id = pmr_info.model_id[pmr_page_idx]

                                    # Find the model state ID for the relevant page in the PMR
                                    self.model.add_map_edge(
                                        gm.ResourceType.VMR,
                                        gm.ResourceType.MO,
                                        ads_id,
                                        pmr_info.device.model_id,
                                        vmr_node_id,
                                        pmr_node_id,
                                        pd_incharge=self.os_name,
                                    )
                                else:
                                    self.__map_vmr_to_pmrs(
                                        mapped_devices,
                                        ads_id,
                                        vmr_node_id,
                                        *sub_vmr_info.pmr,
                                    )
                    elif sub_vmr_info.mapped:
                        self.__map_vmr_to_pmrs(
                            mapped_devices, ads_id, vmr_node_id, *sub_vmr_info.pmr
                        )

            # Add map edge from address space to the devices
            for device_id in mapped_devices:
                self.model.add_map_edge(
                    gm.ResourceType.VMR,
                    gm.ResourceType.MO,
                    ads_id,
                    device_id,
                    pd_incharge=self.os_name,
                )

    # Add All PID Namespaces
    def __add_pid_namespaces(self, kernel_id: int):

        # Create all the PID NS resources, resources_spaces, map_edges, and subset edgs.
        # We will add hold edges when we iterate throught the loops of processes.
        # 1. Create a new ResourceServer for each PID NS
        for ns in self.namespaces.values():
            if ns.type != NamespaceType.PID:
                continue
            self.model.add_resource_space_node(gm.ResourceType.PID, ns.handle)
            self.model.add_hold_edge(gm.perms_all, kernel_id, gm.ResourceType.PID, ns.handle)

        # 2. Create resource nodes, one for each PID, in each NS
        # 3 Create subset edges
        # We re-run the loop to ensure that all resource-spaces are already created
        # When we add the resource space nodes.
        # A process in a child PID NS, will not show up in the ns.host_pids of the parent NS.

        for ns in self.namespaces.values():
            if ns.type != NamespaceType.PID:
                continue
            for pid in ns.host_pids:
                if len(ns.generic_data[pid]) == 1:
                    self.model.add_resource_node(gm.ResourceType.PID, ns.handle, pid)
                else:
                    pid_ns_info = ns.generic_data[pid]

                    parent_ns_pid, parent_ns_id = pid_ns_info[0]
                    child_ns_pid, child_ns_id = pid_ns_info[1]
                    print(f"ns.handle: {ns.handle}")
                    print(f"parent_ns_pid: {parent_ns_pid}, parent_ns_id: {parent_ns_id} " ,end = "")
                    print(f"child_ns_pid: {child_ns_pid}, child_ns_id: {child_ns_id}")

                    assert pid == parent_ns_pid
                    assert child_ns_id == ns.handle

                    self.model.add_resource_node(
                        gm.ResourceType.PID, parent_ns_id, parent_ns_pid
                    )
                    self.model.add_resource_node(
                        gm.ResourceType.PID, child_ns_id, child_ns_pid
                    )

        # 4 create map edges, if a process is in 2 NS, then it has two resource nodes.
        # We say parent and child
        for ns in self.namespaces.values():
            if ns.type not in [NamespaceType.PID, NamespaceType.MNT]:
                continue

            for pid in ns.host_pids:
                if ns.generic_data[pid] and len(ns.generic_data[pid]) > 1:
                    pid_ns_info = ns.generic_data[pid]

                    assert pid == pid_ns_info[0][0]  # Child
                    parent_ns_pid, parent_ns_id = pid_ns_info[0]
                    child_ns_pid, child_ns_id = pid_ns_info[1]

                    self.model.add_map_edge(
                        gm.ResourceType.PID,
                        gm.ResourceType.PID,
                        child_ns_id,
                        parent_ns_id)
                    self.model.add_map_edge(
                        gm.ResourceType.PID,
                        gm.ResourceType.PID,
                        child_ns_id,
                        parent_ns_id,
                        child_ns_pid,
                        parent_ns_pid,
                    )

        # Local function.
        def get_pid_ns_handle_for_proc(process_info: Process):
            for ns_info in process_info.namespaces.values():
                if ns_info.type == NamespaceType.PID:
                    return ns_info.handle

        # 4 Create hold edges; YY, doe it nest
        for process_info in self.procs.values():
            pid_ns_handle = get_pid_ns_handle_for_proc(process_info)
            ns_info = self.namespaces[pid_ns_handle]

            for pid in ns_info.host_pids:
                if len(ns_info.generic_data[pid]) > 1:
                    pid_ns_info = ns_info.generic_data[pid]

                    assert pid == pid_ns_info[0][0]  # Child
                    parent_ns_pid, parent_ns_id = pid_ns_info[0]
                    child_ns_pid, child_ns_id = pid_ns_info[1]

                self.model.add_hold_edge(
                    gm.perms_all,
                    process_info.model_id, 
                    gm.ResourceType.PID,
                    pid_ns_handle,
                    child_ns_pid)
    
    # Add All MNT Namespaces
    def __add_mnt_namespaces(self, kernel_id: int):
        pass

    def to_generic_model(
        self,
        vmr_mapping_type: MappingType,
        pmr_mapping_type: MappingType,
        guest: bool = False,
    ) -> gm.ModelGraph:
        """
        Convert the ProcFsData to a generic model state

        :param vmr_mapping_type: Option controls how to generate VMR nodes from the VMR regions
        :param pmr_mapping_type: Option controls how to generate PMR nodes from the PMR regions
        :return: The generic model state generated from this data
        """

        if guest:
            self.model = gm.ModelGraph(10000)
        else:
            self.model = gm.ModelGraph()

        # Add the kernel
        kernel_id = self.model.add_pd_node(self.os_name)
        self.__add_devices(kernel_id=kernel_id)
        self.__add_PMRS(pmr_mapping_type=pmr_mapping_type, kernel_id=kernel_id)
        self.__add_processes(
            pmr_mapping_type=pmr_mapping_type,
            vmr_mapping_type=vmr_mapping_type,
            kernel_id=kernel_id,
        )
        self.__add_inter_process_hold_edges()
        self.__add_file_resources(kernel_id=kernel_id)
        self.__add_cgroup_resource_spaces(kernel_id=kernel_id)
        # self.__add_pid_namespaces(kernel_id=kernel_id)
        # self.__add_mnt_namespaces(kernel_id=kernel_id)


        return self.model
