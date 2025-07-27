#!/usr/bin/env python3
"""
Parameterized BFS search queries for the OS resource model graph.
Supports both NetworkX (in-memory) and Neo4j (database) backends.
"""

from enum import Enum
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
import networkx as nx
from collections import deque
import json

# Neo4j imports (optional, for when using database backend)
try:
    from neo4j import Session
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    Session = None


class SearchDirection(Enum):
    """Direction for graph traversal"""
    OUTGOING = "outgoing"    # Follow edges in their natural direction
    INCOMING = "incoming"    # Follow edges in reverse direction  
    BOTH = "both"           # Follow edges in both directions


class NodeFilter(Enum):
    """Node type filters for search"""
    PD = "PD"
    RESOURCE = "RESOURCE" 
    RESOURCE_SPACE = "RESOURCE_SPACE"
    ALL = "ALL"


class EdgeFilter(Enum):
    """Edge type filters for search"""
    HOLD = "HOLD"
    MAP = "MAP"
    SUBSET = "SUBSET"
    REQUEST = "REQUEST"
    ALL = "ALL"


@dataclass
class BFSParams:
    """Parameters for BFS search"""
    start_nodes: List[str]                    # Starting node IDs
    max_depth: int = 3                        # Maximum search depth
    direction: SearchDirection = SearchDirection.OUTGOING
    node_filter: List[NodeFilter] = None      # Filter by node types
    edge_filter: List[EdgeFilter] = None      # Filter by edge types
    resource_type_filter: List[str] = None    # Filter by resource DATA field
    permission_filter: List[str] = None       # Filter by HOLD edge permissions
    stop_at_first: bool = False               # Stop at first match per path
    return_paths: bool = True                 # Return full paths vs just end nodes
    exclude_nodes: List[str] = None           # Nodes to exclude from search
    follow_transitive: bool = True            # Follow transitive relationships (SUBSET, etc.)
    
    def __post_init__(self):
        if self.node_filter is None:
            self.node_filter = [NodeFilter.ALL]
        if self.edge_filter is None:
            self.edge_filter = [EdgeFilter.ALL]
        if self.resource_type_filter is None:
            self.resource_type_filter = []
        if self.permission_filter is None:
            self.permission_filter = []
        if self.exclude_nodes is None:
            self.exclude_nodes = []


class NetworkXBFS:
    """BFS search implementation for NetworkX graphs"""
    
    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
    
    def search(self, params: BFSParams) -> Dict[str, Any]:
        """
        Perform parameterized BFS search on NetworkX graph
        
        Returns:
            Dict with 'paths' and 'nodes' keys containing search results
        """
        all_paths = []
        all_nodes = set()
        
        for start_node in params.start_nodes:
            if start_node not in self.graph:
                continue
                
            paths, nodes = self._bfs_from_node(start_node, params)
            all_paths.extend(paths)
            all_nodes.update(nodes)
        
        return {
            'paths': all_paths if params.return_paths else [],
            'nodes': list(all_nodes),
            'count': len(all_nodes)
        }
    
    def _bfs_from_node(self, start_node: str, params: BFSParams) -> Tuple[List, Set]:
        """BFS from a single starting node"""
        queue = deque([(start_node, [start_node], 0)])  # (current_node, path, depth)
        visited = set()
        paths = []
        result_nodes = set()
        
        while queue:
            current_node, path, depth = queue.popleft()
            
            if depth > params.max_depth:
                continue
            
            if current_node in visited and not params.return_paths:
                continue
            visited.add(current_node)
            
            # Check if current node matches our criteria
            if depth > 0 and self._node_matches_filter(current_node, params):
                result_nodes.add(current_node)
                if params.return_paths:
                    paths.append(path)
                if params.stop_at_first:
                    break
            
            # Get neighbors based on direction
            if params.follow_transitive:
                neighbors = self._get_transitive_neighbors(current_node, params)
            else:
                neighbors = self._get_neighbors(current_node, params)
            
            for neighbor, edge_data in neighbors:
                if neighbor in params.exclude_nodes:
                    continue
                if neighbor in path:  # Avoid cycles
                    continue
                if not self._edge_matches_filter(edge_data, params):
                    continue
                    
                new_path = path + [neighbor]
                queue.append((neighbor, new_path, depth + 1))
        
        return paths, result_nodes
    
    def _get_neighbors(self, node: str, params: BFSParams) -> List[Tuple[str, Dict]]:
        """Get neighbors based on search direction"""
        neighbors = []
        
        if params.direction in [SearchDirection.OUTGOING, SearchDirection.BOTH]:
            for neighbor in self.graph.successors(node):
                for edge_data in self.graph[node][neighbor].values():
                    neighbors.append((neighbor, edge_data))
        
        if params.direction in [SearchDirection.INCOMING, SearchDirection.BOTH]:
            for neighbor in self.graph.predecessors(node):
                for edge_data in self.graph[neighbor][node].values():
                    neighbors.append((neighbor, edge_data))
        
        return neighbors
    
    def _get_transitive_neighbors(self, node: str, params: BFSParams) -> List[Tuple[str, Dict]]:
        """Get neighbors through transitive relationships for OS resource model"""
        neighbors = []
        
        # Get direct neighbors first
        direct_neighbors = self._get_neighbors(node, params)
        neighbors.extend(direct_neighbors)
        
        # Handle special transitive relationships for OS resource model
        if params.direction in [SearchDirection.OUTGOING, SearchDirection.BOTH]:
            # If we're at a RESOURCE_SPACE, also find resources that are SUBSET of it
            node_data = self.graph.nodes.get(node, {})
            if node_data.get('type') == 'RESOURCE_SPACE':
                # Find all nodes that have SUBSET edges TO this resource space
                for pred in self.graph.predecessors(node):
                    for edge_data in self.graph[pred][node].values():
                        if edge_data.get('type') == 'SUBSET':
                            neighbors.append((pred, edge_data))
        
        if params.direction in [SearchDirection.INCOMING, SearchDirection.BOTH]:
            # If we're at a RESOURCE, also find the resource space it belongs to
            node_data = self.graph.nodes.get(node, {})
            if node_data.get('type') == 'RESOURCE':
                # Find RESOURCE_SPACE nodes that this resource is a SUBSET of
                for succ in self.graph.successors(node):
                    for edge_data in self.graph[node][succ].values():
                        if edge_data.get('type') == 'SUBSET':
                            neighbors.append((succ, edge_data))
        
        return neighbors
    
    def _node_matches_filter(self, node: str, params: BFSParams) -> bool:
        """Check if node matches the search filters"""
        if NodeFilter.ALL not in params.node_filter:
            node_data = self.graph.nodes[node]
            node_type = node_data.get('type', '')
            if not any(filter_type.value == node_type for filter_type in params.node_filter):
                return False
        
        # Resource type filter
        if params.resource_type_filter:
            node_data = self.graph.nodes[node]
            resource_type = node_data.get('data', '')
            if resource_type not in params.resource_type_filter:
                return False
        
        return True
    
    def _edge_matches_filter(self, edge_data: Dict, params: BFSParams) -> bool:
        """Check if edge matches the search filters"""
        if EdgeFilter.ALL not in params.edge_filter:
            edge_type = edge_data.get('type', '')
            if not any(filter_type.value == edge_type for filter_type in params.edge_filter):
                return False
        
        # Permission filter for HOLD edges
        if params.permission_filter and edge_data.get('type') == 'HOLD':
            edge_perms = edge_data.get('data', '')
            if not any(perm in edge_perms for perm in params.permission_filter):
                return False
        
        return True


class Neo4jBFS:
    """BFS search implementation for Neo4j database"""
    
    def __init__(self, session: Session):
        if not NEO4J_AVAILABLE:
            raise ImportError("neo4j package not available")
        self.session = session
    
    def search(self, params: BFSParams) -> Dict[str, Any]:
        """
        Perform parameterized BFS search using Neo4j Cypher
        
        Returns:
            Dict with 'paths' and 'nodes' keys containing search results
        """
        # Build the Cypher query
        query = self._build_cypher_query(params)
        
        # Execute query with parameters
        cypher_params = {
            'start_nodes': params.start_nodes,
            'max_depth': params.max_depth,
            'resource_types': params.resource_type_filter,
            'permissions': params.permission_filter,
            'exclude_nodes': params.exclude_nodes
        }
        
        result = self.session.run(query, **cypher_params)
        
        # Process results
        paths = []
        nodes = set()
        
        for record in result:
            if params.return_paths and 'path' in record:
                path_nodes = [node['ID'] for node in record['path']]
                paths.append(path_nodes)
            if 'node' in record:
                nodes.add(record['node']['ID'])
        
        return {
            'paths': paths,
            'nodes': list(nodes),
            'count': len(nodes)
        }
    
    def _build_cypher_query(self, params: BFSParams) -> str:
        """Build parameterized Cypher query for BFS"""
        
        # Node type filter
        node_filter_clause = ""
        if NodeFilter.ALL not in params.node_filter:
            node_types = [f.value for f in params.node_filter]
            node_filter_clause = f"AND n.type IN {node_types}"
        
        # Edge type filter  
        edge_types = []
        if EdgeFilter.ALL not in params.edge_filter:
            edge_types = [f.value for f in params.edge_filter]
            relationship_filter = "|".join(edge_types)
        else:
            relationship_filter = "HOLD|MAP|SUBSET|REQUEST"
        
        # Direction
        direction_map = {
            SearchDirection.OUTGOING: ">",
            SearchDirection.INCOMING: "<",
            SearchDirection.BOTH: ""
        }
        direction_symbol = direction_map[params.direction]
        
        # Resource type filter
        resource_filter_clause = ""
        if params.resource_type_filter:
            resource_filter_clause = "AND n.DATA IN $resource_types"
        
        # Permission filter (for HOLD edges)
        permission_filter_clause = ""
        if params.permission_filter:
            permission_filter_clause = """
            AND ALL(rel IN relationships(path) WHERE 
                rel.type <> 'HOLD' OR 
                ANY(perm IN $permissions WHERE rel.DATA CONTAINS perm)
            )
            """
        
        # Exclude nodes filter
        exclude_filter_clause = ""
        if params.exclude_nodes:
            exclude_filter_clause = "AND NOT n.ID IN $exclude_nodes"
        
        query = f"""
        UNWIND $start_nodes AS start_id
        MATCH (start {{ID: start_id}})
        CALL apoc.path.expandConfig(start, {{
            relationshipFilter: "{relationship_filter}",
            maxLevel: $max_depth,
            algorithm: "BFS"
        }})
        YIELD path
        WITH path, nodes(path) AS path_nodes
        UNWIND path_nodes AS n
        WHERE n.ID <> start_id 
        {node_filter_clause}
        {resource_filter_clause}
        {exclude_filter_clause}
        {permission_filter_clause}
        """
        
        if params.return_paths:
            query += "RETURN DISTINCT path, n AS node"
        else:
            query += "RETURN DISTINCT n AS node"
        
        return query


# Convenience functions for common search patterns

def find_accessible_resources(graph_or_session, pd_id: str, resource_type: str = None, 
                            max_depth: int = 3) -> Dict[str, Any]:
    """Find all resources accessible from a PD"""
    params = BFSParams(
        start_nodes=[pd_id],
        max_depth=max_depth,
        direction=SearchDirection.OUTGOING,
        node_filter=[NodeFilter.RESOURCE],
        edge_filter=[EdgeFilter.HOLD, EdgeFilter.MAP, EdgeFilter.SUBSET],  # Include SUBSET for transitive search
        resource_type_filter=[resource_type] if resource_type else [],
        follow_transitive=True  # Enable transitive search
    )
    
    if isinstance(graph_or_session, nx.MultiDiGraph):
        searcher = NetworkXBFS(graph_or_session)
    else:
        searcher = Neo4jBFS(graph_or_session)
    
    return searcher.search(params)

def find_resource_holders(graph_or_session, resource_id: str, max_depth: int = 2) -> Dict[str, Any]:
    """Find all PDs that can access a specific resource"""
    params = BFSParams(
        start_nodes=[resource_id],
        max_depth=max_depth,
        direction=SearchDirection.INCOMING,
        node_filter=[NodeFilter.PD],
        edge_filter=[EdgeFilter.HOLD, EdgeFilter.MAP]
    )
    
    if isinstance(graph_or_session, nx.MultiDiGraph):
        searcher = NetworkXBFS(graph_or_session)
    else:
        searcher = Neo4jBFS(graph_or_session)
    
    return searcher.search(params)

def find_shared_resources(graph_or_session, pd1: str, pd2: str, resource_type: str = None,
                         max_depth: int = 3) -> Dict[str, Any]:
    """Find resources shared between two PDs"""
    # Get resources accessible from both PDs
    resources1 = find_accessible_resources(graph_or_session, pd1, resource_type, max_depth)
    resources2 = find_accessible_resources(graph_or_session, pd2, resource_type, max_depth)
    
    # Find intersection
    shared = set(resources1['nodes']) & set(resources2['nodes'])
    
    return {
        'paths': [],
        'nodes': list(shared),
        'count': len(shared)
    }

def find_authority_chain(graph_or_session, start_pd: str, target_pd: str, 
                        max_depth: int = 4) -> Dict[str, Any]:
    """Find authority/request chains between PDs"""
    params = BFSParams(
        start_nodes=[start_pd],
        max_depth=max_depth,
        direction=SearchDirection.OUTGOING,
        node_filter=[NodeFilter.PD],
        edge_filter=[EdgeFilter.REQUEST, EdgeFilter.HOLD],
        return_paths=True,
        exclude_nodes=[start_pd]
    )
    
    if isinstance(graph_or_session, nx.MultiDiGraph):
        searcher = NetworkXBFS(graph_or_session)
    else:
        searcher = Neo4jBFS(graph_or_session)
    
    result = searcher.search(params)
    
    # Filter paths that end at target_pd
    target_paths = [path for path in result['paths'] if path[-1] == target_pd]
    
    return {
        'paths': target_paths,
        'nodes': [target_pd] if target_paths else [],
        'count': len(target_paths)
    }


if __name__ == "__main__":
    # Example usage
    print("Parameterized BFS Search for OS Resource Model")
    print("="*50)
    
    # Example with NetworkX graph (would need actual graph instance)
    # graph = load_model_graph()  # Your graph loading function
    # result = find_accessible_resources(graph, "PD_1", "VMR", max_depth=2)
    # print(f"Found {result['count']} accessible VMR resources")
    
    # Example with Neo4j session (would need actual session)
    # session = establish_session("neo4j")  # Your session function  
    # result = find_shared_resources(session, "PD_1", "PD_2", "MO")
    # print(f"Found {result['count']} shared MO resources")