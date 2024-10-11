#!./ve_model_state/bin/python3

from generic_model import *
import argparse

# ./cz_cheri-dynamic.py -f cz_cheri-dynamic.csv &&  cp  cz_cheri-dynamic.csv ~/neo4j/import/cz_cheri-dynamic.csv && python import_csv.py --file cz_cheri-dynamic.csv   
parser = argparse.ArgumentParser("cz_cheri-dynamic")
parser.add_argument("-f", "--file", help="a LOCAL file for CSV output", required=True)
args = parser.parse_args()

if __name__ == "__main__":

    model = ModelGraph()

    # Make Kernel PD 
    kernel_id = model.add_pd_node("Kernel", 0x0)

    # Make Proc1
        # PD
    pd_id = model.add_pd_node("P1")
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

    # Make Proc1-CHERI_1
        # PD
    pdd_id = model.add_pd_node("CHERI1_P1")
    req_id = model.add_request_edge(pdd_id, pd_id, 
                                    ResourceType.BUFF, res_id)
                            
        # Colored VAS Resource Space
    crs_id = model.add_resource_space_node(ResourceType.BUFF)
    model.add_createdby_edge(pd_id, ResourceType.BUFF, crs_id)
    
        # Add a CVA Resources
    cres_id = model.add_resource_node(ResourceType.BUFF, crs_id)
    model.add_hold_edge(Permission.R, pdd_id, ResourceType.BUFF, crs_id, cres_id, [pd_id, pdd_id])
    
    model.add_map_edge(ResourceType.BUFF, ResourceType.VMR, crs_id, rs_id,
                       cres_id, res_id, [pd_id])


    pdd_id2 = model.add_pd_node("CHERI2_P1")
    req_id2 = model.add_request_edge(pdd_id2, pd_id, 
                                    ResourceType.BUFF, crs_id)
    
    model.add_hold_edge(Permission.R, pdd_id2, ResourceType.BUFF, crs_id, cres_id, [pd_id, pdd_id2])
        # Add a  Resources
    cres_id = model.add_resource_node(ResourceType.BUFF, crs_id)
    model.add_hold_edge(Permission.R, pdd_id2, ResourceType.BUFF, crs_id, cres_id, [pd_id, pdd_id2])

    model.add_map_edge(ResourceType.BUFF, ResourceType.VMR, crs_id, rs_id,
                       cres_id, res_id, [pd_id])
    model.to_csv(filename = args.file)
    print(args.file, "has the CSV of the model state")

    # Process
