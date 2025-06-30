"""
Decision Tree Visualization for IsoSearch Algorithm
Creates a static HTML page showing the exploration as a tree of OSmosis graph states
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any

class DecisionTreeVisualizer:
    """Creates decision tree visualizations for IsoSearch algorithm exploration"""
    
    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
        self.tree_nodes = []
        self.decision_paths = []
        self.start_time = datetime.now()
        
    def add_decision_node(self, iteration: int, graph_data: Dict, metrics: Dict, 
                         candidates: List[Dict], selected_candidate: Dict = None,
                         parent_id: str = None, is_selected: bool = True):
        """Add a decision node to the tree"""
        node_id = f"iter_{iteration}_{('selected' if is_selected else 'discarded')}"
        
        node_data = {
            'id': node_id,
            'iteration': iteration,
            'parent_id': parent_id,
            'is_selected': is_selected,
            'graph': self._serialize_graph(graph_data),
            'metrics': metrics,
            'candidates': candidates,
            'selected_candidate': selected_candidate,
            'timestamp': datetime.now().isoformat()
        }
        self.tree_nodes.append(node_data)
        return node_id
        
    def add_discarded_paths(self, iteration: int, base_graph: Dict, discarded_candidates: List[Dict]):
        """Add discarded candidate paths as tree branches"""
        for i, candidate in enumerate(discarded_candidates):
            # Simulate what the graph would look like after this transformation
            simulated_graph = self._simulate_transformation(base_graph, candidate)
            simulated_metrics = {'simulated': True, 'candidate': candidate}
            
            discarded_id = f"iter_{iteration}_discarded_{i}"
            self.tree_nodes.append({
                'id': discarded_id,
                'iteration': iteration,
                'parent_id': f"iter_{iteration}_selected",
                'is_selected': False,
                'is_discarded': True,
                'graph': self._serialize_graph(simulated_graph) if simulated_graph else None,
                'metrics': simulated_metrics,
                'candidate_info': candidate,
                'timestamp': datetime.now().isoformat()
            })
    
    def _simulate_transformation(self, base_graph: Dict, candidate: Dict) -> Dict:
        """Simulate what graph would look like after transformation (simplified)"""
        # For now, return None - in full implementation would apply transformation
        # This would require importing the transformation logic
        return None
        
    def _serialize_graph(self, graph) -> Dict:
        """Convert graph to JSON-serializable format"""
        if graph is None:
            return {'nodes': [], 'edges': []}
            
        nodes = []
        edges = []
        
        # Extract nodes
        for node_id, node_data in graph.g.nodes(data=True):
            nodes.append({
                'id': node_id,
                'type': node_data.get('type', 'unknown'),
                'data': node_data.get('data', ''),
                'extra': node_data.get('extra', ''),
                'label': self._format_node_label(node_id, node_data)
            })
            
        # Extract edges
        for source, target, edge_data in graph.g.edges(data=True):
            edges.append({
                'source': source,
                'target': target,
                'type': edge_data.get('type', 'unknown'),
                'permission': edge_data.get('permission', ''),
                'label': self._format_edge_label(edge_data)
            })
            
        return {'nodes': nodes, 'edges': edges}
        
    def _format_node_label(self, node_id: str, node_data: Dict) -> str:
        """Create readable label for node"""
        node_type = node_data.get('type', '')
        if node_type == 'PD':
            return f"{node_id}\n({node_data.get('data', '')})"
        elif node_type == 'RESOURCE':
            extra = node_data.get('extra', '')
            if extra:
                try:
                    extra_data = json.loads(extra) if isinstance(extra, str) else extra
                    vmr_type = extra_data.get('vmr_type', '')
                    va = extra_data.get('va', '')
                    return f"{node_id}\n{vmr_type} @ {va}"
                except:
                    pass
            return f"{node_id}\n{node_data.get('data', '')}"
        else:
            return f"{node_id}\n{node_type}"
            
    def _format_edge_label(self, edge_data: Dict) -> str:
        """Create readable label for edge"""
        edge_type = edge_data.get('type', '')
        permission = edge_data.get('permission', '')
        if permission:
            return f"{edge_type}\n({permission})"
        return edge_type
        
    def generate_html(self, output_path: str = None) -> str:
        """Generate complete HTML decision tree visualization"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"isosearch_tree_{self.scenario_name}_{timestamp}.html"
            
        html_content = self._generate_html_content()
        
        with open(output_path, 'w') as f:
            f.write(html_content)
            
        return output_path
        
    def _generate_html_content(self) -> str:
        """Generate the HTML content for decision tree visualization"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IsoSearch Decision Tree - {self.scenario_name}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }}
        
        .tree-container {{
            width: 100%;
            height: 800px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background-color: #fafafa;
            overflow: hidden;
        }}
        
        .node-group {{
            cursor: pointer;
        }}
        
        .node-selected {{
            stroke: #28a745;
            stroke-width: 3px;
            fill: #d4edda;
        }}
        
        .node-discarded {{
            stroke: #dc3545;
            stroke-width: 2px;
            fill: #f8d7da;
            opacity: 0.7;
        }}
        
        .node-initial {{
            stroke: #007bff;
            stroke-width: 3px;
            fill: #cce5ff;
        }}
        
        .link-selected {{
            stroke: #28a745;
            stroke-width: 3px;
        }}
        
        .link-discarded {{
            stroke: #dc3545;
            stroke-width: 2px;
            stroke-dasharray: 5,5;
            opacity: 0.7;
        }}
        
        .node-label {{
            font-size: 12px;
            text-anchor: middle;
            fill: #333;
            font-weight: bold;
        }}
        
        .metrics-text {{
            font-size: 10px;
            text-anchor: middle;
            fill: #666;
        }}
        
        .tooltip {{
            position: absolute;
            padding: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
        }}
        
        .graph-viewer {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 600px;
            height: 400px;
            background: white;
            border: 3px solid #007bff;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);
            display: none;
            z-index: 1000;
        }}
        
        .graph-viewer h3 {{
            margin: 0 0 15px 0;
            color: #007bff;
        }}
        
        .graph-svg {{
            width: 100%;
            height: 300px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        
        .close-btn {{
            position: absolute;
            top: 10px;
            right: 15px;
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #666;
        }}
        
        .legend {{
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }}
        
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
        }}
        
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 3px;
            margin-right: 8px;
            vertical-align: middle;
        }}
        
        .selected-path {{
            stroke: #28a745;
            stroke-width: 4px;
            fill: none;
            marker-end: url(#arrow-selected);
        }}
        
        .discarded-path {{
            stroke: #dc3545;
            stroke-width: 2px;
            fill: none;
            stroke-dasharray: 5,5;
            marker-end: url(#arrow-discarded);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌳 IsoSearch Decision Tree</h1>
            <h2>{self.scenario_name}</h2>
            <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Each node represents an OSmosis graph state. Click nodes to view detailed graph structure.</p>
        </div>
        
        <div class="tree-container">
            <svg id="tree-svg" width="100%" height="100%">
                <defs>
                    <marker id="arrow-selected" markerWidth="10" markerHeight="10" 
                            refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                        <path d="M0,0 L0,6 L9,3 z" fill="#28a745"/>
                    </marker>
                    <marker id="arrow-discarded" markerWidth="10" markerHeight="10" 
                            refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                        <path d="M0,0 L0,6 L9,3 z" fill="#dc3545"/>
                    </marker>
                </defs>
            </svg>
        </div>
        
        <div class="legend">
            <h3>Legend</h3>
            <div class="legend-item">
                <span class="legend-color" style="background-color: #cce5ff; border: 2px solid #007bff;"></span>
                Initial State
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background-color: #d4edda; border: 2px solid #28a745;"></span>
                Selected Path (Applied Transformation)
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background-color: #f8d7da; border: 2px solid #dc3545;"></span>
                Discarded Path (Rejected Transformation)
            </div>
        </div>
    </div>
    
    <div class="tooltip" id="tooltip"></div>
    
    <div class="graph-viewer" id="graph-viewer">
        <button class="close-btn" onclick="closeGraphViewer()">&times;</button>
        <h3 id="graph-title">Graph Structure</h3>
        <svg class="graph-svg" id="graph-detail-svg">
            <defs>
                <marker id="graph-arrow" markerWidth="10" markerHeight="7" 
                        refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
                </marker>
            </defs>
        </svg>
        <div id="graph-metrics"></div>
    </div>

    <script>
        // Data from Python
        const treeData = {json.dumps(self.tree_nodes, indent=2)};
        
        let svg, g, tooltip, width, height;
        
        // Initialize visualization
        document.addEventListener('DOMContentLoaded', function() {{
            initializeTree();
        }});
        
        function initializeTree() {{
            svg = d3.select('#tree-svg');
            tooltip = d3.select('#tooltip');
            
            const container = document.querySelector('.tree-container');
            width = container.clientWidth;
            height = container.clientHeight;
            
            svg.attr('width', width).attr('height', height);
            
            g = svg.append('g')
                .attr('transform', 'translate(50, 50)');
            
            drawDecisionTree();
        }}
        
        function drawDecisionTree() {{
            // Create hierarchical data structure
            const root = d3.hierarchy(createTreeStructure());
            
            // Create tree layout
            const treeLayout = d3.tree()
                .size([width - 100, height - 100]);
            
            treeLayout(root);
            
            // Draw links
            g.selectAll('.link')
                .data(root.links())
                .enter().append('path')
                .attr('class', d => d.target.data.is_selected ? 'selected-path' : 'discarded-path')
                .attr('d', d3.linkVertical()
                    .x(d => d.x)
                    .y(d => d.y));
            
            // Draw nodes
            const nodeGroups = g.selectAll('.node-group')
                .data(root.descendants())
                .enter().append('g')
                .attr('class', 'node-group')
                .attr('transform', d => `translate(${{d.x}},${{d.y}})`)
                .on('click', showGraphDetail)
                .on('mouseover', showTooltip)
                .on('mouseout', hideTooltip);
            
            // Add circles for nodes
            nodeGroups.append('circle')
                .attr('r', 30)
                .attr('class', d => {{
                    if (d.data.iteration === 0) return 'node-initial';
                    return d.data.is_selected ? 'node-selected' : 'node-discarded';
                }});
            
            // Add iteration labels
            nodeGroups.append('text')
                .attr('class', 'node-label')
                .attr('dy', '-5px')
                .text(d => d.data.iteration === 0 ? 'Initial' : `Iter ${{d.data.iteration}}`);
            
            // Add status labels
            nodeGroups.append('text')
                .attr('class', 'metrics-text')
                .attr('dy', '10px')
                .text(d => {{
                    if (d.data.iteration === 0) return 'Start';
                    return d.data.is_selected ? 'Selected' : 'Discarded';
                }});
        }}
        
        function createTreeStructure() {{
            // Build tree structure from flat node list
            const rootNode = {{
                id: 'root',
                iteration: 0,
                is_selected: true,
                children: []
            }};
            
            // Find root node (iteration 0 or first node)
            const initialNode = treeData.find(n => n.iteration === 0) || treeData[0];
            if (initialNode) {{
                rootNode.graph = initialNode.graph;
                rootNode.metrics = initialNode.metrics;
            }}
            
            // Group nodes by iteration
            const nodesByIteration = d3.group(treeData, d => d.iteration);
            
            let currentParent = rootNode;
            
            // Build tree level by level
            for (let iteration = 1; iteration <= Math.max(...treeData.map(d => d.iteration)); iteration++) {{
                const iterationNodes = nodesByIteration.get(iteration) || [];
                
                const selectedNode = iterationNodes.find(n => n.is_selected);
                const discardedNodes = iterationNodes.filter(n => !n.is_selected);
                
                if (selectedNode) {{
                    selectedNode.children = [];
                    currentParent.children.push(selectedNode);
                    
                    // Add discarded nodes as siblings
                    discardedNodes.forEach(discarded => {{
                        discarded.children = [];
                        currentParent.children.push(discarded);
                    }});
                    
                    currentParent = selectedNode;
                }}
            }}
            
            return rootNode;
        }}
        
        function showTooltip(event, d) {{
            const nodeData = d.data;
            let content = `<strong>Iteration ${{nodeData.iteration}}</strong><br/>`;
            
            if (nodeData.metrics) {{
                if (nodeData.metrics.RSI) {{
                    const rsi = typeof nodeData.metrics.RSI === 'object' ? 
                        Object.values(nodeData.metrics.RSI)[0] : nodeData.metrics.RSI;
                    content += `RSI: ${{rsi?.toFixed(3) || 'N/A'}}<br/>`;
                }}
                if (nodeData.metrics.ASR) {{
                    content += `ASR: ${{nodeData.metrics.ASR.toFixed(3)}}<br/>`;
                }}
            }}
            
            if (nodeData.candidate_info) {{
                content += `<br/><strong>Transformation:</strong><br/>`;
                content += `${{nodeData.candidate_info.transition_type}}<br/>`;
                content += `Impact: ${{nodeData.candidate_info.predicted_improvement?.toFixed(3) || 'N/A'}}`;
            }}
            
            tooltip.style('opacity', 1)
                .html(content)
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 10) + 'px');
        }}
        
        function hideTooltip() {{
            tooltip.style('opacity', 0);
        }}
        
        function showGraphDetail(event, d) {{
            const nodeData = d.data;
            const viewer = document.getElementById('graph-viewer');
            const title = document.getElementById('graph-title');
            const metrics = document.getElementById('graph-metrics');
            
            title.textContent = `Graph Structure - Iteration ${{nodeData.iteration}}`;
            
            // Show metrics
            let metricsHtml = '<strong>Metrics:</strong><br/>';
            if (nodeData.metrics && !nodeData.metrics.simulated) {{
                Object.entries(nodeData.metrics).forEach(([key, value]) => {{
                    if (typeof value === 'object') {{
                        const displayValue = Object.values(value)[0];
                        metricsHtml += `${{key}}: ${{typeof displayValue === 'number' ? displayValue.toFixed(3) : displayValue}}<br/>`;
                    }} else if (typeof value === 'number') {{
                        metricsHtml += `${{key}}: ${{value.toFixed(3)}}<br/>`;
                    }}
                }});
            }} else if (nodeData.candidate_info) {{
                metricsHtml += `Transformation: ${{nodeData.candidate_info.transition_type}}<br/>`;
                metricsHtml += `Predicted Impact: ${{nodeData.candidate_info.predicted_improvement?.toFixed(3) || 'N/A'}}`;
            }}
            metrics.innerHTML = metricsHtml;
            
            // Draw graph if available
            if (nodeData.graph && nodeData.graph.nodes) {{
                drawDetailGraph(nodeData.graph);
            }}
            
            viewer.style.display = 'block';
        }}
        
        function closeGraphViewer() {{
            document.getElementById('graph-viewer').style.display = 'none';
        }}
        
        function drawDetailGraph(graphData) {{
            const svg = d3.select('#graph-detail-svg');
            svg.selectAll('*').remove();
            
            const width = 560;
            const height = 280;
            
            // Create force simulation
            const simulation = d3.forceSimulation(graphData.nodes)
                .force('link', d3.forceLink(graphData.edges).id(d => d.id).distance(80))
                .force('charge', d3.forceManyBody().strength(-200))
                .force('center', d3.forceCenter(width / 2, height / 2));
            
            // Add links
            const link = svg.append('g')
                .selectAll('line')
                .data(graphData.edges)
                .enter().append('line')
                .attr('stroke', d => d.type === 'HOLD' ? '#4CAF50' : '#2196F3')
                .attr('stroke-width', 2)
                .attr('stroke-dasharray', d => d.type === 'REQUEST' ? '5,5' : 'none');
            
            // Add nodes
            const node = svg.append('g')
                .selectAll('g')
                .data(graphData.nodes)
                .enter().append('g');
            
            node.append('circle')
                .attr('r', d => d.type === 'PD' ? 20 : d.type === 'RESOURCE' ? 15 : 10)
                .attr('fill', d => {{
                    if (d.type === 'PD') return '#4CAF50';
                    if (d.type === 'RESOURCE') return '#2196F3';
                    return '#FF9800';
                }})
                .attr('stroke', '#333')
                .attr('stroke-width', 1);
            
            node.append('text')
                .text(d => d.id)
                .attr('text-anchor', 'middle')
                .attr('dy', '0.35em')
                .attr('font-size', '8px')
                .attr('fill', 'white')
                .attr('font-weight', 'bold');
            
            // Update positions on simulation tick
            simulation.on('tick', () => {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node
                    .attr('transform', d => `translate(${{d.x}},${{d.y}})`);
            }});
        }}
    </script>
</body>
</html>
        """


def create_test_decision_tree():
    """Create a test decision tree visualization"""
    viz = DecisionTreeVisualizer("test_decision_tree")
    
    # Create mock graph data similar to the working example
    class MockGraph:
        def __init__(self, nodes_data, edges_data):
            class MockNetworkXGraph:
                def __init__(self, nodes_data, edges_data):
                    self._nodes = nodes_data
                    self._edges = edges_data
                
                def nodes(self, data=False):
                    if data:
                        return self._nodes
                    return [node_id for node_id, _ in self._nodes]
                
                def edges(self, data=False):
                    if data:
                        return self._edges
                    return [(source, target) for source, target, _ in self._edges]
            
            self.g = MockNetworkXGraph(nodes_data, edges_data)
    
    # Initial graph
    initial_nodes = [
        ('PD_1', {'type': 'PD', 'data': 'user_process', 'extra': ''}),
        ('PD_2', {'type': 'PD', 'data': 'database_server', 'extra': ''}),
        ('VMR_1_1', {'type': 'RESOURCE', 'data': 'VMR', 'extra': '{"vmr_type": "HEAP", "va": "0x1000"}'})
    ]
    initial_edges = [
        ('PD_1', 'VMR_1_1', {'type': 'HOLD', 'permission': 'R'}),
        ('PD_2', 'VMR_1_1', {'type': 'HOLD', 'permission': 'R'})
    ]
    initial_graph = MockGraph(initial_nodes, initial_edges)
    
    # Add initial state
    viz.add_decision_node(
        iteration=0,
        graph_data=initial_graph,
        metrics={'RSI': {'VMR': 0.5}, 'ASR': 1.0, 'TCB': {'PD_1': [], 'PD_2': []}},
        candidates=[]
    )
    
    # Add iteration 1 with decision
    iter1_graph = MockGraph(initial_nodes, [('PD_1', 'VMR_1_1', {'type': 'HOLD', 'permission': 'R'})])
    viz.add_decision_node(
        iteration=1,
        graph_data=iter1_graph,
        metrics={'RSI': {'VMR': 0.0}, 'ASR': 0.5, 'TCB': {'PD_1': [], 'PD_2': []}},
        candidates=[
            {'transition_type': 'privatize_resource', 'predicted_improvement': 1.0, 'target_description': 'privatize VMR_1_1'},
            {'transition_type': 'add_mediator_pd', 'predicted_improvement': 0.5, 'target_description': 'add mediator for VMR_1_1'}
        ],
        selected_candidate={'transition_type': 'privatize_resource', 'predicted_improvement': 1.0},
        is_selected=True
    )
    
    # Add discarded paths
    viz.add_discarded_paths(
        iteration=1,
        base_graph=initial_graph,
        discarded_candidates=[
            {'transition_type': 'add_mediator_pd', 'predicted_improvement': 0.5, 'target_description': 'add mediator for VMR_1_1'}
        ]
    )
    
    output_file = viz.generate_html("test_decision_tree.html")
    print(f"Test decision tree visualization created: {output_file}")
    return output_file


if __name__ == "__main__":
    create_test_decision_tree()