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
                        if dir_dict[name] not in ['0', 'max']:
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
]

# Example usage
all_files_dirs = get_all_files_and_dirs("/sys/fs/cgroup")
# pp.pprint(all_files_dirs)

memtotal = pfs_obj.get_meminfo()['MemTotal']
pp.pprint(memtotal)

def print_dict(d, indent=0):
    for key, value in d.items():
        print(' ' * indent + str(key))
        if isinstance(value, dict):
            print_dict(value, indent + 4)
        else:
            print(' ' * (indent + 4) + str(value))

print_dict(all_files_dirs)