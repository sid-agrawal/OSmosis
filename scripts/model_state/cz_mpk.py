#!./ve_model_state/bin/python3

from generic_model import *
import argparse

# ./cz_mpk.py -f cz_mpk.csv &&  cp  cz_mpk.csv ~/neo4j/import/cz_mpk.csv && python import_csv.py --file cz_mpk.csv   
parser = argparse.ArgumentParser("cz_mpk")
parser.add_argument("-f", "--file", help="a LOCAL file for CSV output", required=True)
args = parser.parse_args()

if __name__ == "__main__":

    model = ModelGraph()

    # Make Kernel PD 
    kernel_id = model.add_pd_node("Kernel", 0x0)

    # Make Proc1
        # PD
    pd_id = model.add_pd_node("P1", 0x01)
    req_id = model.add_request_edge(pd_id, kernel_id, 
                                    ResourceType.VMR, kernel_id)
                            
        # VAS Resource Space
    rs_id = model.add_resource_space_node(ResourceType.VMR, 0x01)
    model.add_createdby_edge(kernel_id, ResourceType.VMR, rs_id)

        # Add a VMR
    res_id = model.add_resource_node(ResourceType.VMR, rs_id)
    model.add_hold_edge(Permission.R, pd_id, ResourceType.VMR, rs_id, res_id, [kernel_id])

    # res_id = model.add_resource_node(ResourceType.VMR, rs_id)
    # model.add_hold_edge(Permission.R, pd_id, ResourceType.VMR, rs_id, res_id)

    # Make Proc1-MPK_1
        # PD
    pdd_id1 = model.add_pd_node("MPK1_P1", 0x2)
                            
        # Colored VAS Resource Space
    crs_id1 = model.add_resource_space_node(ResourceType.PVA, "Key1")
    model.add_createdby_edge(pd_id, ResourceType.PVA, crs_id1)
    req_id = model.add_request_edge(pdd_id1, pd_id, 
                                    ResourceType.PVA, crs_id1)
    
    crs_id2 = model.add_resource_space_node(ResourceType.PVA, "Key2")
    model.add_createdby_edge(pd_id, ResourceType.PVA, crs_id2)

        # Add a CVA Resources
    cres_id1 = model.add_resource_node(ResourceType.PVA, crs_id1, "Key1")
    model.add_hold_edge(Permission.R, pdd_id1, ResourceType.PVA, crs_id1, cres_id1, [pd_id])
    
    cres_id2 = model.add_resource_node(ResourceType.PVA, crs_id2, "Key2")
    model.add_hold_edge(Permission.R, pdd_id1, ResourceType.PVA, crs_id2, cres_id2, [pd_id])

    model.add_map_edge(ResourceType.PVA, ResourceType.VMR, crs_id1, rs_id,
                       cres_id1, res_id, [kernel_id])

    # Make Proc1-MPK_1
        # PD
    pdd_id2 = model.add_pd_node("MPK1_P2", 0x3)
    model.add_hold_edge(Permission.R, pdd_id2, ResourceType.PVA, crs_id2, cres_id2, [pd_id])

    req_id = model.add_request_edge(pdd_id2, pd_id, 
                                    ResourceType.PVA, crs_id2)
    # Invariant:
       # A VA can be a target to max 16 CVA

    model.to_csv(filename = args.file)
    print(args.file, "has the CSV of the model state")

    # Process
