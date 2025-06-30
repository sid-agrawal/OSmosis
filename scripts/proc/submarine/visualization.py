"""
HTML Visualization System for IsoSearch Algorithm
Generates interactive HTML reports showing graph transformations, metrics, and decisions
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any

class IsoSearchVisualizer:
    """Creates HTML visualizations for IsoSearch algorithm progress"""
    
    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
        self.iterations = []
        self.decisions = []
        self.start_time = datetime.now()
        
    def add_iteration(self, iteration_num: int, graph_data: Dict, metrics: Dict, 
                     candidates: List[Dict], selected_candidate: Dict = None):
        """Add data for one iteration"""
        iteration_data = {
            'iteration': iteration_num,
            'timestamp': datetime.now().isoformat(),
            'graph': self._serialize_graph(graph_data),
            'metrics': metrics,
            'candidates': candidates,
            'selected': selected_candidate,
            'goals_met': self._check_goals_met(metrics)
        }
        self.iterations.append(iteration_data)
        
    def add_decision(self, iteration: int, selected: str, discarded: List[str], reasoning: str):
        """Add decision data for visualization"""
        decision_data = {
            'iteration': iteration,
            'selected': selected,
            'discarded': discarded,
            'reasoning': reasoning,
            'timestamp': datetime.now().isoformat()
        }
        self.decisions.append(decision_data)
        
    def _serialize_graph(self, graph) -> Dict:
        """Convert graph to JSON-serializable format"""
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
        
    def _check_goals_met(self, metrics: Dict) -> bool:
        """Simple check if goals appear to be met"""
        # This is a simplified check - in practice would need access to scenario goals
        rsi = metrics.get('RSI', {})
        if isinstance(rsi, dict):
            return all(val < 0.3 for val in rsi.values()) if rsi else True
        return rsi < 0.3 if isinstance(rsi, (int, float)) else False
        
    def generate_html(self, output_path: str = None) -> str:
        """Generate complete HTML visualization"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"isosearch_viz_{self.scenario_name}_{timestamp}.html"
            
        html_content = self._generate_html_content()
        
        with open(output_path, 'w') as f:
            f.write(html_content)
            
        return output_path
        
    def _generate_html_content(self) -> str:
        """Generate the actual HTML content"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IsoSearch Visualization - {self.scenario_name}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        
        .container {{
            max-width: 1400px;
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
        
        .controls {{
            margin-bottom: 20px;
            text-align: center;
        }}
        
        .iteration-selector {{
            padding: 10px;
            font-size: 16px;
            border: 2px solid #007bff;
            border-radius: 5px;
            margin: 0 10px;
        }}
        
        .metrics-panel {{
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }}
        
        .metric-box {{
            text-align: center;
            padding: 10px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 120px;
        }}
        
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }}
        
        .metric-label {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
        
        .visualization-area {{
            display: flex;
            gap: 20px;
        }}
        
        .graph-container {{
            flex: 2;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px;
            background-color: #fafafa;
        }}
        
        .decisions-panel {{
            flex: 1;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            background-color: #f8f9fa;
            max-height: 600px;
            overflow-y: auto;
        }}
        
        .decision-item {{
            margin-bottom: 15px;
            padding: 10px;
            background-color: white;
            border-radius: 5px;
            border-left: 4px solid #28a745;
        }}
        
        .decision-item.discarded {{
            border-left-color: #dc3545;
            opacity: 0.7;
        }}
        
        .decision-title {{
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .decision-details {{
            font-size: 14px;
            color: #666;
        }}
        
        .graph-svg {{
            width: 100%;
            height: 500px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: white;
        }}
        
        .node {{
            cursor: pointer;
        }}
        
        .node circle {{
            stroke: #333;
            stroke-width: 2px;
        }}
        
        .node.pd circle {{
            fill: #4CAF50;
            r: 25;
        }}
        
        .node.resource circle {{
            fill: #2196F3;
            r: 20;
        }}
        
        .node.resource-space circle {{
            fill: #FF9800;
            r: 15;
        }}
        
        .node text {{
            font-size: 12px;
            text-anchor: middle;
            dominant-baseline: central;
            fill: white;
            font-weight: bold;
        }}
        
        .link {{
            stroke: #333;
            stroke-width: 2;
            marker-end: url(#arrowhead);
        }}
        
        .link.hold {{
            stroke: #4CAF50;
        }}
        
        .link.request {{
            stroke: #2196F3;
            stroke-dasharray: 5,5;
        }}
        
        .link-label {{
            font-size: 10px;
            text-anchor: middle;
            fill: #666;
        }}
        
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        
        .status-success {{
            background-color: #28a745;
        }}
        
        .status-pending {{
            background-color: #ffc107;
        }}
        
        .status-error {{
            background-color: #dc3545;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 IsoSearch Algorithm Visualization</h1>
            <h2>{self.scenario_name}</h2>
            <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
        
        <div class="controls">
            <label for="iteration-select">Iteration:</label>
            <select id="iteration-select" class="iteration-selector">
                <option value="0">Initial State</option>
            </select>
            <button onclick="playAnimation()">▶️ Play Animation</button>
            <button onclick="pauseAnimation()">⏸️ Pause</button>
            <button onclick="resetAnimation()">⏹️ Reset</button>
        </div>
        
        <div class="metrics-panel" id="metrics-panel">
            <!-- Metrics will be populated by JavaScript -->
        </div>
        
        <div class="visualization-area">
            <div class="graph-container">
                <h3>Graph Structure</h3>
                <svg class="graph-svg" id="graph-svg">
                    <defs>
                        <marker id="arrowhead" markerWidth="10" markerHeight="7" 
                                refX="9" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
                        </marker>
                    </defs>
                </svg>
            </div>
            
            <div class="decisions-panel">
                <h3>Decisions & Candidates</h3>
                <div id="decisions-list">
                    <!-- Decisions will be populated by JavaScript -->
                </div>
            </div>
        </div>
    </div>

    <script>
        // Data from Python
        const iterationsData = {json.dumps(self.iterations, indent=2)};
        const decisionsData = {json.dumps(self.decisions, indent=2)};
        
        let currentIteration = 0;
        let animationInterval = null;
        
        // Initialize visualization
        document.addEventListener('DOMContentLoaded', function() {{
            setupIterationSelector();
            showIteration(0);
        }});
        
        function setupIterationSelector() {{
            const selector = document.getElementById('iteration-select');
            
            // Clear existing options except initial
            while (selector.options.length > 1) {{
                selector.remove(1);
            }}
            
            // Add options for each iteration
            iterationsData.forEach((iteration, index) => {{
                const option = document.createElement('option');
                option.value = index + 1;
                option.textContent = `Iteration ${{iteration.iteration}}`;
                selector.appendChild(option);
            }});
            
            selector.addEventListener('change', function() {{
                showIteration(parseInt(this.value));
            }});
        }}
        
        function showIteration(iterationIndex) {{
            currentIteration = iterationIndex;
            
            if (iterationIndex === 0) {{
                // Show initial state
                if (iterationsData.length > 0) {{
                    const initialData = iterationsData[0];
                    updateMetrics({{}}); // Empty metrics for initial state
                    drawGraph(initialData.graph);
                    updateDecisions([]);
                }}
            }} else {{
                const iterationData = iterationsData[iterationIndex - 1];
                updateMetrics(iterationData.metrics);
                drawGraph(iterationData.graph);
                updateDecisions(iterationData.candidates, iterationData.selected);
            }}
        }}
        
        function updateMetrics(metrics) {{
            const panel = document.getElementById('metrics-panel');
            panel.innerHTML = '';
            
            // Handle different metric formats
            const displayMetrics = {{
                'RSI': extractRSI(metrics.RSI),
                'ASR': metrics.ASR ? metrics.ASR.toFixed(3) : 'N/A',
                'TCB': extractTCB(metrics.TCB),
                'FR': extractFR(metrics.FR)
            }};
            
            Object.entries(displayMetrics).forEach(([name, value]) => {{
                const metricBox = document.createElement('div');
                metricBox.className = 'metric-box';
                metricBox.innerHTML = `
                    <div class="metric-value">${{value}}</div>
                    <div class="metric-label">${{name}}</div>
                `;
                panel.appendChild(metricBox);
            }});
        }}
        
        function extractRSI(rsi) {{
            if (!rsi) return 'N/A';
            if (typeof rsi === 'object') {{
                const values = Object.values(rsi);
                return values.length > 0 ? values[0].toFixed(3) : '0.000';
            }}
            return rsi.toFixed(3);
        }}
        
        function extractTCB(tcb) {{
            if (!tcb) return 'N/A';
            if (typeof tcb === 'object') {{
                const totalCount = Object.values(tcb).reduce((sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0), 0);
                return totalCount.toString();
            }}
            return tcb.toString();
        }}
        
        function extractFR(fr) {{
            if (!fr) return 'N/A';
            if (typeof fr === 'object') {{
                const values = Object.values(fr).filter(v => v !== Infinity && !isNaN(v));
                return values.length > 0 ? values[0].toFixed(1) : '∞';
            }}
            return fr.toString();
        }}
        
        function drawGraph(graphData) {{
            const svg = d3.select('#graph-svg');
            svg.selectAll('*').remove();
            
            const width = 800;
            const height = 500;
            
            // Create force simulation
            const simulation = d3.forceSimulation(graphData.nodes)
                .force('link', d3.forceLink(graphData.edges).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2));
            
            // Add links
            const link = svg.append('g')
                .selectAll('line')
                .data(graphData.edges)
                .enter().append('line')
                .attr('class', d => `link ${{d.type.toLowerCase()}}`)
                .attr('stroke-width', 2);
            
            // Add link labels
            const linkLabel = svg.append('g')
                .selectAll('text')
                .data(graphData.edges)
                .enter().append('text')
                .attr('class', 'link-label')
                .text(d => d.label);
            
            // Add nodes
            const node = svg.append('g')
                .selectAll('g')
                .data(graphData.nodes)
                .enter().append('g')
                .attr('class', d => `node ${{d.type.toLowerCase().replace('_', '-')}}`)
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));
            
            node.append('circle')
                .attr('r', d => {{
                    if (d.type === 'PD') return 25;
                    if (d.type === 'RESOURCE') return 20;
                    return 15;
                }});
            
            node.append('text')
                .text(d => d.label)
                .attr('dy', '0.35em')
                .style('font-size', '10px');
            
            // Update positions on simulation tick
            simulation.on('tick', () => {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                linkLabel
                    .attr('x', d => (d.source.x + d.target.x) / 2)
                    .attr('y', d => (d.source.y + d.target.y) / 2);
                
                node
                    .attr('transform', d => `translate(${{d.x}},${{d.y}})`);
            }});
            
            function dragstarted(event, d) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }}
            
            function dragged(event, d) {{
                d.fx = event.x;
                d.fy = event.y;
            }}
            
            function dragended(event, d) {{
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }}
        }}
        
        function updateDecisions(candidates, selected) {{
            const decisionsList = document.getElementById('decisions-list');
            decisionsList.innerHTML = '';
            
            if (!candidates || candidates.length === 0) {{
                decisionsList.innerHTML = '<p>No decisions for this iteration</p>';
                return;
            }}
            
            candidates.forEach(candidate => {{
                const isSelected = selected && candidate.description === selected.description;
                const decisionDiv = document.createElement('div');
                decisionDiv.className = `decision-item ${{isSelected ? '' : 'discarded'}}`;
                
                const statusClass = isSelected ? 'status-success' : 'status-pending';
                const statusText = isSelected ? 'SELECTED' : 'DISCARDED';
                
                decisionDiv.innerHTML = `
                    <div class="decision-title">
                        <span class="status-indicator ${{statusClass}}"></span>
                        ${{statusText}}: ${{candidate.target_description || candidate.description || 'Unknown transformation'}}
                    </div>
                    <div class="decision-details">
                        Impact: ${{candidate.predicted_improvement || candidate.improvement || 'N/A'}}
                    </div>
                `;
                
                decisionsList.appendChild(decisionDiv);
            }});
        }}
        
        function playAnimation() {{
            if (animationInterval) return;
            
            animationInterval = setInterval(() => {{
                currentIteration++;
                if (currentIteration > iterationsData.length) {{
                    currentIteration = 0;
                }}
                
                document.getElementById('iteration-select').value = currentIteration;
                showIteration(currentIteration);
            }}, 2000);
        }}
        
        function pauseAnimation() {{
            if (animationInterval) {{
                clearInterval(animationInterval);
                animationInterval = null;
            }}
        }}
        
        function resetAnimation() {{
            pauseAnimation();
            currentIteration = 0;
            document.getElementById('iteration-select').value = 0;
            showIteration(0);
        }}
    </script>
</body>
</html>
        """


def create_test_visualization():
    """Create a test visualization with sample data"""
    viz = IsoSearchVisualizer("test_scenario")
    
    # Create mock graph data
    class MockGraph:
        def __init__(self):
            class MockNetworkXGraph:
                def nodes(self, data=False):
                    if data:
                        return [
                            ('PD_1', {'type': 'PD', 'data': 'user_process', 'extra': ''}),
                            ('PD_2', {'type': 'PD', 'data': 'database_server', 'extra': ''}),
                            ('VMR_1_1', {'type': 'RESOURCE', 'data': 'VMR', 'extra': '{"vmr_type": "HEAP", "va": "0x1000"}'})
                        ]
                    return ['PD_1', 'PD_2', 'VMR_1_1']
                
                def edges(self, data=False):
                    if data:
                        return [
                            ('PD_1', 'VMR_1_1', {'type': 'HOLD', 'permission': 'R'}),
                            ('PD_2', 'VMR_1_1', {'type': 'HOLD', 'permission': 'R'})
                        ]
                    return [('PD_1', 'VMR_1_1'), ('PD_2', 'VMR_1_1')]
            
            self.g = MockNetworkXGraph()
    
    mock_graph = MockGraph()
    
    # Add test iteration
    viz.add_iteration(
        iteration_num=1,
        graph_data=mock_graph,
        metrics={'RSI': {'VMR': 0.5}, 'ASR': 1.0, 'TCB': {'PD_1': [], 'PD_2': []}, 'FR': {'PD_1,PD_2': 2.0}},
        candidates=[
            {'description': 'privatize_resource VMR_1_1', 'improvement': 1.0},
            {'description': 'add_mediator_pd between PD_1 and PD_2', 'improvement': 0.5}
        ],
        selected_candidate={'description': 'privatize_resource VMR_1_1', 'improvement': 1.0}
    )
    
    output_file = viz.generate_html("test_visualization.html")
    print(f"Test visualization created: {output_file}")
    return output_file


if __name__ == "__main__":
    create_test_visualization()