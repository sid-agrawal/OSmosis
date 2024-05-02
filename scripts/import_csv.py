# Import a CSV file to Neo4j
# Usage: pass the command line argument for the gdrive url index to upload
# eg: python import_csv.py 3

from neo4j import GraphDatabase
import argparse
import configparser

parser = argparse.ArgumentParser("import_csv")
parser.add_argument("file", help="ID of csv to upload", type=int)
args = parser.parse_args()

config = configparser.ConfigParser()   
config.read("config.txt")

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

# Public CSV file for upload
gdriveUrls = [
"", #0
"https://drive.google.com/uc?export=download&id=18x8W0HIMJhkRw3YRZzGMLD1gYYPG9Rpe", # 1
"https://drive.google.com/uc?export=download&id=12n97Zlo4UNkt7T9tx9ePlkmn6pw72NLS", # 2
"https://drive.google.com/uc?export=download&id=1K-qNGXI1uafKqMPt4bDNTBhH3DEZ7DYy", # 3
"https://drive.google.com/uc?export=download&id=1pY6ftNAMiShIq2CgurVbmxPgredawu-g", # 4
"https://drive.google.com/uc?export=download&id=1X3648_Tq0VAw-UVVnwOqMRsZ7el0aVMV", # 5
"https://drive.google.com/uc?export=download&id=17Dbzko_liuN-YPkxjuItWjHk72gPDrJn", # 6
]

def upload_csv(file_url):
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.verify_connectivity()

        # Delete nodes
        query = """
                MATCH (n) 
                DETACH DELETE n;"""
        
        driver.execute_query(query)
        
        # Load nodes
        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.NODE_TYPE IS NOT NULL
                CALL apoc.merge.node([row.NODE_TYPE], {ID: row.NODE_ID, DATA: row.DATA}, {}, {})
                YIELD node
                RETURN null;
                """ % file_url
        
        driver.execute_query(query)
        
        # Load edges
        query = """
                LOAD CSV WITH HEADERS FROM '%s' AS row
                WITH row
                WHERE row.EDGE_TYPE IS NOT NULL
                MATCH (n1 {ID: row.EDGE_FROM})
                MATCH (n2 {ID: row.EDGE_TO})
                CALL apoc.merge.relationship(n1, row.EDGE_TYPE, {TYPE: row.DATA}, {}, n2, {})
                YIELD rel
                RETURN null;
                """ % file_url
        
        driver.execute_query(query)

if __name__ == "__main__":
    file_url = gdriveUrls[args.file]
    upload_csv(file_url)