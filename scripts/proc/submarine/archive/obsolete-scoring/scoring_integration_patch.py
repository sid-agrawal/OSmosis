"""
Scoring Integration Patch

This module provides integration points for using the new generic scoring framework
with the existing isosearch.py without requiring major modifications.
"""

import os
import sys

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from pattern_aware_scoring_v2 import get_pattern_aware_score as get_generic_score
from generic_scoring_factory import create_scoring_for_domain, ScoringSystemFactory


class ScoringIntegration:
    """Integration layer for connecting new scoring system to existing code"""
    
    def __init__(self, use_generic=True, domain="os_security"):
        self.use_generic = use_generic
        self.domain = domain
        self._scorer = None
        
        if use_generic:
            self._scorer = create_scoring_for_domain(domain)
    
    def get_pattern_aware_score(self, transition, candidate, graph, goals, constraints, initial_graph=None):
        """
        Unified interface that can use either original or generic scoring
        """
        if self.use_generic and self._scorer:
            return self._scorer.score_operation(transition, candidate, graph, goals, constraints)
        else:
            # Fallback to original implementation
            try:
                from pattern_aware_scoring import get_pattern_aware_score as original_score
                return original_score(transition, candidate, graph, goals, constraints, initial_graph)
            except ImportError:
                # If original not available, use generic as fallback
                return get_generic_score(transition, candidate, graph, goals, constraints, initial_graph)
    
    def configure_for_scenario(self, scenario_name: str):
        """Configure scoring system for specific scenario"""
        
        # Map scenario names to domains
        scenario_domain_map = {
            'basic_sharing': 'os_security',
            'basic_sharing_primitive': 'os_security', 
            'mediator_test_indirect': 'os_security',
            'high_sharing': 'os_security',
            'attack_surface_reduction': 'network_security'
        }
        
        domain = scenario_domain_map.get(scenario_name, 'os_security')
        
        if domain != self.domain:
            self.domain = domain
            self._scorer = create_scoring_for_domain(domain)
    
    def get_scoring_explanation(self, transition, candidate, graph, goals, constraints):
        """Get detailed explanation of scoring decision"""
        if self.use_generic and self._scorer:
            return self._scorer.get_scoring_explanation(transition, candidate, graph, goals, constraints)
        else:
            return {"explanation": "Detailed explanations only available with generic framework"}


# Global integration instance
_integration = ScoringIntegration(use_generic=True)


def patch_isosearch():
    """
    Monkey patch isosearch.py to use new scoring system
    Call this function before running isosearch to enable generic framework
    """
    
    # Try to patch the existing module
    try:
        import isosearch
        
        # Store original function
        if not hasattr(isosearch, '_original_predict_improvement'):
            isosearch._original_predict_improvement = isosearch._predict_improvement
        
        # Replace with our integration
        def patched_predict_improvement(transition, candidate, graph, goals, constraints=None):
            return _integration.get_pattern_aware_score(transition, candidate, graph, goals, constraints)
        
        isosearch._predict_improvement = patched_predict_improvement
        print("✅ Successfully patched isosearch to use generic scoring framework")
        
    except ImportError:
        print("⚠️  Could not import isosearch module for patching")
    except Exception as e:
        print(f"❌ Error patching isosearch: {e}")


def unpatch_isosearch():
    """Restore original isosearch behavior"""
    try:
        import isosearch
        
        if hasattr(isosearch, '_original_predict_improvement'):
            isosearch._predict_improvement = isosearch._original_predict_improvement
            print("✅ Restored original isosearch scoring")
        
    except ImportError:
        print("⚠️  Could not import isosearch module")


def configure_integration(use_generic=True, domain="os_security"):
    """Configure the global integration settings"""
    global _integration
    _integration = ScoringIntegration(use_generic=use_generic, domain=domain)


def get_integration_status():
    """Get current integration status"""
    return {
        'using_generic': _integration.use_generic,
        'domain': _integration.domain,
        'scorer_type': type(_integration._scorer).__name__ if _integration._scorer else 'None'
    }


# Convenience functions for common scenarios
def enable_generic_scoring(domain="os_security"):
    """Enable generic scoring framework"""
    configure_integration(use_generic=True, domain=domain)
    patch_isosearch()


def disable_generic_scoring():
    """Disable generic scoring framework and use original"""
    configure_integration(use_generic=False)
    unpatch_isosearch()


def switch_domain(domain: str):
    """Switch to different domain configuration"""
    _integration.configure_for_scenario(domain)


# Testing utilities
def test_integration():
    """Test the integration with sample data"""
    
    print("Testing scoring integration...")
    
    # Create mock objects for testing
    class MockTransition:
        def __init__(self, name):
            self.name = name
    
    class MockGraph:
        def __init__(self):
            self.g = None  # Would be actual networkx graph
    
    # Test basic functionality
    try:
        transition = MockTransition("add_hold_edge")
        candidate = {'param_values': {'from_node': 'PD_1', 'to_node': 'FILE_1_3'}}
        graph = MockGraph()
        goals = []
        constraints = []
        
        score = _integration.get_pattern_aware_score(transition, candidate, graph, goals, constraints)
        print(f"✅ Integration test successful, score: {score}")
        
        # Test explanation
        explanation = _integration.get_scoring_explanation(transition, candidate, graph, goals, constraints)
        print(f"✅ Explanation generation successful: {explanation.get('final_score', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")


# Performance comparison
def compare_scoring_performance(num_iterations=100):
    """Compare performance between original and generic scoring"""
    
    print(f"Comparing scoring performance over {num_iterations} iterations...")
    
    # This would run actual performance comparison
    # For now, just demonstrate the interface
    print("Performance comparison requires actual graph data for meaningful results")


if __name__ == "__main__":
    # Run integration tests when executed directly
    test_integration()
    
    # Show how to use the integration
    print("\nIntegration Usage Examples:")
    print("1. Enable generic scoring: enable_generic_scoring('os_security')")
    print("2. Switch domains: switch_domain('network_security')")
    print("3. Disable generic scoring: disable_generic_scoring()")
    print("4. Check status: get_integration_status()")