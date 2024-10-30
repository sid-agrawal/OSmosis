#!/bin/python

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

# Import a CSV file to Neo4j
# Usage: pass the command line argument for the public url index to upload
# eg: python import_csv.py --file local-file --copy --append

config = configparser.ConfigParser()   
config.read("config.txt")

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

def upload_csv_import(db_name: str, filename:str):

    dirname = os.path.dirname(filename)

    pd_file = os.path.join(dirname, "pd.csv")
    res_file = os.path.join(dirname, "res.csv")
    rs_file = os.path.join(dirname, "rs.csv")
    edge_file = os.path.join(dirname, "edge.csv")

    # Create new formatted CSV Files.
    ####./neo4j_shard_csv.py --input outputs/qemu-86/host.csv --pd pd.csv --res res.csv --rs rs.csv --edge edge.csv && cp *.csv ~/neo4j/import
    split(filename, pd_file, res_file, rs_file, edge_file)

    # Copy it to the neo4j import dir.
    for f in [pd_file, res_file, rs_file, edge_file]:
        basename = os.path.basename(f)
        copy_file(f, os.path.expanduser(f"~/neo4j/import/{basename}"))

    # docker exec  neo4j-osm sh -c 'cd /import ;neo4j-admin database import full osm2 --overwrite-destination --nodes=pd.csv --nodes=res.csv --nodes=rs.csv --relationships=edge.csv --verbose'
    exec_cmd = f"cd /import ;neo4j-admin database import full {db_name} --overwrite-destination --nodes=pd.csv --nodes=res.csv --nodes=rs.csv --relationships=edge.csv --verbose"
    command = [
        'docker',
        'exec',
        'neo4j-osm',
        'sh',
        '-c',
        exec_cmd
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print("Command output:", result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error occurred: {e.stderr}")

    # Delete all neo4j-db except system
    neo4j_data_dir = os.path.expanduser("~/neo4j/data/databases")
    for item in os.listdir(neo4j_data_dir):
        item_path = os.path.join(neo4j_data_dir, item)
        if os.path.isdir(item_path):
            if item != "system":
                # shutil.rmtree(item_path)
                print(f"Deleted directory: {item_path}")

    # Change the default db name
    #  docker exec neo4j-osm sh -c 'echo "dbms.default_database=osm3" > /var/lib/neo4j/conf/neo4j.conf'
    exec_cmd = f"echo dbms.default_database={db_name} > /var/lib/neo4j/conf/neo4j.conf"
    command = ['docker', 'exec', 'neo4j-osm', 'sh', '-c', exec_cmd]

    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print("Updated config file in the config")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error occurred: {e.stderr}")

    # Restart the container
    command = [ "docker", "restart", "neo4j-osm"]
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print("Restarted the container")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error occurred: {e.stderr}")

# Look at the old import and new import and ensure that the fields end up in the tight place
def upload_csv_query(db_name: str, filename:str, append_data: bool):

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
        parser.parse_args(['-h'])
        raise SystemExit()

    driver = GraphDatabase.driver(URI, auth=AUTH)
    driver.verify_connectivity()

    with driver.session(database=db_name) as session:
        if not append_data:
                # Delete nodes
                query = """
                        MATCH (n)-[r]-() DELETE r
                        """
                
                summary = session.run(query)
                print(f"Deleted {summary.consume().counters.relationships_deleted} edges")
        
                query = """
                        MATCH (n) DELETE n;
                        """
        
                summary = session.run(query)
                print(f"Deleted {summary.consume().counters.nodes_deleted} nodes")
        
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
        # import pdb; pdb.set_trace()
        
        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.NODE_TYPE = "RESOURCE" OR row.NODE_TYPE = "RESOURCE_SPACE"
                CALL apoc.create.node([%s], {NODE_TYPE: row.NODE_TYPE, ID: row.NODE_ID, 
                   DATA: row.DATA, EXTRA: coalesce(row.EXTRA, "0")})
                YIELD node
                RETURN count(node) as num_rows_added;
                """ % (file_url, 'row.NODE_TYPE + "_" + COALESCE(row.DATA, "")' if args.color else 'row.NODE_TYPE')
        
        result = session.run(query)
        print(f"Added {result.single().value()} of either Resource or Resource Space nodes")
        
        # Load edges
        for edge_type in [gm.EdgeType.REQUEST, gm.EdgeType.MAP, gm.EdgeType.SUBSET, gm.EdgeType.HOLD]:
            query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.EDGE_TYPE = '%s'
                MATCH (n1 {ID: row.EDGE_FROM})
                MATCH (n2 {ID: row.EDGE_TO})
                CALL apoc.create.relationship(n1, row.EDGE_TYPE, {DATA: row.DATA}, n2)
                YIELD rel
                RETURN count(rel) as num_rows_added;
                """ % (file_url, edge_type.name)
        
            start_time = time.time()
            result = session.run(query)
            print(f"Added {result.single().value()} {edge_type.name} Edges. Duration : {time.time()- start_time} seconds")
            # print(f"Added {summary[0][0]['num_rows_added']} {edge_type.name} Edges")

        print("Complete")

def copy_file(src: str, dst: str):
    """
    Copy a file from src to dst.

    :param src: Source file path
    :param dst: Destination file path
    """
    try:
        shutil.copy(src, dst)
        print(f"File copied from {src} to {dst}")
    except FileNotFoundError:
        print(f"Source file {src} not found.")
    except PermissionError:
        print(f"Permission denied while copying to {dst}.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("import_csv")
    parser.add_argument(
        "-f", "--file", required=True, help="filename with the data"
    )
    parser.add_argument(
        "-d",
        "--db",
        help="DB to upload the data too",
        default="neo4j",
    )
    parser.add_argument(
        "-a",
        "--append",
        help="do not delete the existing data",
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
    args = parser.parse_args()

    if args.append:
        copy_file(args.file, os.path.expanduser(f"~/neo4j/import/{args.file}"))
        upload_csv_query(args.db, args.filename, args.append)
    else:
        upload_csv_import(args.db, args.file)
