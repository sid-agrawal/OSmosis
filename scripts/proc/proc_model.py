import os
import signal
import subprocess
from enum import Enum
import time
import math
from dataclasses import dataclass, field
import traceback
from utils import EasyDict, IntervalDict
from read_pagemap import get_va_pa_mappings, PageMapObj
from generic_model import *
import sys

sys.path.append("pfs/lib")
import pypfs

### CONFIGURATION ###
print_logs = False

class ProcessStartType(Enum):
    """
    Different ways of starting a process for the configuration
    These types need to be supported by run_process
    """
    
    NORMAL = 1     # start the process in the default way
    NEW_PID_NS = 2 # start the process in a new PID namespace
    
program_names: EasyDict = EasyDict(
    basic = "hello",
    static1 = "hello_static_1",
    static2 = "hello_static_2",
    malloc = "hello_malloc",
    mmap = "hello_mmap",
    print_pid = "hello_print_pid")

run_configs = [
    # 0: Basic hello
    [(program_names.basic, ProcessStartType.NORMAL), (program_names.basic, ProcessStartType.NORMAL)],
    # 1: Hello with malloc
    [(program_names.malloc, ProcessStartType.NORMAL), (program_names.malloc, ProcessStartType.NORMAL)],
    # 2: Hello with shared mem via mmap
    [(program_names.mmap, ProcessStartType.NORMAL), (program_names.mmap, ProcessStartType.NORMAL)],
    # 3: Hello linked statically
    [(program_names.static1, ProcessStartType.NORMAL), (program_names.static2, ProcessStartType.NORMAL)],
    # 4: Hello in different PID namespaces
    [(program_names.print_pid, ProcessStartType.NEW_PID_NS), (program_names.print_pid, ProcessStartType.NEW_PID_NS)],
]

to_run = run_configs[0]

def log(msg):
    if print_logs:
        print(msg)

### CONSTANTS ###
parent_pid_message = "Child PID in parent ns: "
child_pid_message = "Child PID in child ns: "
temp_output_file = "temp.txt" # used to get output from some c programs

### MODEL HELPER FUNCTIONS ###

pfs_obj = pypfs.procfs() # Interface to the PFS library

def pathname_to_vmr_type(pathname: str):
    """
    Convert a pathname to a VMR reservation type
    
    :param pathname: pathname of a VMR, as read from the /proc/pid/maps file
    """
    global program_names
    
    if pathname is None or len(pathname) == 0:
        return VmrType.NONE
    if pathname == "[heap]":
        return VmrType.HEAP
    elif pathname == "[stack]":
        return VmrType.STACK
    elif pathname == "[vvar]": # what is this?
        return VmrType.VVAR
    elif pathname == "[vdso]": # what is this?
        return VmrType.VDSO
    elif pathname == "[vsyscall]": # what is this?
        return VmrType.VSYSCALL
    elif any([(f"OSmosis/scripts/proc/{program_name}" in pathname) for program_name in program_names.__dict__.values()]):
        return VmrType.PROGRAM # I don't think code and data are separated
    elif pathname.startswith("/dev/shm"):
        return VmrType.SHM
    elif pathname.startswith("/usr/lib/") or pathname.endswith(".a") or pathname.endswith(".so"):
        return VmrType.LIB
    else:
        print(f"Warning: unknown pathname '{pathname}' for VMR")
        return VmrType.UNKNOWN
    
def perms_to_model_perms(perm: pypfs.mem_perm):
    """ 
    Convert a set of permissions from PFS to the generic model's Permissions object
    """
    perm_set = set()
    
    if perm.can_read:
        perm_set.add(Permission.R)
    if perm.can_write:
        perm_set.add(Permission.W)
    if perm.can_execute:
        perm_set.add(Permission.X)
    if perm.is_private:
        perm_set.add(Permission.P)
    if perm.is_shared:
        perm_set.add(Permission.S)
    
    return Permissions(perm_set)

def size_to_pages(size: int) -> int:
        """
        Convert the size of a region to the number of pages, assuming 4k pages
        
        :return: the number of pages
        """
        
        n_pages = size / page_size
        assert(n_pages % 1 == 0)
        return math.ceil(n_pages)

### DATA STORAGE CLASSES ###

@dataclass
class SubVMR:
    """Tracks a single contiguous mapping of a VMR to a contiguous PMR, or an unmapped VMR"""
    mapped: bool = False # Whether or not this VMR is mapped to a PMR
    pmr: tuple[int,int] = None # The PMR range that this VMR maps to
    
@dataclass
class VMR:
    """Tracks a VMR in an address space."""
    pathname: str    # What this VMR is for - a file, or a marker like '[heap]'
    perms: pypfs.mem_perm # Store of permissions for the VMR as given by pfs
    sub_vmrs: IntervalDict = field(default_factory=lambda: IntervalDict()) # Dict of contiguous mappings within this VMR
    # Address range is tracked by the IntervalDict
    model_id: list[int] = field(default_factory=list) # The ID(s) of this node in the model state, once added
    
@dataclass
class ProcAddressSpace:
    """Tracks a process' address space."""
    vmrs: IntervalDict = field(default_factory=lambda: IntervalDict()) # list of VMR in the address space
    model_id: int = 0 # The ID of this node in the model state, once added

class NamespaceType(Enum):
    UTS = 1
    USER = 2
    PID = 3
    NET = 4
    MNT = 5
    IPC = 6
    CGROUP = 7
    TIME = 8
    NONE = 9 # we choose to ignore some namespace types: pid_for_children and time_for_children

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
    
@dataclass
class Namespace:
    type: NamespaceType
    handle: int
    
@dataclass
class Process:
    """Tracks a process"""
    name: str # Name of the process
    ads: ProcAddressSpace = field(default_factory=lambda: ProcAddressSpace()) # The process' address space
    namespaces: list[Namespace] = field(default_factory=lambda: list())
    model_id: int = 0 # The ID of this node in the model state, once added
    pid_in_ns: int = 0 # PID of the process according to its own PID namespace
    # The PID (in global PID namespace) will be the key of the dict this is in
    
@dataclass 
class Device:
    """Tracks a physical memory device in the system"""
    size: int           # Size of the device, in bytes
    # Address range is tracked by the IntervalDict
    model_id: int = 0 # The ID of this node in the model state, once added

@dataclass
class PMR:
    """Tracks a PMR in the system"""
    device: Device # The Device this PMR is from
    # Address range is tracked by the IntervalDict
    model_id: list[int] = field(default_factory=list) # The ID(s) of this node in the model state, once added
    
    # Define copy for when PMRs get split
    def __copy__(self):
        result = PMR(self.device)
        
        return result

# Different ways to display VA / PA nodes in the graph
class MappingType(Enum):
    PER_PAGE = 1        # Every node is exactly one page
    CO_CONTIGUOUS = 2   # Show co-contiguous mapped regions as one VA / PA node
    CONTIGUOUS = 3      # Show contiguous regions as one node

class ProcFsData():
    """
    Intermediate repository for the relevant data from /proc for multiple processes
    This object can be converted to the generic ModelGraph
    """
    
    def __init__(self):
        self.namespaces = {} # dict from namespace handle to Namespace
        self.procs = {} # dict from PID to Process
        self.pmrs = IntervalDict() # list of PMR
        self.devices = IntervalDict() # list of physical memory devices, ProcDev
    
    def __map_vmr_to_pmrs(self, mapped_devices: set, ads_id: int, vmr_node_id: int, pmr_range_start: int, pmr_range_end: int):
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
        pmrs = data.pmrs.get_interval(pmr_range_start, pmr_range_end)
        
        for (pmr_start, pmr_end), pmr_info  in pmrs:
            mapped_devices.add(pmr_info.device.model_id)
            self.model.add_map_edge(ResourceType.VMR, ResourceType.MO, ads_id, pmr_info.device.model_id, vmr_node_id, pmr_info.model_id[0])
        
    def to_generic_model(self, vmr_mapping_type: MappingType, pmr_mapping_type: MappingType) -> ModelGraph:
        """
        Convert the ProcFsData to a generic model state
        
        :param vmr_mapping_type: Option controls how to generate VMR nodes from the VMR regions
        :param pmr_mapping_type: Option controls how to generate PMR nodes from the PMR regions
        :return: The generic model state generated from this data
        """
        
        self.model = ModelGraph()
        
        # Add the kernel
        kernel_id = self.model.add_pd_node("Kernel")
        
        # Add the devices
        for (start, end), device_info in self.devices.items():
            device_info.model_id = self.model.add_resource_space_node(ResourceType.MO)
                    
        # Add the PMRs
        for (start, end), pmr_info in self.pmrs.items():
            n_pages = size_to_pages(end - start)
            
            if pmr_mapping_type is MappingType.CO_CONTIGUOUS:
                # The region is a node
                # PMR regions have already been split to be co-contiguous
                pmr_node_id = self.model.add_mo_node(pmr_info.device.model_id, start, n_pages)
                pmr_info.model_id.append(pmr_node_id)
                self.model.add_hold_edge(perms_all, kernel_id, ResourceType.MO, pmr_info.device.model_id, pmr_node_id)
            elif pmr_mapping_type is MappingType.CONTIGUOUS:
                assert 0, "Contiguous mapping type for PMR is not currently supported"
            elif pmr_mapping_type is MappingType.PER_PAGE:
                # Every page is a node
                for i in range(n_pages):
                    pmr_info.model_id.append(self.model.add_mo_node(pmr_info.device.model_id, start + page_size * i, 1))
                
        # Add the processes
        for process_info in self.procs.values():
            # Add the PD
            pd_id = self.model.add_pd_node(process_info.name)
            
            # Add the address space
            process_info.ads.model_id = self.model.add_resource_space_node(ResourceType.VMR)
            ads_id = process_info.ads.model_id
            mapped_devices = set()
            
            # PD can request from its address space
            self.model.add_request_edge(pd_id, kernel_id, ResourceType.VMR, ads_id)
            
            # Add the VMRs
            for (start, end), vmr_info in process_info.ads.vmrs.items():
                n_pages = size_to_pages(end - start)
                perms = perms_to_model_perms(vmr_info.perms)
                
                vmr_node_id = 0
                
                # Contiguous VMR level
                if vmr_mapping_type is MappingType.CONTIGUOUS:
                    vmr_node_id = self.model.add_vmr_node(ads_id, pathname_to_vmr_type(vmr_info.pathname), n_pages)
                    self.model.add_hold_edge(perms_all, kernel_id, ResourceType.VMR, ads_id, vmr_node_id)
                    self.model.add_hold_edge(perms, pd_id, ResourceType.VMR, ads_id, vmr_node_id)
                    vmr_info.model_id.append(vmr_node_id)
                
                for (sub_start, sub_end), sub_vmr_info in vmr_info.sub_vmrs.items():
                    sub_n_pages = size_to_pages(sub_end - sub_start)
                    
                    # Co-contiguous VMR level
                    if vmr_mapping_type is MappingType.CO_CONTIGUOUS:
                        vmr_node_id = self.model.add_vmr_node(ads_id, pathname_to_vmr_type(vmr_info.pathname), sub_n_pages)
                        self.model.add_hold_edge(perms_all, kernel_id, ResourceType.VMR, ads_id, vmr_node_id)
                        self.model.add_hold_edge(perms, pd_id, ResourceType.VMR, ads_id, vmr_node_id)
                        vmr_info.model_id.append(vmr_node_id)
                        
                    if vmr_mapping_type is MappingType.PER_PAGE or pmr_mapping_type is MappingType.PER_PAGE:
                        # Need to iterate through all the pages
                        for i in range(sub_n_pages):
                            page_vaddr = sub_start + page_size * i
                            
                            if vmr_mapping_type is MappingType.PER_PAGE:
                                vmr_node_id = self.model.add_vmr_node(ads_id, pathname_to_vmr_type(vmr_info.pathname), 1)
                                self.model.add_hold_edge(perms_all, kernel_id, ResourceType.VMR, ads_id, vmr_node_id)
                                self.model.add_hold_edge(perms, pd_id, ResourceType.VMR, ads_id, vmr_node_id)
                                vmr_info.model_id.append(vmr_node_id)
                        
                            if sub_vmr_info.mapped:
                                if pmr_mapping_type is MappingType.PER_PAGE:
                                    sub_pmr_start = sub_vmr_info.pmr[0]
                                    page_paddr = sub_pmr_start + page_size * i
                                    
                                    # Fetch the pmr every time, since the PMR may have been split
                                    (pmr_start, pmr_end), pmr_info = self.pmrs.get(page_paddr)
                                    mapped_devices.add(pmr_info.device.model_id)
                                
                                    # Maps to one page
                                    pmr_page_idx = size_to_pages(page_paddr - pmr_start)
                                    pmr_node_id = pmr_info.model_id[pmr_page_idx]
                                    
                                    # Find the model state ID for the relevant page in the PMR
                                    self.model.add_map_edge(ResourceType.VMR, ResourceType.MO, ads_id, pmr_info.device.model_id, vmr_node_id, pmr_node_id)
                                else:
                                    self.__map_vmr_to_pmrs(mapped_devices, ads_id, vmr_node_id, *sub_vmr_info.pmr)
                    elif sub_vmr_info.mapped:
                        self.__map_vmr_to_pmrs(mapped_devices, ads_id, vmr_node_id, *sub_vmr_info.pmr)
                
            # Add map edge from address space to the devices
            for device_id in mapped_devices:
                self.model.add_map_edge(ResourceType.VMR, ResourceType.MO, ads_id, device_id)
    
        return self.model

### RUNNING PROCESSES & EXTRACTING DATA ###
    
def run_process(name: str, start_type: ProcessStartType = False) -> tuple[int,int]:
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
            ["sudo", "./create_proc_in_ns", name, temp_output_file],
            stderr=subprocess.PIPE)
        
        # The process will output the pid
        output_file_read = open(temp_output_file, "r")
        while True:
            # if something goes wrong, this might hang
            line = output_file_read.readline().strip()
            
            if line:
                log(line)

            if line.startswith(parent_pid_message):
                pid = int(line[len(parent_pid_message):])
                log(f"PID in parent process: {pid}")
                break
            
            # This is not needed because we can get the child PID from /proc/pid/status
            #elif line.startswith(child_pid_message):
            #    pid_in_child = int(line[len(child_pid_message):])
            #    log(f"PID in child process: {pid_in_child}")
            
            elif not line:
                time.sleep(2)
    else:
        process = subprocess.Popen(
            f'./{name}',
            text=True)

        pid = process.pid
    
    time.sleep(2) # Give the process time to get set up
    
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
            print(f"[{map.start_address}, {map.end_address}]")
            print(f"- Device: {map.device}")
            print(f"- Pathname: {map.pathname}")
            
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
            
    return status

def read_mountinfo_file(pid: int, should_print: bool = False) -> list[pypfs.mount]:
    """
    Parse a /proc/pid/status file
    
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
        print("MOUNTS")
        for mount in mounts:
            print(f"Mount {mount.id}")
            print(f"- Parent: {mount.parent_id}")
            print(f"- Device: {mount.device}")
            print(f"- Root: {mount.root}")
            print(f"- Source: {mount.source}")
            print(f"- Point: {mount.point}")
            
    return mounts

def extract_namespaces(data: ProcFsData, pid: int, should_print: bool = False):
    """
    Find the namespaces this process belongs to
    Add to global data if not already present, and add to the process' list of namespaces
    
    :param pid: PID of the process to check for namespaces
    :param should_print: If true, print all of the namespaces found
    """
    
    task = pfs_obj.get_task(pid)
    ns_data = task.get_ns()
    
    # This only gets us the namespace type and handle
    # To find what the parent NS is, you can use ioctl, as shown in get_ns_info.c
    # I'm not sure if there is any other way to do this
    
    namespaces = []
    for (path, handle) in ns_data.items():
        namespace_type = str_to_namespace_type[path]
        
        if namespace_type == NamespaceType.NONE:
            # Ignore some namespace types
            continue
        
        if handle in data.namespaces:
            assert data.namespaces[handle].type == namespace_type, "duplicate handle for different ns"
            namespaces.append(data.namespaces[handle])
        else:
            namespace = Namespace(namespace_type, handle)
            namespaces.append(namespace)
            data.namespaces[handle] = namespace            
            
    if should_print:
        print("NAMESPACES")
        for ns_info in namespaces:
            print(f"- NS: type {ns_info.type.name}, handle {ns_info.handle}")
            
    data.procs[pid].namespaces = namespaces
    
def read_pagemap_file(pid: int, should_print: bool = False) -> list[PageMapObj]:
    """
    Parse a /proc/pid/pagemaps file
    
    :param process: a process returned from run_process
    :param should_print: if true, prints the raw and parsed file
    :return: a list of objects representing the VA and VA->PA regions in the process' address space
    """
    results = get_va_pa_mappings(pid)
    
    if should_print:
        print(f'VA-PA MAPPINGS')
        print("-" * 40)
        for pagemap in results:
            print(f"VMR {pagemap.vaddr:16x}-{pagemap.vaddr + pagemap.size:16x}", end="")
            if pagemap.mapped:
                print(f'{pagemap.paddr:16x}-{pagemap.paddr + pagemap.size:16x}')
            else:
                print()
        print("-" * 40)
    
    return results
    
def extract_memory_data(data: ProcFsData, pid: int, should_print = False):
    """
    Get the VMR, PMR, and Device data for a particular process
    
    :param data: the data object
    :param pid: the process to query about
    """
    
    print(f"Extract memory data for process {pid}")
    maps = read_maps_file(pid, should_print)
    pagemaps = read_pagemap_file(pid, should_print)
    pagemap_iter = iter(pagemaps)
    next_pagemap = next(pagemap_iter, None)
    
    for map_entry in maps:
        vmr_info = VMR(map_entry.pathname, map_entry.perm)  
        vmr_start_addr = map_entry.start_address
        vmr_end_addr = map_entry.end_address
        
        log(f"Checking VMR {vmr_start_addr:16x}-{vmr_end_addr:16x}, {vmr_info.pathname}")
        
        # Could get permissions here
        
        # Find all PMRs for this VMR
        while next_pagemap is not None:
            pagemap = next_pagemap
            
            log(f"Checking sub-VMR {pagemap.vaddr:16x}-{pagemap.vaddr + pagemap.size:16x}")
            
            # Check if we should move to the next VMR before processing this PMR
            if pagemap.vaddr >= vmr_end_addr:
                break
            
            next_pagemap = next(pagemap_iter, None)

            # Simple tracking of unmapped region
            if not pagemap.mapped:
                vmr_info.sub_vmrs.put(pagemap.vaddr, pagemap.vaddr + pagemap.size, SubVMR(mapped=False))
                continue
            
            log(f"Checking PMR {pagemap.paddr:16x}-{pagemap.paddr + pagemap.size:16x}")
            
            # Track the PMR
            pmr_start_addr = pagemap.paddr
            pmr_end_addr = pagemap.paddr + pagemap.size
            vmr_info.sub_vmrs.put(pagemap.vaddr, pagemap.vaddr + pagemap.size, SubVMR(mapped=True, pmr = (pmr_start_addr, pmr_end_addr)))
            
            # Split if start overlaps with an existing pmr 
            (left_start, left_end), left_pmr_info = data.pmrs.get(pmr_start_addr)
            
            if left_pmr_info is not None:
                if left_start != pmr_start_addr:
                    data.pmrs.split_interval(pmr_start_addr)
                    
                pmr_start_addr = left_end
                
            # Split if end overlaps with an existing pmr
            if pmr_start_addr < pmr_end_addr:
                (right_start, right_end), right_pmr_info = data.pmrs.get(pmr_end_addr - 1)
                
                if right_pmr_info is not None:
                    if right_start != pmr_end_addr and right_end != pmr_end_addr:
                        data.pmrs.split_interval(pmr_start_addr)
                        
                    pmr_end_addr = right_start
                
            # Insert the device, if not already tracked
            _, device_info = data.devices.get(pagemap.device_addr)
            
            if device_info is None:
                device_info = Device(size=pagemap.device_size)
                data.devices.put(pagemap.device_addr, pagemap.device_addr + pagemap.device_size, device_info)
                
            # Add a new entry for any remaining interval of the pmr
            if pmr_start_addr < pmr_end_addr:
                pmr_info = PMR(device_info)
                data.pmrs.put(pmr_start_addr, pmr_end_addr, pmr_info)
                        
        data.procs[pid].ads.vmrs.put(vmr_start_addr, vmr_end_addr, vmr_info)
    
    if print_logs:
        print(data.procs[pid].ads.vmrs)
        print(data.pmrs)
        print(data.devices)

def extract_from_status(data: ProcFsData, pid: int, should_print = False):
    status = read_status_file(pid, should_print)
    assert pid == status.ns_pid[0], "PID from status should have been the same as the given PID"
    data.procs[pid].pid_in_ns = status.ns_pid[1] if len(status.ns_pid) > 1 else pid
    
def extract_process_data(data: ProcFsData, pid: int, name: str, should_print = False):
    """
    Extract data from procfs for a particular process
    
    :param data: the data object
    :param pid_in_parent: PID of the process in the global namespace
    :param pid_in_child: PID of the process in the child namespace
    """
    process = Process(name)
    data.procs[pid] = process
    
    extract_namespaces(data, pid, should_print) # namespaces do not get incorporated into the generic model state yet
    extract_from_status(data, pid, should_print)
    extract_memory_data(data, pid, should_print)
    
    if should_print:
        print(f"Extracted process {pid}:")
        print(data.procs[pid])
    
def terminate_process(pid: int):
    """ 
    Terminate the process with the given pid
    """
    os.kill(pid, signal.SIGTERM) #or signal.SIGKILL 

if __name__ == "__main__":
    data = ProcFsData()
    pids = [run_process(name, start_type) for (name, start_type) in to_run]
    
    try:
        for (name, _), pid in zip(to_run, pids):
            extract_process_data(data, pid, name, True)
            # read_mountinfo_file(pid, True)  # mountinfo is not part of the model state, but we can view it
    except Exception as e:
        print("Error printing stats for hello")
        print(repr(e))
        traceback.print_exc()
    
    for pid in pids:
        terminate_process(pid)
    
    data.to_generic_model(MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS).to_csv()