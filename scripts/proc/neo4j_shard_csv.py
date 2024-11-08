#!/bin/python

import csv
import os
import time
import argparse
import json

#
# neo4j-admin database import full neo4j --nodes=pd.csv --nodes=res.csv --nodes=rs.csv --relationships=edge.csv


def split(input, pd, res, rs, edge):

    input_file = open(input, mode= "r")
    input_csv = csv.reader(input_file) 

    pd_file = open(pd, mode= "w")
    pd_csv = csv.writer(pd_file) 

    res_file = open(res, mode= "w")
    res_csv = csv.writer(res_file) 

    rs_file = open(rs, mode= "w")
    rs_csv = csv.writer(rs_file) 

    edge_file = open(edge, mode= "w")
    edge_csv = csv.writer(edge_file) 

    # Added heads
    print(f"ID:ID,NODE_TYPE,DATA,EXTRA,:LABEL", file=pd_file)
    print(f"ID:ID,NODE_TYPE,DATA,EXTRA,:LABEL", file=res_file)
    print(f"ID:ID,NODE_TYPE,DATA,EXTRA,:LABEL", file=rs_file)
    print(f":START_ID,DATA,EXTRA,:END_ID,:TYPE", file=edge_file)

    for row in input_csv:

        row_type = row[0]
        row_id = row[1]
        row_data = row[2]
        edge_type = row[3]
        edge_from = row[4]
        edge_to = row[5]
        extra_row = row[6]

        if row_type == "NODE_TYPE":  # First Row
            continue

        if extra_row is not None and extra_row != "":
            try:
                extra_dict = json.loads(extra_row)
            except json.JSONDecodeError:
                raise ValueError( f"Coulnd not parse : {extra_row}")
            extra = json.dumps(extra_dict)
        else:
            extra = ""

        if row_type == "PD":
            pd_csv.writerow([row_id, row_type, row_data, extra, row_type])
        elif row_type == "RESOURCE":
            res_csv.writerow([row_id,row_type,  row_data, extra, row_type])
        elif row_type == "RESOURCE_SPACE":
            rs_csv.writerow([row_id,row_type,  row_data, extra, row_type])
        else:
            assert edge_type in ["MAP", "HOLD", "SUBSET", "REQUEST"]
            edge_csv.writerow([edge_from, row_data, extra, edge_to, edge_type])

def main():
    parser = argparse.ArgumentParser(
        description="Conver the OSmosis CSV to another CSV " 
        "more suitable for bulk import in Neo4j"
    )


    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input file, of the current CSV format"
    )
    parser.add_argument(
        "--pd",
        type=str,
        required=True,
        help="Output file PD nodes CSV"
    )

    parser.add_argument(
        "--res",
        type=str,
        required=True,
        help="Output file Resource nodes CSV"
    )
    
    parser.add_argument(
        "--rs",
        type=str,
        required=True,
        help="Output file Resource Space nodes CSV"
    )
    
    parser.add_argument(
        "--edge",
        type=str,
        required=True,
        help="Output file Edges Space nodes CSV"
    )

    args = parser.parse_args()

    split(args.input,
          args.pd,
          args.res,
          args.rs,
          args.edge)

if __name__ == "__main__":
    main()
