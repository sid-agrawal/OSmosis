from generic_model import *

if __name__ == "__main__":
    print("Manual printing") 

    model = ModelGraph()
    kernel_id = model.add_pd_node("Kernel")
    pd_id = model.add_pd_node("Proc")
    req_id = model.add_request_edge(pd_id, kernel_id, ResourceType.VMR, 0x00)
    model.to_csv(filename = "manual.csv")