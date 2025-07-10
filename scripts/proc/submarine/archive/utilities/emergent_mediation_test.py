#!/usr/bin/env python3
"""
Experiment: Can mediation discovery emerge without special-case logic?

This script modifies the IsoSearch algorithm to remove mediation-specific
handling and test whether mediation patterns can emerge naturally through
constraint pressure and exploration.
"""

def simplified_find_add_pd_candidates(self, graph, constraints):
    """Simplified PD addition - no mediation special cases"""
    candidates = []
    
    # Simple strategy: Always suggest adding a new PD when system has constraints
    # Let the scoring system and constraints naturally guide toward mediation
    
    # Check if we have any constraint violations that might benefit from new PDs
    has_violations = False
    for constraint in constraints:
        is_satisfied, _ = validate_constraint(graph, constraint)
        if not is_satisfied:
            has_violations = True
            break
    
    if has_violations:
        # Higher priority when violations exist
        constraint_relevance = 0.7
        description = "add new protection domain to help resolve constraints"
        addresses_violation = True
    else:
        # Lower priority when no violations
        constraint_relevance = 0.3
        description = "add new protection domain for system expansion"
        addresses_violation = False
    
    candidates.append({
        'param_values': {'pd_type': 'new_component'},
        'target_description': description,
        'constraint_relevance': constraint_relevance,
        'addresses_violation': addresses_violation
    })
    
    return candidates


def simplified_find_add_hold_edge_candidates(self, graph, constraints):
    """Simplified HOLD edge addition - minimal special logic"""
    candidates = []
    
    # Find PDs and resources
    pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']
    resources = [node for node, data in graph.g.nodes(data=True) 
                if data.get('type') == 'RESOURCE' and data.get('data') == 'FILE']
    
    for pd in pds:
        current_resources = self._get_pd_held_resources(graph, pd)
        
        for resource in resources:
            if resource not in current_resources:
                # Check prohibit_direct_hold constraints
                prohibited = self._is_connection_prohibited(pd, resource, constraints)
                
                if not prohibited:
                    # Simplified scoring - no complex mediation logic
                    constraint_relevance = 0.4  # Standard score
                    addresses_violation = False
                    description = f"connect {pd} to {resource}"
                    
                    # Small boost for orphaned resources (natural tendency)
                    holders = self._get_resource_holders(graph, resource)
                    if len(holders) == 0:
                        constraint_relevance = 0.5
                        description = f"connect {pd} to orphaned resource {resource}"
                    
                    candidates.append({
                        'param_values': {'pd': pd, 'resource': resource, 'permission': 'R'},
                        'target_description': description,
                        'constraint_relevance': constraint_relevance,
                        'addresses_violation': addresses_violation
                    })
    
    return candidates


def simplified_find_add_request_edge_candidates(self, graph, constraints):
    """Simplified REQUEST edge addition - let patterns emerge naturally"""
    candidates = []
    
    pds = [node for node, data in graph.g.nodes(data=True) if data.get('type') == 'PD']
    
    for from_pd in pds:
        for to_pd in pds:
            if from_pd != to_pd:
                # Check if edge already exists
                edge_exists = False
                for from_node, to_node, edge_data in graph.g.edges(data=True):
                    if (from_node == from_pd and to_node == to_pd and 
                        edge_data.get('type') == 'REQUEST'):
                        edge_exists = True
                        break
                
                if not edge_exists:
                    # Standard scoring - no complex mediation detection
                    constraint_relevance = 0.2  # Lower priority
                    description = f"add authority relationship: {from_pd} -> {to_pd}"
                    
                    # Small boost if to_pd has resources that from_pd might need
                    to_pd_resources = self._get_pd_held_resources(graph, to_pd)
                    if to_pd_resources:
                        constraint_relevance = 0.3
                        description = f"enable indirect access: {from_pd} -> {to_pd}"
                    
                    candidates.append({
                        'param_values': {'from_pd': from_pd, 'to_pd': to_pd},
                        'target_description': description,
                        'constraint_relevance': constraint_relevance,
                        'addresses_violation': False
                    })
    
    return candidates


def add_exploration_diversity(candidates, exploration_factor=0.2):
    """Add diversity to candidate selection to encourage exploration"""
    import random
    
    if len(candidates) <= 1:
        return candidates
    
    # Sort by score
    candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # With some probability, select from top N candidates instead of just the best
    if random.random() < exploration_factor:
        top_n = min(3, len(candidates))
        selected_index = random.randint(0, top_n - 1)
        # Move selected candidate to front
        selected = candidates.pop(selected_index)
        candidates.insert(0, selected)
    
    return candidates


def test_emergent_mediation_discovery():
    """Test whether mediation can emerge without special cases"""
    
    print("🧪 Testing Emergent Mediation Discovery")
    print("=" * 50)
    
    # The key insight: The same constraint combination that forces mediation
    # in the current system should still work:
    
    constraints = [
        # These create the forcing function:
        "prohibit_direct_hold: PD_1 -> FILE_1_3",  # Remove direct access
        "prohibit_direct_hold: PD_2 -> FILE_1_3",  # Remove direct access  
        "requires_resource_access: PD_1 -> FILE_1_3",  # Must have access
        "requires_resource_access: PD_2 -> FILE_1_3",  # Must have access
        "requires_resource_exists: FILE_1_3"  # Cannot delete resource
    ]
    
    print("Key insight: These constraints create an impossible situation")
    print("that can ONLY be resolved through mediation:")
    print()
    print("1. FILE_1_3 cannot be held directly by PD_1 or PD_2")
    print("2. FILE_1_3 cannot be deleted (must exist)")  
    print("3. PD_1 and PD_2 must have access to FILE_1_3")
    print("4. Only solution: Indirect access through a mediator")
    print()
    
    print("Expected emergent discovery path:")
    print("1. Remove prohibited edges (iterations 1-2)")
    print("2. Add new PD when constraint violations exist (iteration 3)")
    print("3. Connect new PD to orphaned resource (iteration 4)")
    print("4. Add REQUEST edges for indirect access (iteration 5+)")
    print()
    
    print("This should work because:")
    print("- Constraint pressure still creates 'orphaned resource' scenario")
    print("- Three-phase scoring still coordinates primitive sequences")
    print("- Natural tendency to connect PDs to orphaned resources")
    print("- REQUEST edges naturally emerge for resource access")


if __name__ == "__main__":
    test_emergent_mediation_discovery()