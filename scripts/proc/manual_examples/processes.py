from generic_model_v2 import *
import argparse
import json
from utils import EasyDict
import random

#  python ./cz_examples/cz_smv.py -f outputs/cz_manual/cz_smv.csv && python ./import_csv.py -f outputs/cz_manual/cz_smv.csv
parser = argparse.ArgumentParser("cz_smv")
parser.add_argument("-f", "--file", help="a LOCAL file for CSV output", required=True)
args = parser.parse_args()


class HW:
    mo_rs_id: int
    pd_rs_id: int
    pcpu_rs_id: int
    l3set_rs_id: int
    l3set_res_dict: EasyDict = EasyDict()


def pick_random(hw) -> int:
    """
    Pick a random element from l3set_res_dict
    """
    return random.choice(list(hw.l3set_res_dict.values()))


def make_generic_process(model: ModelGraph, name: str, kernel_id: int, hw: HW) -> int:
    pd_id = model.add_pd_node(name, hw.pd_rs_id)
    req_id = model.add_request_edge(pd_id, kernel_id, ResourceType.VMR, kernel_id)

    # VAS Resource Space
    vmr_rs_id = model.add_resource_space_node(ResourceType.VMR)
    model.add_hold_edge(
        perms_all, kernel_id, ResourceType.VMR, vmr_rs_id, None, [kernel_id]
    )
    model.add_map_edge(
        ResourceType.VMR,
        ResourceType.MO,
        vmr_rs_id,
        hw.mo_rs_id,
        None,
        None,
        [kernel_id],
    )

    # VCPU Resource Space
    vcpu_rs_id = model.add_resource_space_node(ResourceType.VCPU)
    model.add_hold_edge(
        perms_all, kernel_id, ResourceType.VCPU, vcpu_rs_id, None, [kernel_id]
    )
    model.add_map_edge(
        ResourceType.VCPU,
        ResourceType.PCPU,
        vcpu_rs_id,
        hw.pcpu_rs_id,
        None,
        None,
        [kernel_id],
    )

    # Add VMRs, MO and mappsings
    for vmr_type in ["stack", "code", "heap"]:
        # Make VMR Node
        vmr_res_id = model.add_resource_node(
            ResourceType.VMR,
            vmr_rs_id,
            extra=json.dumps(
                {
                    "vmr_type": vmr_type,
                }
            ),
        )
        # PD --HOLD--> VMR
        model.add_hold_edge(
            Permission.R, pd_id, ResourceType.VMR, vmr_rs_id, vmr_res_id, [kernel_id]
        )
        # Make MO Node
        mo_res_id = model.add_resource_node(
            ResourceType.MO,
            hw.mo_rs_id,
        )
        # Kernel --HOLD--> VMR
        # model.add_hold_edge(
        #     Permission.R, kernel_id, ResourceType.MO, mo_rs_id, mo_res_id, [kernel_id]
        # )

        # VA --> PA
        model.add_map_edge(
            ResourceType.VMR,
            ResourceType.MO,
            vmr_rs_id,
            hw.mo_rs_id,
            vmr_res_id,
            mo_res_id,
            [kernel_id],
        )

        l3_set = pick_random(hw)
        model.add_map_edge(
            ResourceType.MO,
            ResourceType.L3SET,
            hw.mo_rs_id,
            hw.l3set_rs_id,
            mo_res_id,
            l3_set,
            [kernel_id],
        )

    # Add CPU virtual and physical
    vcpu_res_id = model.add_resource_node(
        ResourceType.VCPU,
        vcpu_rs_id,
    )
    # PD --HOLD--> VCPU
    model.add_hold_edge(
        Permission.R, pd_id, ResourceType.VCPU, vcpu_rs_id, vcpu_res_id, [kernel_id]
    )
    # Make MO Node
    pcpu_res_id = model.add_resource_node(
        ResourceType.PCPU,
        hw.pcpu_rs_id,
    )
    # Kernel --HOLD--> VMR
    # model.add_hold_edge(
    #     Permission.R, kernel_id, ResourceType.MO, hw.mo_rs_id, mo_res_id, [kernel_id]
    # )

    # VA --> PA
    model.add_map_edge(
        ResourceType.VCPU,
        ResourceType.PCPU,
        vcpu_rs_id,
        hw.pcpu_rs_id,
        vcpu_res_id,
        pcpu_res_id,
        [kernel_id],
    )

    return pd_id


if __name__ == "__main__":

    model = ModelGraph()
    hw = HW()

    # Make Kernel PD
    # kernel_id = model.add_pd_node("Kernel", 0x0)
    kernel_id =  0
    model.g.add_node(
        f"PD_{kernel_id}",type=NodeType.PD.name, data="Kernel", extra=""
    )

    # Create HW
    # MO Resource Space
    hw.mo_rs_id = model.add_resource_space_node(ResourceType.MO)
    model.add_hold_edge(
        perms_all, kernel_id, ResourceType.MO, hw.mo_rs_id, None, [kernel_id]
    )
    
    # PD Resource Space
    hw.pd_rs_id = model.add_resource_space_node(ResourceType.PD)
    model.add_hold_edge(
        perms_all, kernel_id, ResourceType.PD, hw.pd_rs_id, None, [kernel_id]
    )

    # PCPU Resource Space
    hw.pcpu_rs_id = model.add_resource_space_node(ResourceType.PCPU)
    model.add_hold_edge(
        perms_all, kernel_id, ResourceType.PCPU, hw.pcpu_rs_id, None, [kernel_id]
    )

    # L3 Cache Set Resource Space
    hw.l3set_rs_id = model.add_resource_space_node(ResourceType.L3SET)
    model.add_hold_edge(
        perms_all, kernel_id, ResourceType.L3SET, hw.l3set_rs_id, None, [kernel_id]
    )
    hw.l3set_res_dict.one = model.add_resource_node(ResourceType.L3SET, hw.l3set_rs_id)
    hw.l3set_res_dict.two = model.add_resource_node(ResourceType.L3SET, hw.l3set_rs_id)
    hw.l3set_res_dict.three = model.add_resource_node(
        ResourceType.L3SET, hw.l3set_rs_id
    )
    hw.l3set_res_dict.four = model.add_resource_node(ResourceType.L3SET, hw.l3set_rs_id)

    # Process
    pid1 = make_generic_process(model, "P1", kernel_id, hw)
    pid2 = make_generic_process(model, "P2", kernel_id, hw)

    model.to_csv(filename=args.file)
    print(args.file, "has the CSV of the model state")
