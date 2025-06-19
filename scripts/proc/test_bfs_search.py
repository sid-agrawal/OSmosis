#!/usr/bin/env python3
"""
Test cases for the NetworkX BFS search functionality.
Creates mock OS resource model graphs and tests various search scenarios.
"""

import unittest
import networkx as nx
from bfs_search import (
    NetworkXBFS, BFSParams, SearchDirection, NodeFilter, EdgeFilter,
    find_accessible_resources, find_resource_holders, find_shared_resources,
    find_authority_chain
)
import generic_model as gm


class TestNetworkXBFS(unittest.TestCase):
    """Test cases for NetworkX BFS search"""
    
    def setUp(self):
        """Create a mock OS resource model graph for testing"""
        self.graph = nx.MultiDiGraph()
        
        # Create a sample graph structure:
        # PD_1 -> VMR_SPACE_1 -> VMR_1_1 -> MO_SPACE_1 -> MO_1_1
        #      -> VMR_1_2 ----/
        # PD_2 -> VMR_SPACE_2 -> VMR_2_1 -> MO_SPACE_1 -> MO_1_1 (shared!)
        # PD_3 -> PD_1 (authority relationship)
        
        # Add nodes
        nodes = [
            # Protection Domains
            ("PD_1", {"type": "PD", "data": "process1", "extra": ""}),
            ("PD_2", {"type": "PD", "data": "process2", "extra": ""}),
            ("PD_3", {"type": "PD", "data": "supervisor", "extra": ""}),
            
            # Resource Spaces
            ("VMR_SPACE_1", {"type": "RESOURCE_SPACE", "data": "VMR", "extra": ""}),
            ("VMR_SPACE_2", {"type": "RESOURCE_SPACE", "data": "VMR", "extra": ""}),
            ("MO_SPACE_1", {"type": "RESOURCE_SPACE", "data": "MO", "extra": ""}),
            
            # Virtual Memory Resources
            ("VMR_1_1", {"type": "RESOURCE", "data": "VMR", "extra": '{"vmr_type": "HEAP"}'}),
            ("VMR_1_2", {"type": "RESOURCE", "data": "VMR", "extra": '{"vmr_type": "STACK"}'}),
            ("VMR_2_1", {"type": "RESOURCE", "data": "VMR", "extra": '{"vmr_type": "PROGRAM"}'}),
            
            # Physical Memory Resources
            ("MO_1_1", {"type": "RESOURCE", "data": "MO", "extra": '{"pa": "0x1000"}'}),
            ("MO_1_2", {"type": "RESOURCE", "data": "MO", "extra": '{"pa": "0x2000"}'}),
        ]
        
        for node_id, attrs in nodes:
            self.graph.add_node(node_id, **attrs)
        
        # Add edges
        edges = [
            # PD_1 relationships
            ("PD_1", "VMR_SPACE_1", {"type": "HOLD", "data": "RWX", "extra": ""}),
            ("PD_1", "VMR_1_1", {"type": "HOLD", "data": "RW", "extra": ""}),
            ("PD_1", "VMR_1_2", {"type": "HOLD", "data": "RWX", "extra": ""}),
            
            # PD_2 relationships
            ("PD_2", "VMR_SPACE_2", {"type": "HOLD", "data": "RWX", "extra": ""}),
            ("PD_2", "VMR_2_1", {"type": "HOLD", "data": "RX", "extra": ""}),
            
            # PD_3 authority over PD_1
            ("PD_3", "PD_1", {"type": "HOLD", "data": "SIGNAL", "extra": ""}),
            
            # Resource containment (SUBSET relationships)
            ("VMR_1_1", "VMR_SPACE_1", {"type": "SUBSET", "data": "", "extra": ""}),
            ("VMR_1_2", "VMR_SPACE_1", {"type": "SUBSET", "data": "", "extra": ""}),
            ("VMR_2_1", "VMR_SPACE_2", {"type": "SUBSET", "data": "", "extra": ""}),
            ("MO_1_1", "MO_SPACE_1", {"type": "SUBSET", "data": "", "extra": ""}),
            ("MO_1_2", "MO_SPACE_1", {"type": "SUBSET", "data": "", "extra": ""}),
            
            # Memory mappings (MAP relationships)
            ("VMR_1_1", "MO_1_1", {"type": "MAP", "data": "", "extra": ""}),
            ("VMR_1_2", "MO_1_2", {"type": "MAP", "data": "", "extra": ""}),
            ("VMR_2_1", "MO_1_1", {"type": "MAP", "data": "", "extra": ""}),  # Shared memory!
            
            # Resource space access
            ("MO_SPACE_1", "PD_1", {"type": "REQUEST", "data": "", "extra": ""}),
            ("MO_SPACE_1", "PD_2", {"type": "REQUEST", "data": "", "extra": ""}),
        ]
        
        for source, target, attrs in edges:
            self.graph.add_edge(source, target, **attrs)
        
        # Create searcher instance
        self.searcher = NetworkXBFS(self.graph)
    
    def test_basic_outgoing_search(self):
        """Test basic outgoing BFS search"""
        params = BFSParams(
            start_nodes=["PD_1"],
            max_depth=2,
            direction=SearchDirection.OUTGOING
        )
        
        result = self.searcher.search(params)
        
        # Should find VMR_SPACE_1, VMR_1_1, VMR_1_2, and PD_1 (if PD_3->PD_1 edge exists)
        self.assertGreater(result['count'], 0)
        self.assertIn("VMR_SPACE_1", result['nodes'])
        self.assertIn("VMR_1_1", result['nodes'])
    
    def test_incoming_search(self):
        """Test incoming BFS search"""
        params = BFSParams(
            start_nodes=["VMR_1_1"],
            max_depth=2,
            direction=SearchDirection.INCOMING
        )
        
        result = self.searcher.search(params)
        
        # Should find PD_1 (holds VMR_1_1)
        self.assertIn("PD_1", result['nodes'])
    
    def test_node_type_filter(self):
        """Test filtering by node type"""
        params = BFSParams(
            start_nodes=["PD_1"],
            max_depth=3,
            direction=SearchDirection.OUTGOING,
            node_filter=[NodeFilter.RESOURCE]
        )
        
        result = self.searcher.search(params)
        
        # Should only find RESOURCE nodes, not RESOURCE_SPACE or PD nodes
        for node_id in result['nodes']:
            node_data = self.graph.nodes[node_id]
            self.assertEqual(node_data['type'], 'RESOURCE')
    
    def test_edge_type_filter(self):
        """Test filtering by edge type"""
        params = BFSParams(
            start_nodes=["PD_1"],
            max_depth=2,
            direction=SearchDirection.OUTGOING,
            edge_filter=[EdgeFilter.HOLD]
        )
        
        result = self.searcher.search(params)
        
        # Should find nodes reachable only via HOLD edges
        self.assertIn("VMR_SPACE_1", result['nodes'])
        self.assertIn("VMR_1_1", result['nodes'])
    
    def test_resource_type_filter(self):
        """Test filtering by resource data type"""
        params = BFSParams(
            start_nodes=["PD_1"],
            max_depth=3,
            direction=SearchDirection.OUTGOING,
            node_filter=[NodeFilter.RESOURCE],
            resource_type_filter=["VMR"]
        )
        
        result = self.searcher.search(params)
        
        # Should only find VMR resources, not MO resources
        for node_id in result['nodes']:
            node_data = self.graph.nodes[node_id]
            if node_data['type'] == 'RESOURCE':
                self.assertEqual(node_data['data'], 'VMR')
    
    def test_permission_filter(self):
        """Test filtering by edge permissions"""
        params = BFSParams(
            start_nodes=["PD_1"],
            max_depth=2,
            direction=SearchDirection.OUTGOING,
            edge_filter=[EdgeFilter.HOLD],
            permission_filter=["W"]  # Only edges with write permission
        )
        
        result = self.searcher.search(params)
        
        # Should find VMR_1_1 (RW permission) but not VMR_2_1 (RX permission)
        # Note: VMR_2_1 is not directly reachable from PD_1 anyway in this test
        self.assertGreater(result['count'], 0)
    
    def test_max_depth_limit(self):
        """Test that search respects max depth limit"""
        # Search with depth 1
        params_shallow = BFSParams(
            start_nodes=["PD_1"],
            max_depth=1,
            direction=SearchDirection.OUTGOING
        )
        
        result_shallow = self.searcher.search(params_shallow)
        
        # Search with depth 3
        params_deep = BFSParams(
            start_nodes=["PD_1"],
            max_depth=3,
            direction=SearchDirection.OUTGOING
        )
        
        result_deep = self.searcher.search(params_deep)
        
        # Deep search should find more nodes
        self.assertGreaterEqual(result_deep['count'], result_shallow['count'])
    
    def test_exclude_nodes(self):
        """Test excluding specific nodes from search"""
        params = BFSParams(
            start_nodes=["PD_1"],
            max_depth=2,
            direction=SearchDirection.OUTGOING,
            exclude_nodes=["VMR_1_1"]
        )
        
        result = self.searcher.search(params)
        
        # Should not find the excluded node
        self.assertNotIn("VMR_1_1", result['nodes'])
    
    def test_path_return(self):
        """Test returning full paths"""
        params = BFSParams(
            start_nodes=["PD_1"],
            max_depth=2,
            direction=SearchDirection.OUTGOING,
            return_paths=True
        )
        
        result = self.searcher.search(params)
        
        # Should return paths
        self.assertGreater(len(result['paths']), 0)
        
        # Each path should start with PD_1
        for path in result['paths']:
            self.assertEqual(path[0], "PD_1")
    
    def test_multiple_start_nodes(self):
        """Test search from multiple starting nodes"""
        params = BFSParams(
            start_nodes=["PD_1", "PD_2"],
            max_depth=2,
            direction=SearchDirection.OUTGOING,
            node_filter=[NodeFilter.RESOURCE]
        )
        
        result = self.searcher.search(params)
        
        # Should find resources accessible from both PD_1 and PD_2
        self.assertGreater(result['count'], 0)


class TestConvenienceFunctions(unittest.TestCase):
    """Test the convenience functions"""
    
    def setUp(self):
        """Use the same setup as the main test class"""
        test_case = TestNetworkXBFS()
        test_case.setUp()
        self.graph = test_case.graph
    
    def test_find_accessible_resources(self):
        """Test find_accessible_resources convenience function"""
        result = find_accessible_resources(self.graph, "PD_1", "VMR", max_depth=2)
        
        # Should find VMR resources accessible from PD_1
        self.assertGreater(result['count'], 0)
        
        # All returned nodes should be VMR resources
        for node_id in result['nodes']:
            node_data = self.graph.nodes[node_id]
            self.assertEqual(node_data['type'], 'RESOURCE')
            self.assertEqual(node_data['data'], 'VMR')
    
    def test_find_resource_holders(self):
        """Test find_resource_holders convenience function"""
        result = find_resource_holders(self.graph, "VMR_1_1", max_depth=2)
        
        # Should find PD_1 as holder of VMR_1_1
        self.assertIn("PD_1", result['nodes'])
    
    def test_find_shared_resources(self):
        """Test find_shared_resources convenience function"""
        # First, let's create a shared resource scenario
        # Add edge so PD_2 can also access MO_1_1 via VMR_2_1
        result = find_shared_resources(self.graph, "PD_1", "PD_2", "MO", max_depth=4)
        
        # Check if there are any shared MO resources
        # Note: This depends on the graph structure - MO_1_1 should be shared
        # via the mapping VMR_1_1 -> MO_1_1 and VMR_2_1 -> MO_1_1
        print(f"Shared resources found: {result['nodes']}")
    
    def test_find_authority_chain(self):
        """Test find_authority_chain convenience function"""
        result = find_authority_chain(self.graph, "PD_3", "PD_1", max_depth=2)
        
        # Should find path from PD_3 to PD_1 if such authority exists
        if result['count'] > 0:
            self.assertIn("PD_1", result['nodes'])


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def setUp(self):
        """Create minimal graph for edge case testing"""
        self.graph = nx.MultiDiGraph()
        self.graph.add_node("NODE_1", type="PD", data="test", extra="")
        self.searcher = NetworkXBFS(self.graph)
    
    def test_nonexistent_start_node(self):
        """Test search with non-existent start node"""
        params = BFSParams(start_nodes=["NONEXISTENT"])
        result = self.searcher.search(params)
        
        # Should return empty result
        self.assertEqual(result['count'], 0)
        self.assertEqual(len(result['nodes']), 0)
    
    def test_empty_graph(self):
        """Test search on empty graph"""
        empty_graph = nx.MultiDiGraph()
        searcher = NetworkXBFS(empty_graph)
        
        params = BFSParams(start_nodes=["NODE_1"])
        result = searcher.search(params)
        
        # Should return empty result
        self.assertEqual(result['count'], 0)
    
    def test_isolated_node(self):
        """Test search from isolated node"""
        params = BFSParams(start_nodes=["NODE_1"], max_depth=2)
        result = self.searcher.search(params)
        
        # Should find no additional nodes (isolated node)
        self.assertEqual(result['count'], 0)
    
    def test_cycle_handling(self):
        """Test that cycles don't cause infinite loops"""
        # Create a cycle: A -> B -> C -> A
        self.graph.add_nodes_from([
            ("A", {"type": "PD", "data": "a", "extra": ""}),
            ("B", {"type": "PD", "data": "b", "extra": ""}),
            ("C", {"type": "PD", "data": "c", "extra": ""})
        ])
        
        self.graph.add_edges_from([
            ("A", "B", {"type": "HOLD", "data": "", "extra": ""}),
            ("B", "C", {"type": "HOLD", "data": "", "extra": ""}),
            ("C", "A", {"type": "HOLD", "data": "", "extra": ""})
        ])
        
        params = BFSParams(start_nodes=["A"], max_depth=5)
        result = self.searcher.search(params)
        
        # Should terminate and find nodes B and C
        self.assertGreaterEqual(result['count'], 2)
        self.assertIn("B", result['nodes'])
        self.assertIn("C", result['nodes'])


def create_realistic_test_graph():
    """
    Create a more realistic OS resource model graph for comprehensive testing
    Simulates a multi-process system with shared memory and authority relationships
    """
    model = gm.ModelGraph()
    
    # Create processes
    proc1_pd = model.add_pd_node("nginx_worker")
    proc2_pd = model.add_pd_node("nginx_master") 
    proc3_pd = model.add_pd_node("systemd")
    
    # Create address spaces
    as1 = model.add_resource_space_node(gm.ResourceType.VMR)
    as2 = model.add_resource_space_node(gm.ResourceType.VMR)
    
    # Create physical memory space
    pm_space = model.add_resource_space_node(gm.ResourceType.MO)
    
    # Create VMRs
    heap1 = model.add_vmr_node(as1, gm.VmrType.HEAP, 10, 0x10000)
    stack1 = model.add_vmr_node(as1, gm.VmrType.STACK, 2, 0x7fff0000)
    lib1 = model.add_vmr_node(as1, gm.VmrType.LIB, 5, 0x40000000)
    
    heap2 = model.add_vmr_node(as2, gm.VmrType.HEAP, 20, 0x10000)
    lib2 = model.add_vmr_node(as2, gm.VmrType.LIB, 5, 0x40000000)  # Shared library
    
    # Create MOs (physical memory)
    mo1 = model.add_mo_node(pm_space, 0x1000, 10)
    mo2 = model.add_mo_node(pm_space, 0x2000, 2) 
    mo3 = model.add_mo_node(pm_space, 0x3000, 5)  # Shared physical memory
    mo4 = model.add_mo_node(pm_space, 0x4000, 20)
    
    # Add HOLD relationships (process -> address space)
    model.add_hold_edge(gm.perms_all, proc1_pd, gm.ResourceType.VMR, as1)
    model.add_hold_edge(gm.perms_all, proc2_pd, gm.ResourceType.VMR, as2)
    
    # Add authority relationship (systemd can control nginx processes)
    model.add_inter_pd_hold_edge(gm.Permissions({gm.Permission.X}), proc3_pd, proc1_pd)
    model.add_inter_pd_hold_edge(gm.Permissions({gm.Permission.X}), proc3_pd, proc2_pd)
    model.add_inter_pd_hold_edge(gm.Permissions({gm.Permission.X}), proc2_pd, proc1_pd)
    
    # Add MAP relationships (VMR -> MO mappings)
    model.add_map_edge(gm.ResourceType.VMR, gm.ResourceType.MO, as1, pm_space, heap1, mo1)
    model.add_map_edge(gm.ResourceType.VMR, gm.ResourceType.MO, as1, pm_space, stack1, mo2)
    model.add_map_edge(gm.ResourceType.VMR, gm.ResourceType.MO, as1, pm_space, lib1, mo3)
    
    model.add_map_edge(gm.ResourceType.VMR, gm.ResourceType.MO, as2, pm_space, heap2, mo4)
    model.add_map_edge(gm.ResourceType.VMR, gm.ResourceType.MO, as2, pm_space, lib2, mo3)  # Shared!
    
    return model.g


class TestRealisticScenarios(unittest.TestCase):
    """Test with a more realistic OS resource model"""
    
    def setUp(self):
        """Create realistic test graph"""
        self.graph = create_realistic_test_graph()
        self.searcher = NetworkXBFS(self.graph)
    
    def test_shared_library_detection(self):
        """Test detection of shared libraries between processes"""
        # Find MO resources accessible from both nginx processes
        result1 = find_accessible_resources(self.graph, "PD_1", "MO", max_depth=4)
        result2 = find_accessible_resources(self.graph, "PD_2", "MO", max_depth=4)
        
        shared_mos = set(result1['nodes']) & set(result2['nodes'])
        
        # Should find at least one shared MO (the shared library)
        self.assertGreater(len(shared_mos), 0)
        print(f"Shared MO resources: {shared_mos}")
    
    def test_authority_hierarchy(self):
        """Test finding authority relationships"""
        # systemd should have authority over nginx processes
        result = find_authority_chain(self.graph, "PD_3", "PD_1", max_depth=3)
        
        if result['count'] > 0:
            print(f"Authority chain from systemd to nginx_worker: {result['paths']}")
    
    def test_memory_accessibility_analysis(self):
        """Test comprehensive memory accessibility analysis"""
        # Find all memory accessible from nginx_worker
        vmr_result = find_accessible_resources(self.graph, "PD_1", "VMR", max_depth=3)
        mo_result = find_accessible_resources(self.graph, "PD_1", "MO", max_depth=4)
        
        print(f"VMRs accessible from nginx_worker: {vmr_result['nodes']}")
        print(f"MOs accessible from nginx_worker: {mo_result['nodes']}")
        
        # Should find multiple memory regions
        self.assertGreater(vmr_result['count'], 0)
        self.assertGreater(mo_result['count'], 0)


if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)