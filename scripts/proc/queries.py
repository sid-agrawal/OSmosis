from neo4j import GraphDatabase, Session
import argparse
import configparser
import generic_model as gm
import pprint as pp
from typing import List

config = configparser.ConfigParser()   
config.read("config.txt")

URI = config.get("neo4j", "url")
AUTH = (config.get("neo4j", "user"), config.get("neo4j", "pass"))

# Look at the old import and new import and ensure that the fields end up in the tight place
def all_pds(s: Session, shouldPrint:bool=False) -> List[str]:

    query = """
    MATCH (n:PD) RETURN n
    """
    result = s.run(query)
    nodes = [record["n"] for record in result]
    nodes_dict = {node.element_id: dict(node) for node in nodes}

    if shouldPrint:
        pd_ids = [pd["ID"] for pd in nodes_dict.values()]
        pp.pprint(pd_ids)

    return pd_ids


def shared_resources (s:Session, pd1: str, pd2:str, res_type:str, shouldPrint:bool =False):

    query = """
    MATCH 
        paths= (
            (:PD {ID: $pd1}) -[a:HOLD|MAP*1..4]->
                    (SR:RESOURCE {DATA: $rtype}) 
            <-[b:HOLD|MAP*1..4]-  (:PD {ID: $pd2}))
        RETURN SR
    """
    result = s.run(query, pd1=pd1, pd2=pd2, rtype=res_type)
    nodes = [record["SR"] for record in result]
    nodes_dict = {node.id: dict(node) for node in nodes}

    if shouldPrint:
        for node in nodes_dict:
            pp.pprint(node)

    return nodes_dict

# WHERE (
# (
#   TYPE(a[0]) <> "HOLD" or 
#   a[0].DATA contains $pd1_perms
# )
# and 
# (
#   TYPE(b[0]) <> "HOLD" or 
#   b[0].DATA contains $pd2_perms)
# )


def establish_session(db_name: str):
    driver = GraphDatabase.driver(URI, auth=AUTH)
    driver.verify_connectivity()
    return driver.session(database=db_name)

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
    s = establish_session(db_name="neo4j")

    pd_ids = all_pds(s, shouldPrint=True)

    for i, pd1 in enumerate(pd_ids):
        for pd2 in pd_ids[i+1:]:
            resources = shared_resources(s, pd1, pd2, "FILE", True)
            pp.pprint(resources)

