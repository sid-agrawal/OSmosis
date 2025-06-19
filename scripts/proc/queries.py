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
def all_pds(s: Session, shouldPrint: bool = False) -> List[str]:

    query = """
    MATCH (n:PD) RETURN n
    """
    result = s.run(query)
    nodes = [record["n"] for record in result]
    nodes_dict = {node.element_id: dict(node) for node in nodes}
    pd_ids = [pd["ID"] for pd in nodes_dict.values()]

    if shouldPrint:
        for pd in nodes_dict.values():
            print(f"{pd["ID"]} : {pd["DATA"]}")

    return pd_ids


def shared_resources(
    s: Session, pd1: str, pd2: str, res_type: str, shouldPrint: bool = False
):
    """
    This is Q1 from the paper
    """

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
    nodes_dict = {node.element_id: dict(node) for node in nodes}

    if shouldPrint:
        print(f"\nThe shared resources between {pd1} and {pd2} of type {res_type} are as follows:")
        for node in nodes_dict.values():
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


def shared_resources_spaces(
    s: Session, pd1: str, pd2: str, res_type: str, shouldPrint: bool = False
):
    """
    This is Q2 from the paper
    """

    # Get all the RS of pd1
    q1= """
    MATCH 
        PATHS= (

            (a:PD {ID: $pd1}) 
                -[b:HOLD]     -> (c:RESOURCE}) 
                -[d:SUBSET]   -> (e:RESOURCE_SPACE) 
                -[f:MAP*0..4] -> (g:RESOURCE_SPACE)
    )
    RETURN PATHS
"""

    # Get all the PDs that hold these RSes






    query = """
    MATCH (startNode:PD {ID: "PD_2" })
        CALL apoc.path.expandConfig(startNode, {
            relationshipFilter: "REQUEST|HOLD", // Replace RELATIONSHIP_TYPE with the type of relationships to traverse
            // nodesFilter: "PD|RESOURCE_SPACE",
            algorithm: "BFS", // Specifies breadth-first search
            maxLevel: 2 // Optional: specify the maximum depth of traversal
        })
        
        YIELD path as paths
        WITH ColLECT(nodes(paths)) as nn
        //return nn
UNWIND nn as uw_nn
    """
    result = s.run(query, pd1=pd1, pd2=pd2, rtype=res_type)
    nodes = [record["SR"] for record in result]
    nodes_dict = {node.element_id: dict(node) for node in nodes}

    if shouldPrint:
        for node in nodes_dict:
            pp.pprint(node)

    return nodes_dict


def common_ancestor(s: Session, pd1: str, pd2: str, shouldPrint: bool = False):
    """
    This is Q3 from the paper
    """

    query = """
    MATCH 
        paths= (
            (:PD {ID: $pd1}) -[a:REQUEST*1..4]->
                    (CAPD:PD) 
            <-[b:REQUEST*1..4]-  (:PD {ID: $pd2}))
        RETURN CAPD
    """
    result = s.run(query, pd1=pd1, pd2=pd2)
    nodes = [record["CAPD"] for record in result]
    nodes_dict = {node.element_id: dict(node) for node in nodes}

    if shouldPrint:
        print(f"\nThe common ancestors between {pd1} and {pd2} are as follows:")
        for node in nodes_dict.values():
            pp.pprint(node)

    return nodes_dict

def find_all_killer_pds(s: Session, pd1: str, shouldPrint: bool = False):
    """
    This is Q5 from the paper
    """

    query = """
    MATCH 
        paths= ((killer_pd:PD) -[:HOLD]-> (:PD {ID: $pd1}))
        RETURN killer_pd
    """
    result = s.run(query, pd1=pd1)
    nodes = [record["killer_pd"] for record in result]
    nodes_dict = {node.element_id: dict(node) for node in nodes}

    if shouldPrint:
        print(f"\nThe PDs that can kill {pd1}:")
        for node in nodes_dict.values():
            pp.pprint(node)

    return nodes_dict

def find_all_killable_pds(s: Session, pd1: str, shouldPrint: bool = False):
    """
    This is Q5 from the paper
    """

    query = """
    MATCH 
        paths= ((kill_able_pd:PD) <-[:HOLD]- (:PD {ID: $pd1}))
        RETURN kill_able_pd
    """
    result = s.run(query, pd1=pd1)
    nodes = [record["kill_able_pd"] for record in result]
    nodes_dict = {node.element_id: dict(node) for node in nodes}

    if shouldPrint:
        print(f"\nThe PDs that {pd1} can kill:")
        for node in nodes_dict.values():
            pp.pprint(node)

    return nodes_dict

def collect_attrs(s: Session, pd1: str, res_type: str, shouldPrint: bool = False):
    """
    This is Q4 from the paper
    """

    query = """
        MATCH (startNode:PD {ID: $pd1})
            CALL apoc.path.expandConfig(startNode, {
            relationshipFilter: "HOLD|MAP", // Replace RELATIONSHIP_TYPE with the type of relationships to traverse
            algorithm: "BFS", // Specifies breadth-first search
            maxLevel: 2 // Optional: specify the maximum depth of traversal
        })
        yield path as paths
        with relationships(paths) as rel_list
        UNWIND rel_list as re
        RETURN DISTINCT apoc.convert.fromJsonMap(re.EXTRA).pd_incharge AS TCB;
    """
    result = s.run(query, pd1=pd1, rtype=res_type)
    nodes = [record["TCB"] for record in result]

    if shouldPrint:
        print(f"\nThe TCB (based on edge attr) for {pd1} are as follows:")
        for node in nodes:
            pp.pprint(node)

    return nodes


# TODO
# We may not even be exporting it.
def PD_handler(s: Session, pd1: str, res_type: str, shouldPrint: bool = False):
    """
    This is Q5 from the paper
    """

    pass


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

    # for i, pd1 in enumerate(pd_ids):
    #     for pd2 in pd_ids[i + 1 :]:
    #         resources = shared_resources(s, pd1, pd2, "MO", True)
    resources = shared_resources(s, "PD_187032", "PD_187070", "MO", True)

    # tcb = collect_attrs(s, "PD_2422", "MO", True)

    # tcb = common_ancestor(s, "PD_2422", "PD_1", True)

    # find_all_killer_pds(s, "PD_749727", True)
    # find_all_killable_pds(s, "PD_749727", True)
