"""
OSmosis Graph Transformations

This module defines the valid ways an OSmosis model graph can be transformed
while preserving graph validity and semantic integrity.
"""

from enum import Enum
from typing import Optional, Set, Dict, Any
from generic_model import ModelGraph, NodeType, EdgeType, ResourceType, VmrType, Permission


class TransformationType(Enum):
    """Types of valid graph transformations"""
    NODE_ADD = "node_add"
    NODE_REMOVE = "node_remove" 
    NODE_MODIFY = "node_modify"
    EDGE_ADD = "edge_add"
    EDGE_REMOVE = "edge_remove"
    EDGE_MODIFY = "edge_modify"


class GraphTransformation:
    """Base class for graph transformations"""
    
    def __init__(self, transformation_type: TransformationType):
        self.type = transformation_type
    
    def apply(self, graph: ModelGraph) -> bool:
        """Apply transformation to graph. Returns True if successful."""
        raise NotImplementedError
    
    def validate(self, graph: ModelGraph) -> bool:
        """Validate if transformation can be safely applied."""
        raise NotImplementedError


class NodeTransformations:
    """Node-level transformations that preserve graph validity"""
    
    @staticmethod
    def add_pd_node(graph: ModelGraph, name: str, pd_id: Optional[int] = None) -> int:
        """Add a new PD node with unique ID"""
        return graph.add_pd_node(name, pd_id)
    
    @staticmethod
    def add_resource_space(graph: ModelGraph, res_type: ResourceType, space_id: Optional[int] = None) -> int:
        """Add a new resource space node"""
        return graph.add_resource_space_node(res_type, space_id)
    
    @staticmethod
    def add_vmr_resource(graph: ModelGraph, space_id: int, vmr_type: VmrType, 
                        n_pages: int, vaddr: int) -> int:
        """Add VMR resource to existing VMR space"""
        return graph.add_vmr_node(space_id, vmr_type, n_pages, vaddr)
    
    @staticmethod
    def add_mo_resource(graph: ModelGraph, space_id: int, phys_addr: int, n_pages: int) -> int:
        """Add MO resource to existing MO space"""
        return graph.add_mo_node(space_id, phys_addr, n_pages)
    
    @staticmethod
    def modify_pd_name(graph: ModelGraph, pd_id: int, new_name: str) -> bool:
        """Modify PD node name"""
        pd_string_id = f"PD_{pd_id}"
        if pd_string_id in graph.g.nodes:
            graph.g.nodes[pd_string_id]['data'] = new_name
            return True
        return False
    
    @staticmethod
    def remove_node(graph: ModelGraph, node_id: str) -> bool:
        """Remove node and all associated edges"""
        if node_id in graph.g.nodes:
            graph.g.remove_node(node_id)
            return True
        return False


class EdgeTransformations:
    """Edge-level transformations that preserve graph validity"""
    
    @staticmethod
    def add_hold_edge(graph: ModelGraph, perms: Permission, pd_id: int, 
                     res_type: ResourceType, space_id: int, res_id: Optional[int] = None,
                     pd_incharge: Optional[str] = None):
        """Add HOLD edge from PD to resource/resource space"""
        graph.add_hold_edge(perms, pd_id, res_type, space_id, res_id, pd_incharge)
    
    @staticmethod
    def add_inter_pd_hold_edge(graph: ModelGraph, perms: Permission, from_pd_id: int,
                              to_pd_id: int, pd_incharge: Optional[str] = None):
        """Add HOLD edge between PDs for signal relationships"""
        graph.add_inter_pd_hold_edge(perms, from_pd_id, to_pd_id, pd_incharge)
    
    @staticmethod
    def add_map_edge(graph: ModelGraph, res_type_1: ResourceType, res_type_2: ResourceType,
                    space_id_1: int, space_id_2: int, res_id_1: Optional[int] = None,
                    res_id_2: Optional[int] = None, pd_incharge: Optional[str] = None):
        """Add MAP edge between resources or resource spaces"""
        graph.add_map_edge(res_type_1, res_type_2, space_id_1, space_id_2, 
                          res_id_1, res_id_2, pd_incharge)
    
    @staticmethod
    def add_request_edge(graph: ModelGraph, source_pd_id: int, dest_pd_id: int,
                        res_type: ResourceType, space_id: int, pd_incharge: Optional[str] = None):
        """Add REQUEST edge from PD to PD for resource space"""
        graph.add_request_edge(source_pd_id, dest_pd_id, res_type, space_id, pd_incharge)
    
    @staticmethod
    def modify_edge_permissions(graph: ModelGraph, from_node: str, to_node: str, 
                               new_perms: Permission) -> bool:
        """Modify permissions on HOLD edges"""
        if graph.g.has_edge(from_node, to_node):
            for key, edge_data in graph.g[from_node][to_node].items():
                if edge_data.get('type') == EdgeType.HOLD.name:
                    edge_data['data'] = str(new_perms)
                    return True
        return False
    
    @staticmethod
    def modify_edge_controller(graph: ModelGraph, from_node: str, to_node: str,
                              new_pd_incharge: str) -> bool:
        """Modify pd_incharge field on edges"""
        if graph.g.has_edge(from_node, to_node):
            for key, edge_data in graph.g[from_node][to_node].items():
                extra = edge_data.get('extra', '{}')
                import json
                extra_dict = json.loads(extra) if extra else {}
                extra_dict['pd_incharge'] = new_pd_incharge
                edge_data['extra'] = json.dumps(extra_dict)
                return True
        return False
    
    @staticmethod
    def remove_edge(graph: ModelGraph, from_node: str, to_node: str, 
                   edge_type: Optional[EdgeType] = None) -> bool:
        """Remove specific edge between nodes"""
        if graph.g.has_edge(from_node, to_node):
            if edge_type is None:
                graph.g.remove_edge(from_node, to_node)
                return True
            else:
                edges_to_remove = []
                for key, edge_data in graph.g[from_node][to_node].items():
                    if edge_data.get('type') == edge_type.name:
                        edges_to_remove.append(key)
                
                for key in edges_to_remove:
                    graph.g.remove_edge(from_node, to_node, key)
                return len(edges_to_remove) > 0
        return False


class GraphValidator:
    """Validates graph transformations maintain OSmosis constraints"""
    
    @staticmethod
    def validate_node_types(graph: ModelGraph) -> bool:
        """Ensure all nodes have valid types"""
        valid_types = {nt.name for nt in NodeType}
        for node, data in graph.g.nodes(data=True):
            if data.get('type') not in valid_types:
                return False
        return True
    
    @staticmethod
    def validate_edge_types(graph: ModelGraph) -> bool:
        """Ensure all edges have valid types"""
        valid_types = {et.name for et in EdgeType}
        for _, _, data in graph.g.edges(data=True):
            if data.get('type') not in valid_types:
                return False
        return True
    
    @staticmethod
    def validate_resource_hierarchy(graph: ModelGraph) -> bool:
        """Ensure resources belong to exactly one resource space via SUBSET edges"""
        resource_nodes = [n for n, d in graph.g.nodes(data=True) 
                         if d.get('type') == NodeType.RESOURCE.name]
        
        for resource in resource_nodes:
            subset_edges = [e for e in graph.g.out_edges(resource, data=True)
                           if e[2].get('type') == EdgeType.SUBSET.name]
            if len(subset_edges) != 1:
                return False
        return True
    
    @staticmethod
    def validate_resource_space_consistency(graph: ModelGraph) -> bool:
        """Ensure resource types match their containing space types"""
        for node, data in graph.g.nodes(data=True):
            if data.get('type') == NodeType.RESOURCE.name:
                resource_type = data.get('data')
                
                # Find containing space via SUBSET edge
                subset_edges = [e for e in graph.g.out_edges(node, data=True)
                               if e[2].get('type') == EdgeType.SUBSET.name]
                
                if len(subset_edges) == 1:
                    space_node = subset_edges[0][1]
                    space_data = graph.g.nodes[space_node]
                    space_type = space_data.get('data')
                    
                    # Resource type should match space type
                    if resource_type != space_type:
                        return False
        return True
    
    @staticmethod
    def validate_id_uniqueness(graph: ModelGraph) -> bool:
        """Ensure node IDs follow naming conventions and are unique"""
        node_ids = set()
        for node in graph.g.nodes():
            if node in node_ids:
                return False
            node_ids.add(node)
            
            # Validate ID format
            if not (node.startswith('PD_') or 
                   '_SPACE_' in node or 
                   any(rt.name in node for rt in ResourceType)):
                return False
        return True
    
    @staticmethod
    def validate_graph(graph: ModelGraph) -> Dict[str, bool]:
        """Run all validation checks"""
        return {
            'node_types': GraphValidator.validate_node_types(graph),
            'edge_types': GraphValidator.validate_edge_types(graph),
            'resource_hierarchy': GraphValidator.validate_resource_hierarchy(graph),
            'resource_space_consistency': GraphValidator.validate_resource_space_consistency(graph),
            'id_uniqueness': GraphValidator.validate_id_uniqueness(graph)
        }


class TransformationSequence:
    """Apply sequences of transformations atomically"""
    
    def __init__(self):
        self.transformations = []
    
    def add_transformation(self, transform_func, *args, **kwargs):
        """Add transformation to sequence"""
        self.transformations.append((transform_func, args, kwargs))
    
    def apply_all(self, graph: ModelGraph) -> bool:
        """Apply all transformations. Rollback if any fail."""
        # Create backup of graph state
        import copy
        graph_backup = copy.deepcopy(graph.g)
        
        try:
            for transform_func, args, kwargs in self.transformations:
                result = transform_func(graph, *args, **kwargs)
                if result is False:
                    raise Exception("Transformation failed")
            
            # Validate final state
            validation = GraphValidator.validate_graph(graph)
            if not all(validation.values()):
                raise Exception(f"Validation failed: {validation}")
            
            return True
            
        except Exception:
            # Rollback on failure
            graph.g = graph_backup
            return False


# Example usage and utility functions
def create_basic_system_model() -> ModelGraph:
    """Create a basic system model with common components"""
    graph = ModelGraph()
    
    # Add kernel PD
    kernel_pd = NodeTransformations.add_pd_node(graph, "kernel")
    
    # Add user process PD  
    user_pd = NodeTransformations.add_pd_node(graph, "user_process")
    
    # Add memory spaces
    vmr_space = NodeTransformations.add_resource_space(graph, ResourceType.VMR)
    mo_space = NodeTransformations.add_resource_space(graph, ResourceType.MO)
    
    # Add some basic memory regions
    heap_vmr = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.HEAP, 10, 0x1000)
    stack_vmr = NodeTransformations.add_vmr_resource(graph, vmr_space, VmrType.STACK, 5, 0x7000)
    
    phys_mo = NodeTransformations.add_mo_resource(graph, mo_space, 0x100000, 15)
    
    # Add relationships
    EdgeTransformations.add_hold_edge(graph, Permission.R | Permission.W, 
                                    user_pd, ResourceType.VMR, vmr_space, heap_vmr, "kernel")
    EdgeTransformations.add_map_edge(graph, ResourceType.VMR, ResourceType.MO,
                                   vmr_space, mo_space, heap_vmr, phys_mo, "kernel")
    
    return graph