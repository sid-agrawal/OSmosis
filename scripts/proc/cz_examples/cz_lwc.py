from generic_model_v2 import *
import argparse
import json

#  python ./cz_examples/cz_lwc.py -f outputs/cz_manual/cz_lwc.csv && python ./import_csv.py -f outputs/cz_manual/cz_lwc.csv
parser = argparse.ArgumentParser("cz_lwc")
parser.add_argument("-f", "--file", help="a LOCAL file for CSV output", required=True)
args = parser.parse_args()


def make_generic_process_with_threads_page_table(model: ModelGraph, name: str, kernel_id: int, mo_rs_id: int, pcpu_rs_id: int):

    # Add T1
    l1_id = model.add_pd_node(f"{name}_L1")
    req_id = model.add_request_edge(l1_id, kernel_id, 
                                    ResourceType.VMR, kernel_id)
    # Add T2
    l2_id = model.add_pd_node(f"{name}_L2")
    req_id = model.add_request_edge(l2_id, kernel_id, 
                                    ResourceType.VMR, kernel_id)

    # 2 VAS Resource Spaces, node, map edge to physical resource and edge from the kernel
    vmr1_rs_id = model.add_resource_space_node(ResourceType.VMR)
    model.add_hold_edge(perms_all, kernel_id, ResourceType.VMR, vmr1_rs_id, None, [kernel_id])
    model.add_map_edge(
        ResourceType.VMR, ResourceType.MO, vmr1_rs_id, mo_rs_id, None, None, [kernel_id]
    )

    vmr2_rs_id = model.add_resource_space_node(ResourceType.VMR)
    model.add_map_edge(
         ResourceType.VMR, ResourceType.MO, vmr2_rs_id, mo_rs_id, None, None, [kernel_id]
    )
    model.add_hold_edge(
        perms_all, kernel_id, ResourceType.VMR, vmr2_rs_id, None, [kernel_id]
    )

    ################################################
    ## Private Mappings
    ################################################
    # Add VMRs, MO and mappsings
    for vmr_type in ["stack", "heap"]:
        # Make VMR Node for L1
        vmr1_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr1_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": vmr_type,
                }
            ),
        )

        # Make VMR Node for L2
        vmr2_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr2_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": vmr_type,
                }
            ),
        )
        # PD --HOLD--> VMR
        model.add_hold_edge(
            Permission.R, l1_id, ResourceType.VMR, vmr1_rs_id, vmr1_res_id, [kernel_id]
        )
        model.add_hold_edge(
            Permission.R, l2_id, ResourceType.VMR, vmr2_rs_id, vmr2_res_id, [kernel_id]
        )
        
        # Make MO Node
        mo1_res_id = model.add_resource_node(
            ResourceType.MO,
            mo_rs_id,
        )
        mo2_res_id = model.add_resource_node(
            ResourceType.MO,
            mo_rs_id,
        )
        # VA --> PA
        model.add_map_edge(
            ResourceType.VMR,
            ResourceType.MO,
            vmr1_rs_id,
            mo_rs_id,
            vmr1_res_id,
            mo1_res_id,
            [kernel_id]
        )

        model.add_map_edge(
            ResourceType.VMR,
            ResourceType.MO,
            vmr2_rs_id,
            mo_rs_id,
            vmr2_res_id,
            mo2_res_id,
            [kernel_id]
        )

    ################################################
    ## Shared Mappings
    ################################################
    for vmr_type in ["other", "code", "heap"]:
        # Make VMR Node for L1
        vmr1_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr1_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": vmr_type,
                }
            ),
        )

        # Make VMR Node for L2
        vmr2_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr2_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": vmr_type,
                }
            ),
        )

        # PD --HOLD--> VMR
        model.add_hold_edge(
            Permission.R, l1_id, ResourceType.VMR, vmr1_rs_id, vmr1_res_id, [kernel_id]
        )
        model.add_hold_edge(
            Permission.R, l2_id, ResourceType.VMR, vmr2_rs_id, vmr2_res_id, [kernel_id]
        )
        # Make MO Node
        mo_res_id = model.add_resource_node(
            ResourceType.MO,
            mo_rs_id,
        )
        # VA --> PA
        model.add_map_edge(
            ResourceType.VMR,
            ResourceType.MO,
            vmr1_rs_id,
            mo_rs_id,
            vmr1_res_id,
            mo_res_id,
            [kernel_id]
        )

        model.add_map_edge(
            ResourceType.VMR,
            ResourceType.MO,
            vmr2_rs_id,
            mo_rs_id,
            vmr2_res_id,
            mo_res_id,
            [kernel_id]
        )

    #############################################################
    ###                 CPU STUFF
    #############################################################

    # VCPU Resource Space, node, map edge to physical resource and edge from the kernel
    vcpu_rs_id = model.add_resource_space_node(ResourceType.ExecContext)
    model.add_hold_edge(perms_all, kernel_id, ResourceType.ExecContext, vcpu_rs_id, None, [kernel_id])
    model.add_map_edge(
        ResourceType.ExecContext, ResourceType.PCPU, vcpu_rs_id, pcpu_rs_id, None, None, [kernel_id]
    )

    # Add CPU virtual and physical for only of the two domains
    for t_id in [l1_id]:
        vcpu_res_id = model.add_resource_node(
            ResourceType.ExecContext,
            vcpu_rs_id,
        )
        # PD --HOLD--> VCPU
        model.add_hold_edge(
            Permission.R, t_id, ResourceType.ExecContext, vcpu_rs_id, vcpu_res_id, [kernel_id]
        )

        # Make MO Node
        pcpu_res_id = model.add_resource_node(
            ResourceType.PCPU,
            pcpu_rs_id,
        )
        # Kernel --HOLD--> VMR
        # model.add_hold_edge(
        #     Permission.R, kernel_id, ResourceType.MO, mo_rs_id, mo_res_id, [kernel_id]
        # )

        # VA --> PA
        model.add_map_edge(
            ResourceType.ExecContext,
            ResourceType.PCPU,
            vcpu_rs_id,
            pcpu_rs_id,
            vcpu_res_id,
            pcpu_res_id,
            [kernel_id],
        )

    return  l1_id, l2_id


if __name__ == "__main__":

    model = ModelGraph()

    # Make Kernel PD
    kernel_id = model.add_pd_node("Kernel", 0x0)
    
    # Create HW
    # MO Resource Space
    mo_rs_id = model.add_resource_space_node(ResourceType.MO)
    model.add_hold_edge(perms_all, kernel_id, ResourceType.MO, mo_rs_id, None, [kernel_id])

    # PCPU Resource Space
    pcpu_rs_id = model.add_resource_space_node(ResourceType.PCPU)
    model.add_hold_edge(perms_all, kernel_id, ResourceType.PCPU, pcpu_rs_id, None, [kernel_id])

    # Two LWCs
    pid1, pid2 = make_generic_process_with_threads_page_table(model, "P1", kernel_id, mo_rs_id, pcpu_rs_id)
    
    
    model.to_csv(filename = args.file)
    print(args.file, "has the CSV of the model state")
