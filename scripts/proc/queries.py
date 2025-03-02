
from neo4j import GraphDatabase
import argparse
import configparser
import os
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

# Look at the old import and new import and ensure that the fields end up in the tight place
def all_pds(db_name: str) -> dict:
    driver = GraphDatabase.driver(URI, auth=AUTH)
    driver.verify_connectivity()

    with driver.session(database=db_name) as session:
        query = """
        MATCH (n:PD) RETURN n
        """
        result = session.run(query)
        nodes = [record["n"] for record in result]
        nodes_dict = {node.id: dict(node) for node in nodes}
    return nodes_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser("import_csv")
    parser.add_argument(
        "-t",
        "--tcb",
        help="Run TCB query",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()
    db_name = "neo4j"
    

    pds = all_pds(db_name)
    pp.pprint(pds)