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
    ads: ProcAddressSpace = field(
        default_factory=lambda: ProcAddressSpace()
    )  # The process' address space
    namespaces: list[Namespace] = field(default_factory=lambda: list())
    model_id: int = 0  # The ID of this node in the model state, once added
    pid_in_ns: int = 0  # PID of the process according to its own PID namespace
    # The PID (in global PID namespace) will be the key of the dict this is in
    pid_mounts: list[pypfs.mount] = field(default_factory=lambda: list())


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
            pd_id = self.model.add_pd_node(process_info.name)
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
            for ns_info in process_info.namespaces:
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
        # self.__add_pid_namespaces(kernel_id=kernel_id)
        # self.__add_mnt_namespaces(kernel_id=kernel_id)


        return self.model
