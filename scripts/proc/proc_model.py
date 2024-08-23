import subprocess
import json
import jc
from enum import Enum
import time
import bisect
import copy
import math
from dataclasses import dataclass, asdict, field
from read_pagemap import get_va_pa_mappings, PageMapObj
from generic_model import *

### CONFIGURATION ###
print_logs = False

def log(msg):
    if print_logs:
        print(msg)

### UTILITY CLASSES ###

class EasyDict():
    """
    Dict where entries can be accessed with dot notation
    """
    
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return self.__dict__.get(name)
    
    def __setattr__(self, name, val):
        self.__dict__[name] = val
    
    def __delattr__(self, name):
        del self.__dict__[name]
 
    def __str__(self):
        return self.__dict__.__str__()
    
    def __repr__(self):
        return self.__dict__.__str__()

class IntervalDict():
    """
    Dict where a range of numbers map to a value 
    
    Supports put, get, and split (not delete)
    """
    
    def __init__(self):
        self.endpoint_list = []
        self.dict = {}
        self.list_len = 0
    
    def put(self, start: int, end: int, value: any):
        """
        Add a value to the dictionary for an interval key
        This will fail if it overlaps an existing interval in the dict
        
        :param start: start of the interval key
        :param end: end of the interval key
        :param value: value to add to the dict for the specified interval
        """
        
        insert_idx = bisect.bisect_right(self.endpoint_list, start)
        
        if self.list_len > insert_idx and self.endpoint_list[insert_idx] < end:
            # Interval overlaps another
            print(f'Overlap [{start:16x},{end:16x}]')
            print(self)
            raise ValueError("Overlap interval")
        elif insert_idx > 0 and self.endpoint_list[insert_idx - 1] in self.dict:
            # This start point is already defined
            print(f'Overlap [{start:16x},{end:16x}]')
            print(self)
            raise ValueError("Overlap interval")
        
        # Insert the end point, if needed
        if self.list_len <= insert_idx or self.endpoint_list[insert_idx] != end:
            self.endpoint_list.insert(insert_idx, end)
            self.list_len += 1
        
        # Insert the start point, if needed
        if insert_idx == 0 or self.endpoint_list[insert_idx - 1] != start:
            self.endpoint_list.insert(insert_idx, start)
            self.list_len += 1
            
        # Insert the value to the dict
        self.dict[start] = value
        
    def get(self, key: int) -> tuple[tuple[int,int], any]:
        """
        Get the value for the interval containing the key
        
        :param key: the value to search for in intervals
        :return: a tuple of the interval and value, ((interval_start, interval_end), val)
                 or, if the key is not in any interval, ((None, None), None)
        """
        
        idx = bisect.bisect_right(self.endpoint_list, key)
        
        if idx == 0 or idx >= self.list_len:
            # Index not within any interval
            return (None, None), None
        
        val = self.dict.get(self.endpoint_list[idx - 1])
        
        if val:
            return (self.endpoint_list[idx - 1], self.endpoint_list[idx]), val
        else:
            return (None, None), None
        
    def get_interval(self, start: int, end: int) -> list[tuple[tuple[int,int], any]]:
        """
        Get all intervals and values contained within the specified interval
        
        :param start: start of the range to search for in intervals
        :param end: end of the range to search for in intervals
        :return: a list of tuples of the interval and value, ((interval_start, interval_end), val)
                 or, if the range does not contain any interval, an empty list
        """
        
        left_idx = bisect.bisect_left(self.endpoint_list, start)
        right_idx = bisect.bisect_left(self.endpoint_list, end)
        
        results = []
        for i in range(left_idx, right_idx + 1):
            val = self.dict.get(self.endpoint_list[i])
        
            if val:
                results.append(((self.endpoint_list[i], self.endpoint_list[i + 1]), val))

        return results
    
    def split_interval(self, split_at: int) -> any:
        """
        Splits an interval by the given split_at point
        The right split will get a copy of the original value
        
        :param split_at: point at which to split the interval
        :return: deep copy of the original interval's value, which is now the right split's value
        """
        
        idx = bisect.bisect_right(self.endpoint_list, split_at)
        val = self.dict.get(self.endpoint_list[idx - 1])
        
        assert val is not None, "Can't split a nonexistant interval"
        assert self.endpoint_list[idx - 1] != split_at and self.endpoint_list[idx] != split_at, "Can't split an interval at the endpoint"
        
        bisect.insort(self.endpoint_list, split_at)
        val_copy = copy.deepcopy(val)
        self.dict[split_at] = val_copy
        
        return val_copy
    
    def items(self) -> list[tuple[tuple[int,int], any]]:
        """
        Get a list of all the intervals and values in the dict
        """
        items = []
        
        for i in range(self.list_len - 1):
            value = self.dict.get(self.endpoint_list[i])
            
            if value:
                items.append(((self.endpoint_list[i],self.endpoint_list[i+1]), value))
    
        return items
    
    def __str__(self):
        lines = []
        for i in range(self.list_len - 1):
            value = self.dict.get(self.endpoint_list[i])
            
            if value:
                lines.append(f'-[{self.endpoint_list[i]:16x},{self.endpoint_list[i+1]:16x}]: {value}')

        return '\n'.join(lines)

### MODEL HELPER FUNCTIONS ###

def pathname_to_vmr_type(pathname: str):
    """
    Convert a pathname to a VMR reservation type
    
    :param pathname: pathname of a VMR, as read from the /proc/pid/maps file
    """
    
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
    elif "OSmosis/scripts/proc/" in pathname:
        return VmrType.PROGRAM # I don't think code and data are separated
    elif pathname.startswith("/usr/lib/"):
        return VmrType.LIB
    else:
        print(f"Warning: unknown pathname '{pathname}' for VMR")
        return VmrType.UNKNOWN

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
    pathname: str   # What this VMR is for - a file, or a marker like '[heap]'
    sub_vmrs: IntervalDict = field(default_factory=lambda: IntervalDict()) # Dict of contiguous mappings within this VMR
    # Address range is tracked by the IntervalDict
    model_id: list[int] = field(default_factory=list) # The ID(s) of this node in the model state, once added
    
@dataclass
class ProcAddressSpace:
    """Tracks a process' address space."""
    vmrs: IntervalDict = field(default_factory=lambda: IntervalDict()) # list of VMR in the address space
    model_id: int = 0 # The ID of this node in the model state, once added

@dataclass
class Process:
    """Tracks a process"""
    name: str # Name of the process
    ads: ProcAddressSpace = field(default_factory=lambda: ProcAddressSpace()) # The process' address space
    model_id: int = 0 # The ID of this node in the model state, once added
    
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
        
    # n_pages = (end_addr - start_addr) / page_size
    # assert(n_pages % 1 == 0)
    # vmr_info.pages = math.ceil(n_pages)
    
    def __init__(self):
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
                self.model.add_hold_edge(kernel_id, ResourceType.MO, pmr_info.device.model_id, pmr_node_id)
            elif pmr_mapping_type is MappingType.CONTIGUOUS:
                assert 0, "Contiguous mapping type for PMR is not currently supported"
            elif pmr_mapping_type is MappingType.PER_PAGE:
                # Every page is a node
                for i in range(n_pages):
                    pmr_info.model_id.append(self.model.add_mo_node(pmr_info.device.model_id, start + page_size * i, 1))
        
        # Add the processes
        for pid, process_info in self.procs.items():
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
                
                vmr_node_id = 0
                
                # Contiguous VMR level
                if vmr_mapping_type is MappingType.CONTIGUOUS:
                    vmr_node_id = self.model.add_vmr_node(ads_id, pathname_to_vmr_type(vmr_info.pathname), n_pages)
                    self.model.add_hold_edge(kernel_id, ResourceType.VMR, ads_id, vmr_node_id)
                    self.model.add_hold_edge(pd_id, ResourceType.VMR, ads_id, vmr_node_id)
                    vmr_info.model_id.append(vmr_node_id)
                
                for (sub_start, sub_end), sub_vmr_info in vmr_info.sub_vmrs.items():
                    sub_n_pages = size_to_pages(sub_end - sub_start)
                    
                    # Co-contiguous VMR level
                    if vmr_mapping_type is MappingType.CO_CONTIGUOUS:
                        vmr_node_id = self.model.add_vmr_node(ads_id, pathname_to_vmr_type(vmr_info.pathname), sub_n_pages)
                        self.model.add_hold_edge(kernel_id, ResourceType.VMR, ads_id, vmr_node_id)
                        self.model.add_hold_edge(pd_id, ResourceType.VMR, ads_id, vmr_node_id)
                        vmr_info.model_id.append(vmr_node_id)
                        
                    if vmr_mapping_type is MappingType.PER_PAGE or pmr_mapping_type is MappingType.PER_PAGE:
                        # Need to iterate through all the pages
                        for i in range(sub_n_pages):
                            page_vaddr = sub_start + page_size * i
                            
                            if vmr_mapping_type is MappingType.PER_PAGE:
                                vmr_node_id = self.model.add_vmr_node(ads_id, pathname_to_vmr_type(vmr_info.pathname), 1)
                                self.model.add_hold_edge(kernel_id, ResourceType.VMR, ads_id, vmr_node_id)
                                self.model.add_hold_edge(pd_id, ResourceType.VMR, ads_id, vmr_node_id)
                                vmr_info.model_id.append(vmr_node_id)
                        
                            if sub_vmr_info.mapped:
                                if pmr_mapping_type is MappingType.PER_PAGE:
                                    sub_pmr_start = sub_vmr_info.pmr[0]
                                    page_paddr = sub_pmr_start + page_size * i
                                    
                                    # Fetch the pmr every time, since the PMR may have been split
                                    (pmr_start, pmr_end), pmr_info = self.model.pmrs.get(page_paddr)
                                    mapped_devices.add(pmr_info.device.model_id)
                                
                                    # Maps to one page
                                    pmr_page_idx = size_to_pages(page_paddr - pmr_start)
                                    pmr_node_id = pmr_info.model_id[pmr_page_idx + i]
                                    
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

def run_process(name) -> subprocess.Popen:
    """
    Start a process from this directory (which should be the OSmosis/scripts/proc directory)
    Output will go to stdout
    
    :return: The process object
    """
    print(f'Starting process "{name}"')
    
    process = subprocess.Popen(
        f'./{name}',
        text=True)
    
    time.sleep(2) # Give the process time to get set up
    
    return process

def parse_file(process: subprocess.Popen, filetype: str, should_print: bool = False) -> list[EasyDict]:
    """
    Parse a file that is supported by the jc package
    
    :param process: a process returned from run_process
    :param filetype: the name of the file under `/proc/pid/` to parse
    :param should_print: if true, prints the raw and parsed file
    :return: a list of dicts representing the parsed file
    """
    
    filename = f'/proc/{process.pid}/{filetype}'
    data = ""
    
    print(f'Opening file "{filename}"')
    with open(filename, 'r') as file:
        data = file.read()
    
    print(f'Opened file "{filename}"')
        
    results = jc.parse(f'proc_pid_{filetype}',data)
    
    if should_print:
        print(f'FILE: {filetype}')
        print(f'Plain Data')
        print("-" * 40)
        print(data)
        print("-" * 40)
        print(json.dumps(results, indent=4))
        print("-" * 40)
    
    return [EasyDict(**result) for result in results]

def read_maps_file(process: subprocess.Popen, should_print: bool = False) -> list[EasyDict]:
    """
    Parse a /proc/pid/maps file
    
    :param process: a process returned from run_process
    :param should_print: if true, prints the raw and parsed file
    :return: a list of dicts representing the parsed file
    """
    return parse_file(process, 'maps', should_print)
    
def read_smaps_file(process: subprocess.Popen, should_print: bool = False) -> list[EasyDict]:
    """
    Parse a /proc/pid/smaps file
    
    :param process: a process returned from run_process
    :param should_print: if true, prints the raw and parsed file
    :return: a list of dicts representing the parsed file
    """
    return parse_file(process, 'smaps', should_print)
    
def read_pagemap_file(process: subprocess.Popen, should_print: bool = False) -> list[PageMapObj]:
    """
    Parse a /proc/pid/pagemaps file
    
    :param process: a process returned from run_process
    :param should_print: if true, prints the raw and parsed file
    :return: a list of objects representing the VA and VA->PA regions in the process' address space
    """
    results = get_va_pa_mappings(process.pid)
    
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
    
def extract_memory_data(data: ProcFsData, process: subprocess.Popen):
    """
    Get the VMR, PMR, and Device data for a particular process
    
    :param data: the data object
    :param process: the process to query about
    """
    
    print(f"Extract memory data for process {process.pid}")
    maps = read_maps_file(process)
    #smaps = read_smaps_file(hello)
    pagemaps = read_pagemap_file(process)
    pagemap_iter = iter(pagemaps)
    next_pagemap = next(pagemap_iter, None)
    
    for map_entry in maps:
        vmr_info = VMR(map_entry.pathname)  
        vmr_start_addr = int(map_entry.start, 16)
        vmr_end_addr = int(map_entry.end, 16)
        
        log(f"Checking VMR {vmr_start_addr:16x}-{vmr_end_addr:16x}")
        
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
            (right_start, right_end), right_pmr_info = data.pmrs.get(pmr_end_addr)
            
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
                        
        data.procs[process.pid].ads.vmrs.put(vmr_start_addr, vmr_end_addr, vmr_info)
    
    if print_logs:
        print(data.procs[process.pid].ads.vmrs)
        print(data.pmrs)
        print(data.devices)

def extract_process_data(data, process):
    """
    Extract data from procfs for a particular process
    
    :param data: the data object
    :type data: ProcFsData
    :param process: the process to query about
    :type process: subprocess.Popen
    """
    
    data.procs[process.pid] = Process(process.args[2:]) # Get the process name from the args, removing "./"
    extract_memory_data(data, process)
    
def terminate_process(process):
    process.terminate()
    process.wait()

import traceback

# Configurations
run_configs = [
    # 0: Basic hello
    ["hello", "hello"],
    # 1: Hello with malloc
    ["hello_malloc", "hello_malloc"]
]
if __name__ == "__main__":
    data = ProcFsData()
    
    to_run = run_configs[1]
    
    procs = [run_process(name) for name in to_run]
    
    try:
        for proc in procs:
            extract_process_data(data, proc)
    except Exception as e:
        print("Error printing stats for hello")
        print(repr(e))
        traceback.print_exc()
    
    for proc in procs:
            terminate_process(proc)
    
    data.to_generic_model(MappingType.CONTIGUOUS, MappingType.CO_CONTIGUOUS).to_csv()