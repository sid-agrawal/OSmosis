# Import a CSV file to Neo4j
# Usage: pass the command line argument for the public url index to upload
# eg: python import_csv.py 3

from neo4j import GraphDatabase
import argparse
import configparser
import os

parser = argparse.ArgumentParser("import_csv")
parser.add_argument("-f", "--file", help="filename inside ~/neo4j/import")
parser.add_argument("-c", "--color", help="modifies node types for colored output in neo4j (does not work for metrics)", 
                    action='store_true', default=False)
args = parser.parse_args()

config = configparser.ConfigParser()   
config.read("config.txt")

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

def upload_csv(file_url):
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.verify_connectivity()

        # Delete nodes
        query = """
                MATCH (n)-[r]-() DELETE r
                """
        
        summary = driver.execute_query(query).summary
        print(f"Deleted {summary.counters.relationships_deleted} edges")
        
        query = """
                MATCH (n) DELETE n;
                """
        
        summary = driver.execute_query(query).summary
        print(f"Deleted {summary.counters.nodes_deleted} nodes")
        
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
        
        summary = driver.execute_query(query)
        print(f"Added {summary[0][0]['num_rows_added']} PDs")
        
        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.NODE_TYPE = "RESOURCE" OR row.NODE_TYPE = "RESOURCE_SPACE"
                CALL apoc.create.node([%s], {NODE_TYPE: row.NODE_TYPE, ID: row.NODE_ID, 
                   DATA: row.DATA, EXTRA: coalesce(row.EXTRA, "0")})
                YIELD node
                RETURN count(node) as num_rows_added;
                """ % (file_url, 'row.NODE_TYPE + "_" + COALESCE(row.DATA, "")' if args.color else 'row.NODE_TYPE')
        
        summary = driver.execute_query(query)
        print(f"Added {summary[0][0]['num_rows_added']} of either Resource or Resource Space nodes")
        
        # Load edges
        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.EDGE_TYPE IS NOT NULL
                MATCH (n1 {ID: row.EDGE_FROM})
                MATCH (n2 {ID: row.EDGE_TO})
                CALL apoc.create.relationship(n1, row.EDGE_TYPE, {DATA: row.DATA}, n2)
                YIELD rel
                RETURN count(rel) as num_rows_added;
                """ % file_url
        
        summary = driver.execute_query(query)
        print(f"Added {summary[0][0]['num_rows_added']} Edges")

        print("Complete")

if __name__ == "__main__":
    #if args.file is not None and len(args.file) > 0  and os.path.isfile(args.file) :
    if args.file is not None and len(args.file) > 0 :
        file_url = "file:///" + args.file
        print(
                "Uploading file", args.file
                )
    else:
        print(
                "Please provide either a local CSV file"
                )
        parser.parse_args(['-h'])
        raise SystemExit()
    upload_csv(file_url)
