"""
True BFS (Breadth-First Search) Implementation for IsoSearch
No scoring required - explores all paths exhaustively
"""

from collections import deque
import hashlib
import json
from generic_model import ModelGraph
from constraint_validation import validate_all_constraints

class BFSState:
    """State representation for BFS exploration"""
    def __init__(self, graph, path_history=None, iteration=0):
        self.graph = graph
        self.path_history = path_history or []
        self.iteration = iteration
        
    def get_state_hash(self):
        """Generate a unique hash for this graph state"""
        # Create a canonical representation of the graph
        edges = sorted([(str(u), str(v), str(d)) for u, v, d in self.graph.g.edges(data=True)])
        nodes = sorted([(str(n), str(d)) for n, d in self.graph.g.nodes(data=True)])
        state_str = json.dumps({'nodes': nodes, 'edges': edges}, sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()
    
    def __str__(self):
        return f"BFSState(iter={self.iteration}, path_len={len(self.path_history)})"


def TrueBFSExploration(scenario, max_depth=8, max_states=10000):
    """
    True BFS exploration without scoring - explores ALL paths
    
    Args:
        scenario: Scenario object with goals, constraints, transitions
        max_depth: Maximum exploration depth (default 8)
        max_states: Maximum states to explore before stopping (default 10000)
        
    Returns:
        List of discovered mechanisms
    """
    print("🔍 Starting TRUE BFS exploration (no scoring)")
    print(f"   Max depth: {max_depth}")
    print(f"   Max states: {max_states}")
    
    # Initialize components from scenario
    goals = scenario.goals
    constraints = scenario.constraints
    transitions = scenario.get_allowed_transitions()
    initial_graph = scenario.build_graph()
    
    # BFS data structures
    queue = deque([BFSState(initial_graph)])
    visited = set()  # Track visited states by hash
    explored_mechanisms = []
    states_explored = 0
    
    # Add initial state to visited
    initial_hash = queue[0].get_state_hash()
    visited.add(initial_hash)
    
    print(f"\n📊 Initial graph:")
    from isosearch import _print_graph_arrows
    _print_graph_arrows(initial_graph)
    
    while queue and states_explored < max_states:
        # Get next state from queue (FIFO for BFS)
        current_state = queue.popleft()
        states_explored += 1
        
        # Progress reporting
        if states_explored % 50 == 0:
            print(f"\n⏳ Progress: {states_explored} states explored, {len(queue)} in queue, {len(explored_mechanisms)} mechanisms found")
        
        # Check depth limit
        if current_state.iteration >= max_depth:
            continue
            
        # Check if this state satisfies goals and constraints
        from isosearch import ComputeMetrics, GoalsMet
        
        try:
            # Validate constraints
            constraints_satisfied, violations = validate_all_constraints(
                current_state.graph, constraints, mode="strict"
            )
            
            if constraints_satisfied:
                # Check goals
                metrics = ComputeMetrics(current_state.graph)
                goals_met = GoalsMet(metrics, goals)
                
                if goals_met:
                    # Found a mechanism!
                    print(f"\n✅ MECHANISM FOUND at depth {current_state.iteration}!")
                    print(f"   Path: {' → '.join(current_state.path_history[-3:])}")  # Show last 3 steps
                    explored_mechanisms.append({
                        'graph': current_state.graph,
                        'metrics': metrics,
                        'path': current_state.path_history,
                        'depth': current_state.iteration
                    })
                    
                    # Check if this is a mediation pattern
                    if _is_mediation_pattern(current_state.graph):
                        print("   🎯 MEDIATION PATTERN DISCOVERED!")
                        
        except Exception as e:
            # Continue exploration even if metrics/goals check fails
            pass
        
        # Generate all possible next states
        next_states_count = 0
        
        for transition in transitions:
            try:
                # Find all candidates for this transition
                candidates = transition.find_candidates(current_state.graph, constraints)
                
                for candidate in candidates:
                    # Create new graph with this transition
                    new_graph = ModelGraph()
                    new_graph.g = current_state.graph.g.copy()
                    
                    # Apply the transition
                    param_values = candidate.get('param_values', {})
                    success = transition.apply(new_graph, param_values)
                    
                    if success:
                        # Create new state
                        path_desc = f"{transition.name}({candidate.get('target_description', '')})"
                        new_state = BFSState(
                            graph=new_graph,
                            path_history=current_state.path_history + [path_desc],
                            iteration=current_state.iteration + 1
                        )
                        
                        # Check if we've seen this state before
                        state_hash = new_state.get_state_hash()
                        if state_hash not in visited:
                            visited.add(state_hash)
                            queue.append(new_state)
                            next_states_count += 1
                            
            except Exception as e:
                # Continue with other transitions
                continue
        
        # Report on state expansion (only first few for clarity)
        if next_states_count > 0 and states_explored <= 5:
            print(f"\n🌳 State {states_explored} (depth {current_state.iteration}) expanded to {next_states_count} new states")
            if current_state.path_history:
                print(f"   Current path: ...{current_state.path_history[-1]}")
    
    # Final report
    print(f"\n🏁 BFS exploration complete!")
    print(f"📊 Statistics:")
    print(f"   States explored: {states_explored}")
    print(f"   Unique states visited: {len(visited)}")
    print(f"   States in queue (unexplored): {len(queue)}")
    print(f"   Mechanisms discovered: {len(explored_mechanisms)}")
    
    if states_explored >= max_states:
        print(f"   ⚠️  Stopped due to state limit ({max_states})")
    
    # Show all discovered mechanisms
    if explored_mechanisms:
        print(f"\n🎯 Discovered Mechanisms:")
        for i, mech in enumerate(explored_mechanisms):
            print(f"\n   Mechanism {i+1} (depth {mech['depth']}):")
            print(f"   Full path ({len(mech['path'])} steps):")
            for j, step in enumerate(mech['path']):
                print(f"      {j+1}. {step}")
            
            # Check if mediation
            if _is_mediation_pattern(mech['graph']):
                print("   ✨ This is a MEDIATION pattern!")
    
    return explored_mechanisms


def _is_mediation_pattern(graph):
    """Check if the graph represents a mediation pattern"""
    # Look for pattern: PD1 -> REQUEST -> PD3 -> HOLD -> Resource <- REQUEST <- PD2
    
    request_edges = [(u, v) for u, v, d in graph.g.edges(data=True) 
                     if d.get('type') == 'REQUEST']
    
    # Look for a mediator PD (has incoming REQUEST edges)
    mediator_candidates = {}
    for from_pd, to_pd in request_edges:
        if to_pd not in mediator_candidates:
            mediator_candidates[to_pd] = []
        mediator_candidates[to_pd].append(from_pd)
    
    # Check if any mediator has multiple requesters and holds resources
    for mediator, requesters in mediator_candidates.items():
        if len(requesters) >= 2:  # At least 2 PDs requesting from mediator
            # Check if mediator holds any resources
            mediator_resources = [v for u, v, d in graph.g.edges(data=True)
                                 if u == mediator and d.get('type') == 'HOLD']
            if mediator_resources:
                return True
    
    return False


# Integration function to use with existing isosearch
def run_true_bfs(scenario_name):
    """Run true BFS on a specific scenario"""
    from scenarios import get_scenario
    
    scenario = get_scenario(scenario_name)
    if not scenario:
        print(f"❌ Scenario '{scenario_name}' not found")
        return []
    
    print(f"🎯 Running TRUE BFS on scenario: {scenario.name}")
    print(f"   Description: {scenario.description}")
    
    mechanisms = TrueBFSExploration(scenario)
    
    return mechanisms