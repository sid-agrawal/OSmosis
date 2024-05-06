# Calculate RSI and FR metrics for a pair of PDs
# Usage: pass the configuration ID as an argument
# eg: python metrics.py 2

from neo4j import GraphDatabase
import argparse
import configparser
import pandas as pd
import networkx as nx
from collections import deque
import logging, sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

# Files and PDs of interest for different configurations
# Index is the 'configuration' argument
configurations = [
    {},
    {},
    {'file': 'kvstore_2_diff_pd.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_5.0.0'},
    {'file': 'kvstore_3_diff_ns.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_5.0.0'},
    {'file': 'kvstore_4_diff_fs.csv', 'pd1': 'PD_5.0.0', 'pd2': 'PD_6.0.0'},
    {'file': 'kvstore_5_diff_ads.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_4.0.1'},
    {'file': 'kvstore_6_diff_threads.csv', 'pd1': 'PD_4.0.0', 'pd2': 'PD_4.1.0'},
]

parser = argparse.ArgumentParser("import_csv")
parser.add_argument("config", help="Which configuration index to use", type=int)
args = parser.parse_args()

config = configparser.ConfigParser()   
config.read("config.txt")

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

def calc_rsi(pd1, pd2):
    # Resource types of interest
    types = ["VMR","PMR","VCPU","PCPU","FILE","BLOCK"]

    query = """
        WITH "%s" as pd1, "%s" as pd2

        // Find all accessible resources
        MATCH (:PD {ID: pd1})-[:HOLD|MAP*1..4]->(r1:RESOURCE)
        WITH pd2, COLLECT(DISTINCT r1) as r1
        MATCH (:PD {ID: pd2})-[:HOLD|MAP*1..4]->(r2:RESOURCE)
        WITH r1, COLLECT(DISTINCT r2) as r2

        // Split by type
        WITH r1, r2, ["VMR","PMR","VCPU","PCPU","FILE","BLOCK"] AS types
        WITH [t IN types | [n in r1 WHERE n.DATA = t] ] as r1, [t IN types | [n in r2 WHERE n.DATA = t] ] as r2 
        WITH r1, r2, apoc.coll.zip(r1, r2) as r_zip

        // Intersection
        WITH [entry in r_zip | apoc.coll.intersection(entry[0], entry[1])] as inter,
        [entry in r_zip | apoc.coll.union(entry[0], entry[1])] as union

        // Counts
        WITH [t in union | size(t)] as cU, [t in inter | size(t)] as cI

        with  {cU: cU, cI:cI} as info
        return info
        """ % (pd1, pd2)

    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.verify_connectivity()

        records, _, _ = driver.execute_query(query)

        counts_intersect = records[0]['info']['cI']
        counts_union = records[0]['info']['cU']

        for type,union,intersect in zip(types, counts_union, counts_intersect):
             print(f"RSI {type}: {intersect / union if union > 0 else 0}")

# Read a CSV to a networkx graph
def read_csv_to_graph(filename):
    try:
        # Read CSV file into a pandas DataFrame
        df = pd.read_csv(filename, on_bad_lines='skip')
    except FileNotFoundError:
        logging.error(f"Error: File '{filename}' not found.")
        return None
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None

    # Create a new NetworkX graph
    G = nx.MultiDiGraph()

    # Add nodes and edges
    for _, row in df.iterrows():
        if pd.notna(row['NODE_TYPE']):
            G.add_node(row['NODE_ID'], type=row['NODE_TYPE'], data=row['DATA'])
        elif pd.notna(row['EDGE_TYPE']):
            G.add_edge(row['EDGE_FROM'], row['EDGE_TO'], type=row['EDGE_TYPE'], data=row['DATA'])
        else:
            logging.error("Unexpected row while loading CSV")

    return G

space_defns = {}

# Flatten the pd->res->subset<-manager edges to current_pd->manager
def fr_flatten(G):
    logging.debug('------FLATTEN GRAPH------')


    # Obtain a set of all resource spaces
    spaces = set()
    for _, dst, data in G.out_edges(data=True):
        if data.get('type') == 'SUBSET':
            spaces.add((dst))

    logging.debug(f'Spaces {spaces}')

    # For each space: Find managing PDs, and dependent PDs
    # Flatten relationship with an edge
    for space in spaces:
        space_type = G.nodes[space]['data']

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
                map_types.add(G.nodes[dst]['data'])

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
                    logging.debug(f'Add RDE: ({dependent})--[REQUEST {space_type}]-->({owner})')
                else:
                    logging.debug(f'Existing RDE: ({dependent})--[REQUEST {space_type}]-->({owner})')

        # Add space defn
        space_defns[space_type] = {'space': space, 'map_types': map_types}
        logging.debug(f'Space {space} owners {owners}, dependents {dependents}, map types {map_types}')

    return G

# Traverse edges according to FR algorithm, set accumulator at nodes
def fr_bfs(G, pd_0):
    logging.debug('')
    logging.debug(f'------BFS {pd_0}------')

    acc_key = f'accumulator_{pd_0}'

    # Find the start types as all resources the PD holds
    start_types_set = set()
    for _, dst, data in G.out_edges(pd_0, data=True):
        if data.get('type') == 'HOLD':
            start_types_set.add(G.nodes[dst]['data'])

    logging.debug(f'Start types {start_types_set}')

    # Flatten graph
    Q = deque([(pd_0, 0, start_types_set)])

    while Q:
        current_pd, fr, types_set = Q.popleft()

        logging.debug('')
        logging.debug(f'{current_pd}')
        logging.debug(f'- Types: [{types_set}]')

        # Set accum value
        if acc_key not in G.nodes[current_pd]:
            G.nodes[current_pd][acc_key] = fr
            logging.debug(f'- Set {acc_key}={fr}')
        else:
            logging.debug(f'- {acc_key} already set')

        # Follow RDEs within the types set
        for _, dst, data in G.out_edges(current_pd, data=True):
            if data.get('type') == 'REQUEST' and data.get('data') in types_set:

                # Update the types set with types that this space maps to
                rde_map_types = {}
                if data.get('data') in space_defns:
                    rde_map_types = space_defns[data.get('data')]['map_types']
                else:
                    logging.debug(f'Warning: "{data.get("data")}" not in space types\n')
                new_types_set = types_set.union(rde_map_types)

                Q.append((dst, fr + 1, new_types_set))

    return G

# Calculate FR metric from accumulators (set by fr_bfs)
def fr_acc(G, pd_0, pd_1):
    logging.debug('')
    logging.debug(f'------CALCULATE FR------')

    acc_key_0 = f'accumulator_{pd_0}'
    acc_key_1 = f'accumulator_{pd_1}'
    min_fr = float('inf')

    for node, data in G.nodes(data=True):
        if acc_key_0 in data and acc_key_1 in data:
            logging.debug(f'Node {node} in union, {acc_key_0}={data[acc_key_0]}, {acc_key_1}={data[acc_key_1]}')
            min_fr = min(min_fr, data[acc_key_0], data[acc_key_1])
    
    return min_fr

def calc_fr(filename, pd1, pd2):
    # Load CSV to dataframe
    g = read_csv_to_graph(filename)

    #draw_graph(g)

    # Flatten graph
    g = fr_flatten(g)

    # BFS from both nodes
    g = fr_bfs(g, pd1)
    g = fr_bfs(g, pd2)

    # Calculate result
    fr = fr_acc(g, pd1, pd2)

    # Output result
    print(f"FR: {fr}")

if __name__ == "__main__":
    config = configurations[args.config]
    pd1 = config['pd1']
    pd2 = config['pd2']
    file = config['file']
    
    print(f"Calculating metrics for '{file}' ({pd1},{pd2})")
    calc_rsi(pd1, pd2)
    calc_fr(file, pd1, pd2)