
from neo4j import GraphDatabase
import argparse
import configparser
import os
import sys
import shutil
import time
import generic_model as gm
import pprint as pp
import subprocess
from neo4j_shard_csv import split
from utils import docker_cmd

config = configparser.ConfigParser()   
config.read("config.txt")

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

def upload_csv_import(db_name: str, filenames:list[str]):

    pd_files = {}
    res_files = {}
    rs_files = {}
    edge_files = {}

    for f in filenames:
        basename = os.path.basename(f)

        dirname = f + "_dir"
        os.makedirs(dirname, exist_ok=True)

        pd_files[f] = os.path.join(dirname, f"{basename}"+"_pd.csv")
        res_files[f] = os.path.join(dirname, f"{basename}"+"_res.csv")
        rs_files[f] = os.path.join(dirname, f"{basename}"+"_rs.csv")
        edge_files[f] = os.path.join(dirname, f"{basename}"+"_edge.csv")

    # Create new formatted CSV Files.
        print (f"Splitting {f} in {pd_files[f]}, {res_files[f]}, {rs_files[f]}, {edge_files[f]}")
        split(f, pd_files[f], res_files[f], rs_files[f], edge_files[f])


        # Copy it to the neo4j import dir.
        for new_f in [pd_files[f], res_files[f], rs_files[f], edge_files[f]]:
            basename = os.path.basename(new_f)
            copy_file(new_f, os.path.expanduser(f"~/neo4j/import/{basename}"))


    
    # Stop the neo4j database (not the server)
    exec_cmd = 'cypher-shell -u neo4j -p password -d system "stop database neo4j"'
    docker_cmd("exec", "neo4j-osm", exec_cmd, debug=True)

    # Import Data
    exec_cmd = f"cd /import ;neo4j-admin database import full --overwrite-destination {db_name} --verbose" 
    for key, value in pd_files.items():
        exec_cmd += f" --nodes={os.path.basename(value)} "
    for key, value in res_files.items():
        exec_cmd += f" --nodes={os.path.basename(value)} "
    for key, value in rs_files.items():
        exec_cmd += f" --nodes={os.path.basename(value)} "
    for key, value in edge_files.items():
        exec_cmd += f" --relationships={os.path.basename(value)} "

    docker_cmd("exec", "neo4j-osm", exec_cmd, debug=False)
    
    # Start the neo4j database (not the server)
    exec_cmd = 'cypher-shell -u neo4j -p password -d system "start database neo4j"'
    docker_cmd("exec", "neo4j-osm", exec_cmd, debug=False)


    # # Delete all neo4j-db except system
    # neo4j_data_dir = os.path.expanduser("~/neo4j/data/databases")
    # for item in os.listdir(neo4j_data_dir):
    #     item_path = os.path.join(neo4j_data_dir, item)
    #     if os.path.isdir(item_path):
    #         if item not in  ["system", db_name]:
    #             shutil.rmtree(item_path)
    #             print(f"Deleted directory: {item_path}")

    # # # Change the default db name
    # print(f"Changing the Default DB Name to {db_name}")
    # exec_cmd = f"echo dbms.default_database={db_name} > /var/lib/neo4j/conf/neo4j.conf"
    # docker_cmd("exec", "neo4j-osm", exec_cmd)

    docker_cmd("restart", "neo4j-osm")

    driver = GraphDatabase.driver(URI, auth=AUTH)
    timeout = 20
    print(f"Waiting {timeout} seconds Check if the DB is back up")
    # Try to verify connectivity in a loop for 10 seconds until it succeeds
    start_time = time.time()
    while True:
        try:
            driver.verify_connectivity()
            print("Successfully connected to the database.")
            driver.close()
            break
        except Exception as e:
            if time.time() - start_time > timeout:
                print(f"Failed to connect to the database within {timeout} seconds.")
                raise e
            # print("\tRetrying connection...")
            time.sleep(5)
    

def wipe_all_data(db_name: str):
    driver = GraphDatabase.driver(URI, auth=AUTH)
    driver.verify_connectivity()

    print("Starting wipe and this can take a while if you have 100Ks of edges")
    with driver.session(database=db_name) as session:
        # Delete nodes
        query = """
               MATCH (n)-[r]-() DELETE r
               """
        start_time = time.time()
        summary = session.run(query)
        print(f"Deleted {summary.consume().counters.relationships_deleted} edges in {time.time()-start_time:.2f} seconds")
        
        # Delete Edges
        query = """
               MATCH (n) DELETE n;
               """
        
        start_time = time.time()
        summary = session.run(query)
        print(f"Deleted {summary.consume().counters.nodes_deleted} nodes in {time.time()-start_time:.2f} seconds")
        
# Look at the old import and new import and ensure that the fields end up in the tight place
def upload_csv_query(db_name: str, filename:str, color:bool):

    print(f"Uploading: {filename}")

    copy_file(filename, os.path.expanduser(f"~/neo4j/import/{os.path.basename(filename)}"))

    if filename is not None and len(filename) > 0  and os.path.isfile(filename) :
        input_file = os.path.basename(filename)
        file_url = "file:///" + input_file
        print(
                "Uploading file", input_file
                )
    else:
        print(
                "Please provide either a local CSV file"
                )
        # parser.parse_args(['-h'])
        raise SystemExit()

    driver = GraphDatabase.driver(URI, auth=AUTH)
    driver.verify_connectivity()
    with driver.session(database=db_name) as session:
        # Load nodes
        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.NODE_TYPE = "PD"
                CALL apoc.create.node([row.NODE_TYPE], {NODE_TYPE: row.NODE_TYPE, 
                   ID: row.NODE_ID, DATA: row.DATA, EXTRA: coalesce(row.EXTRA, "0")})
                YIELD node
                RETURN count(node) as num_rows_added;
                """ % (file_url)
        
        result = session.run(query)
        print(f"Added {result.single().value()} PDs")
        
        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.NODE_TYPE = "RESOURCE" OR row.NODE_TYPE = "RESOURCE_SPACE"
                CALL apoc.create.node([%s], {NODE_TYPE: row.NODE_TYPE, ID: row.NODE_ID, 
                   DATA: row.DATA, EXTRA: coalesce(row.EXTRA, "0")})
                YIELD node
                RETURN count(node) as num_rows_added;
                """ % (file_url, 'row.NODE_TYPE + "_" + COALESCE(row.DATA, "")' if color else 'row.NODE_TYPE')
        
        result = session.run(query)
        print(f"Added {result.single().value()} of either Resource or Resource Space nodes")
        
        # Load edges
        query = """
            LOAD CSV WITH HEADERS FROM '%s' AS row
            WITH row
            MATCH (n1 {ID: row.EDGE_FROM})
            MATCH (n2 {ID: row.EDGE_TO})
            CALL apoc.create.relationship(n1, row.EDGE_TYPE, {DATA: row.DATA}, n2)
            YIELD rel
            RETURN count(rel) as num_rows_added;
            """ % (file_url)
        
        start_time = time.time()
        result = session.run(query)
        print(f"Added {result.single().value()} Edges. Duration : {time.time()- start_time:.2f} seconds")
            # print(f"Added {summary[0][0]['num_rows_added']} {edge_type.name} Edges")

        print("Complete")

def copy_file(src: str, dst: str, debug:bool=False):
    """
    Copy a file from src to dst.

    :param src: Source file path
    :param dst: Destination file path
    """
    try:
        shutil.copy(src, dst)
        if debug:
            print(f"File copied from {src} to {dst}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Source file {src} not found.")
    except PermissionError:
        raise PermissionError(f"Permission denied while copying to {dst}.")
    except Exception as e:
        raise Exception(f"An error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("import_csv")
    parser.add_argument(
        "-f", "--files", required=True, help="space separates filenames with the data",
        nargs = '+'
    )
    parser.add_argument(
        "-w",
        "--wipe",
        help="delete the existing data",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-c",
        "--color",
        help="modifies node types for colored output in neo4j (does not work for metrics)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-q",
        "--query",
        help="Run queries instead of using neo4j-admin",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()
    db_name = "neo4j"
    
    # Conditrionally Wipe
    if args.wipe:
        wipe_all_data(db_name)

    if args.query:

        # Always append
        for f in args.files:
            upload_csv_query(db_name, f, args.color)
    else:
        upload_csv_import(db_name, args.files)
