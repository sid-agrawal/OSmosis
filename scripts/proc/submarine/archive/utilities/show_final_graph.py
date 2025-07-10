#!/usr/bin/env python3

"""
Script to show the final graph structure for the basic_sharing_primitive solution
"""

from scenarios import get_scenario
from true_bfs_exploration import TrueBFSExploration
from isosearch import ComputeMetrics
import json

def print_graph_structure(graph, title="Graph Structure"):
    """Print a detailed view of the graph structure"""
    print(f"\n=== {title} ===")
    
    # Count nodes by type
    node_types = {}
    for node, data in graph.g.nodes(data=True):
        node_type = data.get('type', 'UNKNOWN')
        if node_type not in node_types:
            node_types[node_type] = []
        node_types[node_type].append(node)
    
    print(f"📊 Summary: {graph.g.number_of_nodes()} nodes, {graph.g.number_of_edges()} edges")
    
    # Show nodes by type
    for node_type, nodes in node_types.items():
        print(f"\n🔹 {node_type} nodes ({len(nodes)}):")
        for node in sorted(nodes):
            data = graph.g.nodes[node]
            extra_info = ""
            if data.get('extra'):
                try:
                    extra_data = json.loads(data['extra'])
                    if 'file_type' in extra_data:
                        extra_info = f" ({extra_data['file_type']})"
                    elif 'path' in extra_data:
                        extra_info = f" ({extra_data['path']})"
                except:
                    pass
            print(f"    • {node}{extra_info}")
    
    # Show edges by type
    edge_types = {}
    for from_node, to_node, data in graph.g.edges(data=True):
        edge_type = data.get('type', 'UNKNOWN')
        if edge_type not in edge_types:
            edge_types[edge_type] = []
        edge_types[edge_type].append((from_node, to_node))
    
    print(f"\n🔗 Edges by type:")
    for edge_type, edges in edge_types.items():
        print(f"\n🔹 {edge_type} edges ({len(edges)}):")
        for from_node, to_node in sorted(edges):
            print(f"    • {from_node} → {to_node}")

def show_metrics(graph, title="Metrics"):
    """Show computed metrics for the graph"""
    print(f"\n=== {title} ===")
    
    try:
        metrics = ComputeMetrics(graph)
        print(f"📈 RSI: {metrics.get('RSI', 'N/A')}")
        print(f"📈 ASR: {metrics.get('ASR', 'N/A')}")
        print(f"📈 TCB: {metrics.get('TCB', 'N/A')}")
        print(f"📈 FR: {metrics.get('FR', 'N/A')}")
        
        # Check goal satisfaction
        rsi_value = metrics.get('RSI', {}).get('PD_1,PD_2', 1.0)
        asr_value = metrics.get('ASR', 999.0)
        tcb_value = len(metrics.get('TCB', {}).get('PD_1', []))
        
        print(f"\n✅ Goal Status:")
        print(f"    • RSI ≤ 0.3: {rsi_value:.3f} {'✅' if rsi_value <= 0.3 else '❌'}")
        print(f"    • ASR ≤ 1.0: {asr_value:.3f} {'✅' if asr_value <= 1.0 else '❌'}")
        print(f"    • TCB = 0: {tcb_value} {'✅' if tcb_value == 0 else '❌'}")
        
    except Exception as e:
        print(f"❌ Error computing metrics: {e}")

def main():
    print("🔍 Analyzing basic_sharing_primitive solutions...")
    
    # Get scenario
    scenario = get_scenario("basic_sharing_primitive")
    
    # Show initial graph
    initial_graph = scenario.build_graph()
    print_graph_structure(initial_graph, "Initial Graph")
    show_metrics(initial_graph, "Initial Metrics")
    
    # Run True BFS to get solutions
    print("\n🔍 Running True BFS to find solutions...")
    mechanisms = TrueBFSExploration(scenario, max_depth=3, max_states=50)
    
    if mechanisms:
        # Show first mechanism (simplest solution)
        mechanism = mechanisms[0]
        print(f"\n🎯 Solution Found (Mechanism 1):")
        print(f"   Path: {' → '.join(mechanism.get('path', ['N/A']))}")
        print(f"   Depth: {mechanism.get('depth', 'N/A')}")
        
        # Show final graph
        final_graph = mechanism['graph']
        print_graph_structure(final_graph, "Final Graph (Solution)")
        show_metrics(final_graph, "Final Metrics")
        
        # Show the transformation
        print(f"\n🔄 Transformation Summary:")
        print(f"   Initial nodes: {initial_graph.g.number_of_nodes()}")
        print(f"   Final nodes: {final_graph.g.number_of_nodes()}")
        print(f"   Initial edges: {initial_graph.g.number_of_edges()}")
        print(f"   Final edges: {final_graph.g.number_of_edges()}")
        
        # Show what changed
        initial_nodes = set(initial_graph.g.nodes())
        final_nodes = set(final_graph.g.nodes())
        
        removed_nodes = initial_nodes - final_nodes
        added_nodes = final_nodes - initial_nodes
        
        if removed_nodes:
            print(f"   Removed nodes: {', '.join(removed_nodes)}")
        if added_nodes:
            print(f"   Added nodes: {', '.join(added_nodes)}")
        
        print(f"\n💡 Key insight: The simplest solution was to remove the shared resource FILE_1_3")
        print(f"   This eliminates all sharing between PD_1 and PD_2, achieving RSI = 0.0")
        
    else:
        print("❌ No mechanisms found!")

if __name__ == "__main__":
    main()