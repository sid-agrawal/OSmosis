#!./ve_model_state/bin/python3

from generic_model import *
import argparse

# ./cz_pt.py -f cz_pt.csv &&  cp  cz_pt.csv ~/neo4j/import/cz_pt.csv && python import_csv.py --file cz_pt.csv   
parser = argparse.ArgumentParser("cz_pt")
parser.add_argument("-f", "--file", help="a LOCAL file for CSV output", required=True)
args = parser.parse_args()

if __name__ == "__main__":

    model = ModelGraph()

    # Make Kernel PD 
    kernel_id = model.add_pd_node("Kernel", 0x0)

    # Make Proc1
        # PD
    pd_id1 = model.add_pd_node("LWC1_P1", 0x01)
    req_id = model.add_request_edge(pd_id1, kernel_id, 
                                    ResourceType.VMR, kernel_id)
                            
        # VAS Resource Space
    rs_id1 = model.add_resource_space_node(ResourceType.VMR, 0x01)
    model.add_createdby_edge(kernel_id, ResourceType.VMR, rs_id1)

        # Add a VMR
    res_id1 = model.add_resource_node(ResourceType.VMR, rs_id1)
    model.add_hold_edge(Permission.R, pd_id1, ResourceType.VMR, rs_id1, res_id1, [kernel_id])

    # res_id = model.add_resource_node(ResourceType.VMR, rs_id)
    # model.add_hold_edge(Permission.R, pd_id, ResourceType.VMR, rs_id, res_id)

    # Make Proc1-MD_1
        # PD
    pd_id2 = model.add_pd_node("LWC2_P1", 0x2)
    req_id = model.add_request_edge(pd_id2, kernel_id, 
                                    ResourceType.VMR, kernel_id)
                            
        # VAS Resource Space
    rs_id2 = model.add_resource_space_node(ResourceType.VMR, 0x02)
    model.add_createdby_edge(kernel_id, ResourceType.VMR, rs_id2)
    
        # Add a VMR 1
    res_id2 = model.add_resource_node(ResourceType.VMR, rs_id2)
    model.add_hold_edge(Permission.R, pd_id2, ResourceType.VMR, rs_id2, 
                        res_id2, [kernel_id])
        # Add a VMR 2
    res_id2 = model.add_resource_node(ResourceType.VMR, rs_id2)
    model.add_hold_edge(Permission.R, pd_id2, ResourceType.VMR, rs_id2, 
                        res_id2, [kernel_id])

    # Add all MO resource Space
    rs_id3 = model.add_resource_space_node(ResourceType.MO)
    model.add_createdby_edge(kernel_id, ResourceType.MO, rs_id3)

    # Make a MO page and have two VMR mapped to it
    res_id3 = model.add_resource_node(ResourceType.MO, rs_id3)
    model.add_map_edge(ResourceType.VMR, ResourceType.MO, rs_id1, rs_id3, res_id1, res_id3, [kernel_id])
    model.add_map_edge(ResourceType.VMR, ResourceType.MO, rs_id2, rs_id3, res_id2, res_id3, [kernel_id])

    model.to_csv(filename = args.file)
    print(args.file, "has the CSV of the model state")

    # Process
