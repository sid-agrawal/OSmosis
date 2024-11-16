from generic_model_v2 import *
import argparse
import json

#  python ./cz_examples/threads.py -f outputs/cz_manual/threads.csv && python ./import_csv.py -f outputs/cz_manual/threads.csv
parser = argparse.ArgumentParser("threads")
parser.add_argument(
        "--impl",
        type=str,
        choices=["page-table", "other"],
        required=True,
        help="In a page-table impl, we will have to VAS Resource Spaces"
    )
parser.add_argument("-f", "--file", help="a LOCAL file for CSV output", required=True)
args = parser.parse_args()

def make_generic_process_with_threads_other(model: ModelGraph, name: str, kernel_id: int, mo_rs_id: int, pcpu_rs_id: int):
    # Add T1
    t1_id = model.add_pd_node(f"{name}_T1")
    req_id = model.add_request_edge(t1_id, kernel_id, 
                                    ResourceType.VMR, kernel_id)
    # Add T2
    t2_id = model.add_pd_node(f"{name}_T2")
    req_id = model.add_request_edge(t2_id, kernel_id, 
                                    ResourceType.VMR, kernel_id)

    # Only 1 VAS Resource Spaces, node, map edge to physical resource and edge from the kernel
    vmr1_rs_id = model.add_resource_space_node(ResourceType.VMR)
    model.add_hold_edge(perms_all, kernel_id, ResourceType.VMR, vmr1_rs_id, None, [kernel_id])
    model.add_map_edge(
        ResourceType.VMR, ResourceType.MO, vmr1_rs_id, mo_rs_id, None, None, [kernel_id]
    )

    # Handle Stack 1
    for t_id in [t1_id, t2_id]:
        stack_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr1_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": "stack",
                }
            ),
        )

        # T1 --HOLD--> Stack1
        model.add_hold_edge(
            Permission.R, t_id, ResourceType.VMR, vmr1_rs_id, stack_res_id, [kernel_id]
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
            stack_res_id,
            mo_res_id,
            [kernel_id],
        )

    # Add VMRs, MO and mappsings
    for vmr_type in ["code", "heap"]:
        # Make VMR Node for T1
        vmr1_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr1_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": vmr_type,
                }
            ),
        )

        # PD --HOLD--> VMR
        model.add_hold_edge(
            Permission.R, t1_id, ResourceType.VMR, vmr1_rs_id, vmr1_res_id, [kernel_id]
        )
        model.add_hold_edge(
            Permission.R, t2_id, ResourceType.VMR, vmr1_rs_id, vmr1_res_id, [kernel_id]
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
            vmr1_rs_id,
            mo_rs_id,
            vmr1_res_id,
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

    # Add CPU virtual and physical for two threads
    for t_id in [t1_id, t2_id]:
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

    return  t1_id, t2_id


def make_generic_process_with_threads_page_table(model: ModelGraph, name: str, kernel_id: int, mo_rs_id: int, pcpu_rs_id: int):

    # Add T1
    t1_id = model.add_pd_node(f"{name}_T1")
    req_id = model.add_request_edge(t1_id, kernel_id, 
                                    ResourceType.VMR, kernel_id)
    # Add T2
    t2_id = model.add_pd_node(f"{name}_T2")
    req_id = model.add_request_edge(t2_id, kernel_id, 
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

    # Add VMRs, MO and mappsings
    for vmr_type in ["stack", "code", "heap"]:
        # Make VMR Node for T1
        vmr1_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr1_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": vmr_type,
                }
            ),
        )

        # Make VMR Node for T2
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
            Permission.R, t1_id, ResourceType.VMR, vmr1_rs_id, vmr1_res_id, [kernel_id]
        )
        model.add_hold_edge(
            Permission.R, t2_id, ResourceType.VMR, vmr2_rs_id, vmr2_res_id, [kernel_id]
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

    # Add CPU virtual and physical for two threads
    for t_id in [t1_id, t2_id]:
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

    return  t1_id, t2_id


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

    # Process
    match args.impl:
        case "page-table":
            pid1, pid2 = make_generic_process_with_threads_page_table(model, "P1", kernel_id, mo_rs_id, pcpu_rs_id)
        case "other":
            pid1, pid2 = make_generic_process_with_threads_other(model, "P1", kernel_id, mo_rs_id, pcpu_rs_id)
    
    
    model.to_csv(filename = args.file)
    print(args.file, "has the CSV of the model state")
