""" 
Calculate FR metric as described in the SOSP paper
"""

import numpy as np
import pandas as pd
import networkx as nx
import os
import re
import matplotlib.pyplot as plt
from collections import deque

ROOT_TASK_PD = "PD_1"

def read_csv_to_graph(filename):
    try:
        # Read CSV file into a pandas DataFrame
        df = pd.read_csv(filename, on_bad_lines='skip')
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    # Create a new NetworkX graph
    G = nx.MultiDiGraph()

    # Add nodes and edges
    for index, row in df.iterrows():
        if pd.notna(row['RES_TYPE']) and pd.notna(row['RES_ID']):
            G.add_node(row['RES_ID'], type=row['RES_TYPE'])
        elif pd.notna(row['PD_ID']) and pd.notna(row['PD_NAME']):
            G.add_node(row['PD_ID'], name=row['PD_NAME'])
        elif pd.notna(row['RESOURCE_FROM']) and pd.notna(row['RESOURCE_TO']) and not G.has_edge(row['RESOURCE_FROM'], row['RESOURCE_TO']):
            G.add_edge(row['RESOURCE_FROM'], row['RESOURCE_TO'], type=row['REL_TYPE'])
        elif pd.notna(row['PD_FROM']) and pd.notna(row['PD_TO']):
            # Avoid adding duplicate RDE edge
            if G.has_edge(row['PD_FROM'], row['PD_TO']):
                edge_data = G.get_edge_data(row['PD_FROM'], row['PD_TO'])

                edge_exists = False
                for _, data in edge_data.items():
                    if 'restype' in data and data['restype'] == row['RES_TYPE']:
                        # This RDE edge already exists
                        edge_exists = True
                        break

                if edge_exists: continue

            G.add_edge(row['PD_FROM'], row['PD_TO'], type='REQUEST', restype=row['RES_TYPE'])
        elif pd.notna(row['PD_FROM']) and pd.notna(row['RESOURCE_TO']) and not G.has_edge(row['PD_FROM'], row['RESOURCE_TO']):
            G.add_edge(row['PD_FROM'], row['RESOURCE_TO'], type='HOLD')

    return G

def draw_graph(g):
    pos = nx.spring_layout(g)  # positions for all nodes
    node_labels = {node: node for node in g.nodes()}
    nx.draw(g, pos, with_labels=True, labels=node_labels)
    edge_labels = {(u, v): data['type'] for u, v, data in g.edges(data=True)}
    #nx.draw_networkx_edge_labels(g, pos, edge_labels=edge_labels)
    plt.show()

space_defns = {}

# Also flatten the pd->res->subset<-manager edges to current_pd->manager
def flatten_graph(G):
    print('------FLATTEN GRAPH------')


    # Obtain a set of all resource spaces
    spaces = set()
    for _, dst, data in G.out_edges(data=True):
        if data.get('type') == 'SUBSET':
            spaces.add((dst))

    print(f'Spaces {spaces}')

    # For each space: Find managing PDs, and dependent PDs
    # Flatten relationship with an edge
    for space in spaces:
        space_type = G.nodes[space]['type']

        owners = set()
        resources = set()
        dependents = set()
        map_types = set()

        # Find owners of space and resources in space
        for src, _, data in G.in_edges(space, data=True):
            if data.get('type') == 'HOLD':
                owners.add(src)
            elif data.get('type') == 'SUBSET':
                resources.add(src)

        # Find types mapped to by space
        for _, dst, data in G.out_edges(space, data=True):
            if data.get('type') == 'MAP':
                map_types.add(G.nodes[dst]['type'])

        # Find dependents of space
        for res in resources:
            for src, _, data in G.in_edges(res, data=True):
                if data.get('type') == 'HOLD' and src not in owners:
                    dependents.add(src)
        
        # Add implicit RDE from dependents to owners
        for owner in owners:
            for dependent in dependents:
                if not G.has_edge(dependent, owner):
                    G.add_edge(dependent, owner, type='REQUEST', restype=space_type)
                    print(f'Add RDE: ({dependent})--[REQUEST {space_type}]-->({owner})')
                else:
                    print(f'Existing RDE: ({dependent})--[REQUEST {space_type}]-->({owner})')

        # Add space defn
        space_defns[space_type] = {'space': space, 'map_types': map_types}
        # print(f'Space {space} owners {owners}, dependents {dependents}, map types {map_types}')

    return G

def fr_bfs(G, pd_0):
    print()
    print(f'------BFS {pd_0}------')

    acc_key = f'accumulator_{pd_0}'

    # Find the start types as all resources the PD holds
    start_types_set = set()
    for _, dst, data in G.out_edges(pd_0, data=True):
        if data.get('type') == 'HOLD':
            start_types_set.add(G.nodes[dst]['type'])

    print(f'Start types {start_types_set}')

    # Flatten graph
    Q = deque([(pd_0, 0, start_types_set)])

    while Q:
        current_pd, fr, types_set = Q.popleft()

        print()
        print(f'{current_pd}')
        print(f'- Types: [{types_set}]')

        # Set accum value
        if acc_key not in G.nodes[current_pd]:
            G.nodes[current_pd][acc_key] = fr
            print(f'- Set {acc_key}={fr}')
        else:
            print(f'- {acc_key} already set')

        # Follow RDEs within the types set
        for _, dst, data in G.out_edges(current_pd, data=True):
            if data.get('type') == 'REQUEST' and data.get('restype') in types_set:

                # Update the types set with types that this space maps to
                rde_map_types = {}
                if data.get('restype') in space_defns:
                    rde_map_types = space_defns[data.get('restype')]['map_types']
                else:
                    print(f'Warning: "{data.get("restype")}" not in space types\n')
                new_types_set = types_set.union(rde_map_types)

                Q.append((dst, fr + 1, new_types_set))

    return G

def calc_fr(G, pd_0, pd_1):
    print()
    print(f'------CALCULATE FR------')

    acc_key_0 = f'accumulator_{pd_0}'
    acc_key_1 = f'accumulator_{pd_1}'
    min_fr = float('inf')

    for node, data in G.nodes(data=True):
        if acc_key_0 in data and acc_key_1 in data:
            print(f'Node {node} in union, {acc_key_0}={data[acc_key_0]}, {acc_key_1}={data[acc_key_1]}')
            min_fr = min(min_fr, data[acc_key_0], data[acc_key_1])
    
    return min_fr

# Files to load, and PDs of interest per file
files = [
    # {'file': '2fs.csv', 'pd1': 'APP_1', 'pd2': 'APP_2'},
    {'file': 'kvstore_2_diff_pd.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_5.0.0'},
    # {'file': 'kvstore_3_diff_ns.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_4.0.0'},
    # {'file': 'kvstore_4_diff_fs.csv', 'pd1': 'PD_5.0.0', 'pd2': 'PD_6.0.0'},
    # {'file': 'kvstore_5_diff_ads.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_4.0.1'},
    # {'file': 'kvstore_6_diff_threads.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_4.1.0'},
]

if __name__ == "__main__":
    print("Version 1")

    # Iterate through all files
    for file in files:
        # Load CSV to dataframe
        g = read_csv_to_graph(file['file'])

        #draw_graph(g)

        # Flatten graph
        g = flatten_graph(g)

        # BFS from both nodes
        g = fr_bfs(g, file['pd1'])
        g = fr_bfs(g, file['pd2'])

        # Calculate result
        fr = calc_fr(g, file['pd1'], file['pd2'])

        # Output result
        print(f"FR '{file['file']}' ({file['pd1']},{file['pd2']}): {fr}")

