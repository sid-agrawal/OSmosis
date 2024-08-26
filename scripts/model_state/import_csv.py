# Import a CSV file to Neo4j
# Usage: pass the command line argument for the public url index to upload
# eg: python import_csv.py 3

from neo4j import GraphDatabase
import argparse
import configparser

parser = argparse.ArgumentParser("import_csv")
parser.add_argument("-f", "--file", help="a LOCAL CSV file to upload")
parser.add_argument("-i", "--uidx", help="index of a URL in public_urls to upload", type=int)
parser.add_argument("-c", "--color", help="modifies node types for colored output in neo4j (does not work for metrics)", 
                    action='store_true', default=False)
args = parser.parse_args()

config = configparser.ConfigParser()   
config.read("config.txt")

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

# Public CSV file for upload
public_urls = [
"https://drive.google.com/uc?id=1jfZn5dlESzoPav2b2Gxm7BYHNTgJ_Fpm&export=download", #0 proc basic, lindt
"https://drive.google.com/uc?id=1SN8vHF8hDlkH-4QVLxFMUTcnnSW91qLq&export=download", #1 proc malloc, lindt
"https://drive.google.com/uc?id=1-TfOq-eGQQeFnA1hNVSeze-SD7dBG6kh&export=download", #2 proc mmap, lindt
"",
"",
"https://drive.google.com/uc?id=1h-F2jcFYY2680G_jMvOLyUw_MhsqdYtF&export=download", #5 proc mmap, ubuntu WSL
]

def upload_csv(file_url):
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.verify_connectivity()

        # Delete nodes
        print("Deleting old graph...")

        query = """
                MATCH (n) 
                DETACH DELETE n;"""
        
        driver.execute_query(query)
        
        # Load nodes
        print("Importing new nodes...")

        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.NODE_TYPE IS NOT NULL
                CALL apoc.merge.node([%s], {NODE_TYPE: row.NODE_TYPE, ID: row.NODE_ID, DATA: row.DATA, EXTRA: coalesce(row.EXTRA, "0")}, {}, {})
                YIELD node
                RETURN null;
                """ % (file_url, 'row.NODE_TYPE + "_" + COALESCE(row.DATA, "")' if args.color else 'row.NODE_TYPE')
        
        driver.execute_query(query)
        
        # Load edges
        print("Importing new edges...")

        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.EDGE_TYPE IS NOT NULL
                MATCH (n1 {ID: row.EDGE_FROM})
                MATCH (n2 {ID: row.EDGE_TO})
                CALL apoc.merge.relationship(n1, row.EDGE_TYPE, {DATA: row.DATA}, {}, n2, {})
                YIELD rel
                RETURN null;
                """ % file_url
        
        driver.execute_query(query)

        print("Complete")

if __name__ == "__main__":
    if args.file is not None and len(args.file) > 0:
        file_url = "file:///" + args.file
    elif args.uidx is not None:
        file_url = public_urls[args.uidx]
    else:
        print(
            "Please provide either a local CSV file or an index for a remote CSV URL in the public_urls array"
        )
        parser.parse_args(['-h'])
        raise SystemExit()
    upload_csv(file_url)
