from enum import Enum
import networkx as nx
import csv
import json

## Constants
page_size = 4096  # Assume all 4k pages for now
page_size_bits = 12


class NodeType(Enum):
    RESOURCE = 1
    RESOURCE_SPACE = 2
    PD = 3


class EdgeType(Enum):
    HOLD = 1
    MAP = 2
    SUBSET = 3
    REQUEST = 4


class ResourceType(Enum):
    VMR = 1
    MO = 2  # Same as PMR, a region of contiguous virtual memory
    PID = 3  # Same as PMR, a region of contiguous virtual memory
    FILE = 4  # File system resources


class VmrType(Enum):
    UNKNOWN = 0
    NONE = 1
    STACK = 2
    PROGRAM = 3
    LIB = 4
    VDSO = 5
    VVAR = 6
    VSYSCALL = 7
    HEAP = 8
    SHM = 9
    DEV = 10
    KVM = 11


class FileType(Enum):
    UNKNOWN = 0
    REGULAR = 1    # Regular files
    CONFIG = 2     # Configuration files
    LOG = 3        # Log files
    DATABASE = 4   # Database files
    LIBRARY = 5    # Shared library files
    EXECUTABLE = 6 # Executable files
    TEMP = 7       # Temporary files
    CACHE = 8      # Cache files
    DEVICE = 9     # Device files
    SOCKET = 10    # Socket files


class Permission(Enum):
    R = 0  # read
    W = 1  # write
    X = 2  # execute
    P = 3  # private
    S = 4  # private

    # Define ordering to print permissions in consistent order
    def __lt__(self, other):
        return self.value < other.value


class Permissions:
    """
    Stores a set of binary permissions for a hold edge
    """

    def __init__(self, perm_set: set[Permission] = {}):
        self.perms = perm_set

    def __str__(self):
        perms = ""
        for perm in sorted(list(self.perms), reverse=False):
            perms += perm.name

        return perms


perms_all = Permissions({Permission.R, Permission.W, Permission.X})


class EasyDict:
    """
    Dict that can be accessed with dot notation
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return self.__dict__.get(name)

    def __setattr__(self, name, val):
        self.__dict__[name] = val

    def __delattr__(self, name):
        del self.__dict__[name]

    def __str__(self):
        return self.__dict__.__str__()

    def __repr__(self):
        return self.__dict__.__str__()


class ModelGraph:
    def __init__(self, id_offset=0):
        self.g = nx.MultiDiGraph()
        self.pd_counter = id_offset
        self.space_counter = id_offset
        self.resource_counters = {}

    def __resource_string_id(self, res_type: ResourceType, space_id: int, res_id: int):
        return f"{res_type.name}_{space_id}_{res_id}"

    def __space_string_id(self, res_type: ResourceType, space_id: int):
        return f"{res_type.name}_SPACE_{space_id}"

    def __pd_string_id(self, pd_id: int):
        return f"PD_{pd_id}"

    def add_resource_node(
        self,
        res_type: ResourceType,
        space_id: int,
        res_id: int | None = None,
        extra: str = None,
    ) -> int:
        """
        Add a resource node to a model state graph, including the subset edge to the resource space

        :param res_type: The resource node's type
        :param space_id: ID of the space to add the resource to
        :param res_id: The resource node's unique ID within the space
                Optional: if None, a new ID will be assigned
        :param extra: Data to put in the "extra" field, depends on resource type
        :return: the resource ID
        """
        if res_id is None:
            # Initialize counter if it doesn't exist
            if space_id not in self.resource_counters:
                self.resource_counters[space_id] = 0
            self.resource_counters[space_id] += 1
            res_id = self.resource_counters[space_id]

        string_id = self.__resource_string_id(res_type, space_id, res_id)
        self.g.add_node(
            string_id, type=NodeType.RESOURCE.name, data=res_type.name, extra=extra
        )

        space_string_id = self.__space_string_id(res_type, space_id)
        self.__add_edge(EdgeType.SUBSET, string_id, space_string_id)

        return res_id

    def add_vmr_node(
        self, space_id: int, vmr_type: VmrType, n_pages: int, vaddr: int
    ) -> int:
        """
        Add a VMR node to a model state graph, including the subset edge to the address space

        :param space_id: ID of the address space to add the VMR to
        :param vmr_type: The type of VMR reservation (CODE, STACK, etc.)
        :param n_pages: Number of 4k pages in the VMR
        :param vadd: virtual address
        :return: the resource ID
        """

        # This is formatted to match the CellulOS output
        # extra = f'{vmr_type.name}_{n_pages}_{page_size_bits}'
        extra = {
            "va": hex(vaddr),
            "vmr_type": vmr_type.name,
            "num_pages": str(n_pages),
            "page_size": str(1 << page_size_bits),
        }
        return self.add_resource_node(
            ResourceType.VMR, space_id, None, json.dumps(extra)
        )

    def add_mo_node(self, space_id: int, phys_addr: int, n_pages: int) -> int:
        """
        Add an MO node to a model state graph, including the subset edge to the device

        :param space_id: ID of the device's physical memory space to add the MO to
        :param phys_addr: Physical address of this MO
        :param n_pages: Number of 4k pages in the MO
        :return: the resource ID
        """

        # This is formatted to match the CellulOS output
        # extra = f'{phys_addr:16x}_{n_pages}_{page_size_bits}'
        extra = {
            "pa": hex(phys_addr),
            "num_pages": str(n_pages),
            "page_size": str(1 << page_size_bits),
        }

        return self.add_resource_node(
            ResourceType.MO, space_id, None, json.dumps(extra)
        )

    def add_file_node(
        self, space_id: int, file_type: FileType, file_path: str, file_size: int = 0
    ) -> int:
        """
        Add a FILE node to a model state graph, including the subset edge to the file system space

        :param space_id: ID of the file system space to add the file to
        :param file_type: The type of file (CONFIG, LOG, DATABASE, etc.)
        :param file_path: File path string (e.g., "/etc/config.txt", "/var/log/app.log")
        :param file_size: Size of file in bytes (default: 0)
        :return: the resource ID
        """

        extra = {
            "path": file_path,
            "file_type": file_type.name,
            "size_bytes": str(file_size),
            "permissions": "rw-"  # Default file permissions
        }
        return self.add_resource_node(
            ResourceType.FILE, space_id, None, json.dumps(extra)
        )

    def add_pd_node(self, name: str, pd_id: int | None = None) -> int:
        """
        Add a PD node to a model state graph

        :param name: The PD's name
        :param pd_id: The PD's unique ID
            Optional: if None, a new ID will be assigned
        :return: the PD ID
        """

        if pd_id is None:
            self.pd_counter += 1
            pd_id = self.pd_counter

        string_id = self.__pd_string_id(pd_id)
        self.g.add_node(string_id, type=NodeType.PD.name, data=name, extra="")

        return pd_id

    def add_resource_space_node(
        self, res_type: ResourceType, space_id: int = None
    ) -> int:
        """
        Add a resource node to a model state graph, including the subset edge to the resource space

        :param res_type: The resource space's type
        :param space_id: The resource space's unique ID
                Optional: if None, a new ID will be assigned
        :return: the space ID
        """

        if space_id is None:
            self.space_counter += 1
            space_id = self.space_counter

        self.resource_counters[space_id] = 0

        string_id = self.__space_string_id(res_type, space_id)
        self.g.add_node(
            string_id, type=NodeType.RESOURCE_SPACE.name, data=res_type.name, extra=""
        )

        return space_id

    def __add_edge(
        self,
        edge_type: EdgeType,
        string_id_from: str,
        string_id_to: str,
        data: str | None = "NONE",
        extra: str | None = "",
    ):
        """
        Internal function to add an edge to the model state

        :param edge_type: The type of edge
        :param string_id_from: the string ID of the 'from' node
        :param string_id_to: the string ID of the 'from' node
        :param data: any data string to add to the edge
        :type data: string or None
        """
        self.g.add_edge(string_id_from, string_id_to, type=edge_type.name, data=data, extra=extra)

    def add_hold_edge(
        self,
        perms: Permission,
        pd_id: int,
        res_type: ResourceType,
        space_id: int,
        res_id: int | None = None,
        pd_incharge: str | None = None,
    ):
        """
        Add a hold edge from a PD to a resource or resource space

        :param pd_id: The PD's unique ID
        :param res_type: The resource space's type
        :param space_id: The resource space's unique ID
        :param res_id: The resource's unique ID
                Optional: if None, the hold edge is for a resource space
        """
        pd_string_id = self.__pd_string_id(pd_id)
        target_string_id = ""
        if res_id is None:
            target_string_id = self.__space_string_id(res_type, space_id)
        else:
            target_string_id = self.__resource_string_id(res_type, space_id, res_id)

        extra = { "pd_incharge" : pd_incharge}

        self.__add_edge(EdgeType.HOLD, pd_string_id, target_string_id, str(perms), json.dumps(extra))
    
    def add_inter_pd_hold_edge(
        self,
        perms: Permission,
        from_pd_id: int,
        to_pd_id: int,
        pd_incharge: str | None = None,
    ):
        """
        Add a hold edge from a PD to another PD 

        :param Permission: Signals allowed
        :param from_pd_id: The PD's unique ID
        :param to_pd_id: The PD's unique ID
        :param pd_incharge: The PD's unique ID

        """
        from_pd_string_id = self.__pd_string_id(from_pd_id)
        to_pd_string_id = self.__pd_string_id(to_pd_id)

        extra = { "pd_incharge" : pd_incharge}

        self.__add_edge(EdgeType.HOLD, from_pd_string_id, to_pd_string_id, str(perms), json.dumps(extra))


    def add_map_edge(
        self,
        res_type_1: int,
        res_type_2: int,
        space_id_1: int,
        space_id_2: int,
        res_id_1: int | None = None,
        res_id_2: int | None = None,
        pd_incharge: str | None = None,
    ):
        """
        Add a map edge from a PD to a resource to a resource or a resource space to a resource space

        :param res_type_1: The source resource space's type
        :param res_type_2: The destinatino resource space's type
        :param space_id_1: The source resource space's unique ID
        :param space_id_2: The source resource space's unique ID
        :param res_id_1: The source resource's unique ID
                Optional: if None, the map edge is for a resource space
        :param res_id_1: The destination resource's unique ID
                Optional: if None, the map edge is for a resource space
        """
        source_string_id = ""
        dest_string_id = ""

        if res_id_1 is None:
            source_string_id = self.__space_string_id(res_type_1, space_id_1)
            dest_string_id = self.__space_string_id(res_type_2, space_id_2)
        else:
            source_string_id = self.__resource_string_id(
                res_type_1, space_id_1, res_id_1
            )
            dest_string_id = self.__resource_string_id(res_type_2, space_id_2, res_id_2)

        extra = { "pd_incharge" : pd_incharge}

        self.__add_edge(EdgeType.MAP, source_string_id, dest_string_id, data="", extra=json.dumps(extra))

    def add_map_edge_raw(
        self, source_string_id: str, dest_string_id: str, pd_incharge: str | None = None
    ):
        """
        Add a map edge from a node to another node
        Assumes that source_string_id & des_string_id is correctly formatted.

        """

        extra = { "pd_incharge" : pd_incharge}
        self.__add_edge(EdgeType.MAP, source_string_id, dest_string_id, extra=json.dumps(extra))

    def add_request_edge(
        self, 
        source_pd_id: int, 
        dest_pd_id: int, 
        res_type: ResourceType, 
        space_id: int,
        pd_incharge: str | None = None,
    ):
        """
        Add a request edge from a PD to a PD

        :param source_pd_id: The source PD's unique ID
        :param dest_pd_id: The desination PD's unique ID
        :param res_type: The request edge's type
        :param space_id: The request edge's space ID
        :param res_id: The resource's unique ID
                Optional: if None, the hold edge is for a resource space
        """
        source_string_id = self.__pd_string_id(source_pd_id)
        dest_string_id = self.__pd_string_id(dest_pd_id)

        rs_string_id = self.__space_string_id(res_type, space_id)

        extra = { "pd_incharge" : pd_incharge}

        # Should be showing space ID too, need to update the CellulOS model output
        self.__add_edge(
            EdgeType.REQUEST, source_string_id, dest_string_id, rs_string_id, extra= json.dumps(extra)
        )

    def add_request_edge_raw(
        self, source_string_id: str, dest_string_id: str, pd_incharge: str | None = None
    ):
        """
        Add a request edge from a node to another node
        Assumes that source_string_id & des_string_id is correctly formatted.

        """

        extra = { "pd_incharge" : pd_incharge}
        self.__add_edge(EdgeType.REQUEST, source_string_id, dest_string_id, extra=json.dumps(extra))

    def to_csv(self, filename: str = "proc_model.csv", only_edge: bool = False):
        """
        Write the model state to a CSV

        :param filename: Where to save the CSV
        """

        headers = [
            "NODE_TYPE",
            "NODE_ID",
            "DATA",
            "EDGE_TYPE",
            "EDGE_FROM",
            "EDGE_TO",
            "EXTRA",
        ]
        with open(filename, mode="w", newline="") as file:
            writer = csv.writer(file)

            writer.writerow(headers)

            if not only_edge:
                for node, data in self.g.nodes(data=True):
                    writer.writerow(
                        [
                            data.get("type"),
                            node,
                            data.get("data"),
                            None,
                            None,
                            None,
                            data.get("extra"),
                        ]
                    )

            for node_from, node_to, data in self.g.edges(data=True):
                writer.writerow(
                    [
                        None,
                        None,
                        data.get("data"),
                        data.get("type"),
                        node_from,
                        node_to,
                        data.get("extra"),
                    ]
                )
