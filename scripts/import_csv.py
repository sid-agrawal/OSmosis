# Import a CSV file to Neo4j
# Usage: pass the command line argument for the gdrive url index to upload
# eg: python import_csv.py 3

from neo4j import GraphDatabase
import argparse
import configparser
import os

parser = argparse.ArgumentParser("import_csv")
parser.add_argument("file", help="ID of csv to upload", type=int)
args = parser.parse_args()

config = configparser.ConfigParser()   
config.read('config.txt')

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

# Public CSV file for upload
gdriveUrls = [
"https://docs.google.com/spreadsheets/d/e/2PACX-1vTxfSLozI_E8YOpvK3qOy0Ynb0iOw8-iKlxTPg8kZvKmWsPHFrzD4LTqIE6yjyCF1KnkzZ3EQ-j2Cd5/pub?gid=1413058884&single=true&output=csv"
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
                CALL apoc.merge.node([row.NODE_TYPE], {ID: row.NODE_ID, DATA: row.DATA, EXTRA: coalesce(row.EXTRA, "0")}, {}, {})
                YIELD node
                RETURN null;
                """ % file_url
        
        driver.execute_query(query)
        
        # Load edges
        print("Importing new edges...")

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

        print("Complete")

if __name__ == "__main__":
    file_url = gdriveUrls[args.file]
    upload_csv(file_url)