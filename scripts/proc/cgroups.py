import re
from collections import defaultdict
import subprocess

def parse_cgroup_output(output):
    tree = {}
    stack = []

    for line in output.splitlines():
        indent_level = len(line) - len(line.lstrip(' '))
        line = line.strip()
        
        if not line:
            continue
        
        while stack and stack[-1][1] >= indent_level:
            stack.pop()
        
        node = {'name': line, 'children': []}
        
        if stack:
            parent = stack[-1][0]
            parent['children'].append(node)
        else:
            tree = node
        
        stack.append((node, indent_level))
    
    return tree

def get_cgroup_output():
    result = subprocess.run(['sudo', 'systemd-cgls', '--no-pager', '-l'], stdout=subprocess.PIPE, text=True)
    return result.stdout

output = get_cgroup_output()

parsed_tree = parse_cgroup_output(output)

def print_tree(node, indent=0):
    print(' ' * indent + node['name'])
    for child in node['children']:
        print_tree(child, indent + 2)

print_tree(parsed_tree)