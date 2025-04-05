import re
from collections import defaultdict
import os
from functools import reduce
import pprint as pp
import sys

# PFS Setup
sys.path.append("pfs/lib")
import pypfs # type: ignore

def get_all_files_and_dirs(path):
    def recursive_dict(path):
        dir_dict = {}
        for root, dirs, files in os.walk(path):
            for name in dirs:
                dir_dict[name] = recursive_dict(os.path.join(root, name))
            for name in files:
                if name not in interested_files:
                    continue
                try:
                    with open(os.path.join(root, name), 'r') as file:
                        dir_dict[name] = file.read().rstrip('\n')
                        if dir_dict[name] not in ['0', 'max'] and name != "cgroup.procs":
                            print(f"\033[93mFile {os.path.join(root, name)} has value {dir_dict[name]}\033[0m")
                except OSError as e:
                    if e.errno == 22:
                        print(f"Error reading file {os.path.join(root, name)}: {e}")
                    else:
                        raise
            break  # Prevents os.walk from going into subdirectories
        return dir_dict

    return recursive_dict(path)

pfs_obj = pypfs.procfs()  # Interface to the PFS library

interested_files = [
    "memory.max",
    "memory.min",
    "memory.high",
    "memory.low",
    "cgroup.procs"
]

# Example usage
all_files_dirs = get_all_files_and_dirs("/sys/fs/cgroup")
# pp.pprint(all_files_dirs)

memtotal = pfs_obj.get_meminfo()['MemTotal']
# pp.pprint(memtotal)


def human_readable_size(size:int):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} YB"

def print_dict(d, indent=0):
    is_leaf: bool = True
    for value in d.values():
        if isinstance(value, dict):
            is_leaf = False
            break

    for key, value in d.items():
        if is_leaf:
            print(f"\033[92m{' ' * indent + str(key)}\033[0m", end ="")
        else:
            print(f"\033[91m{' ' * indent + str(key)}\033[0m", end ="")

        if isinstance(value, dict):
            print()
            print_dict(value, indent + 4)
        else:
            if is_leaf:
                print(f"\033[92m{' ' * (indent + 4) + str(value)}\033[0m")
            else:
                print(f"\033[91m{' ' * (indent + 4) + str(value)}\033[0m")


def find_max_depth(d, depth=0):
    if not isinstance(d, dict) or not d:
        return depth
    return max(find_max_depth(v, depth + 1) for v in d.values())

max_depth = find_max_depth(all_files_dirs)
# print(f"Max depth of the dictionary: {max_depth}")

def update_memory_max(d, memtotal:int):
    for key, value in d.items():
        if key == "memory.max":
            if value != "max":
                print(f"\033[93mUpdating memory.max from {human_readable_size(int(value))} to "
                      f"{human_readable_size(memtotal)}\033[0m")
                memtotal = min (int(value), memtotal)
    for key, value in d.items():
        if isinstance(value, dict):
            update_memory_max(value, memtotal)

# update_memory_max(all_files_dirs, memtotal)
# pp.pprint(all_files_dirs)


print_dict(all_files_dirs)
# print(f"MemTotal in human readable format: {human_readable_size(memtotal)}")