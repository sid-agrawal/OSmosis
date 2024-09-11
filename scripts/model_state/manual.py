#!./ve_model_state/bin/python3

from generic_model import *
import argparse

parser = argparse.ArgumentParser("manual")
parser.add_argument("-f", "--file", help="a LOCAL file for CSV output", required=True)
args = parser.parse_args()

if __name__ == "__main__":

    model = ModelGraph()

    # Make Kernel PD 
    kernel_id = model.add_pd_node("Kernel")

    # Make Proc1
        # PD
    pd_id = model.add_pd_node("Proc1")
    req_id = model.add_request_edge(pd_id, kernel_id, 
                                    ResourceType.VMR, kernel_id)
                            
        # VAS Resource Space
    rs_id = model.add_resource_space_node(ResourceType.VMR, 0x01)
    model.add_createdby_edge(kernel_id, ResourceType.VMR, rs_id)

        # Add a VMR
    res_id = model.add_resource_node(ResourceType.VMR, rs_id)
    model.add_hold_edge(Permission.R, pd_id, ResourceType.VMR, rs_id, res_id)

    # res_id = model.add_resource_node(ResourceType.VMR, rs_id)
    # model.add_hold_edge(Permission.R, pd_id, ResourceType.VMR, rs_id, res_id)

    # Make Proc1-MPK_1
        # PD
    pdd_id = model.add_pd_node("Proc1_D1")
    # req_id = model.add_request_edge(pdd_id, kernel_id, 
    #                                 ResourceType.VMR, kernel_id)
                            
        # Colored VAS Resource Space
    crs_id = model.add_resource_space_node(ResourceType.CVMR)
    model.add_createdby_edge(pd_id, ResourceType.CVMR, crs_id)

        # Add a VMR
    cres_id = model.add_resource_node(ResourceType.CVMR, crs_id)
    model.add_hold_edge(Permission.R, pdd_id, ResourceType.CVMR, crs_id, cres_id)

    model.add_map_edge(ResourceType.CVMR, ResourceType.VMR, crs_id, rs_id,
                       cres_id, res_id, pd_id)



    model.to_csv(filename = args.file)
    print(args.file, "has the CSV of the model state")

    # Process
