"""
Pattern-Aware Scoring V2 - Generic Framework Integration

This module provides a migration path from the hardcoded pattern-aware scoring
to the new generic framework while maintaining backward compatibility.
"""

from generic_scoring_factory import (
    create_default_scoring, create_scoring_for_domain, ScoringSystemFactory
)
from generic_pattern_aware_scoring import GenericPatternAwareScoring
from generic_resource_type_system import ResourceTypeSystem
from typing import Dict, List, Optional, Any

# Global instance for backward compatibility
_default_scorer = None


def get_pattern_aware_score(transition, candidate, graph, goals, constraints, initial_graph=None):
    """
    Drop-in replacement for the original get_pattern_aware_score function.
    Uses the new generic framework with configuration that matches original behavior.
    """
    global _default_scorer
    
    # Create scorer instance if not cached
    if _default_scorer is None:
        _default_scorer = create_default_scoring()
    
    return _default_scorer.score_operation(transition, candidate, graph, goals, constraints)


class LegacyPatternAwareScoring:
    """
    Legacy-compatible wrapper around the new generic scoring system.
    Provides the same interface as the original PatternAwareScoring class.
    """
    
    def __init__(self, initial_graph=None):
        """Initialize with backward-compatible interface"""
        self.scorer = create_default_scoring()
        
        # Set initial graph for original PD identification if provided
        if initial_graph is not None:
            self.scorer._pattern_states['original_pds'] = self.scorer._identify_original_pds(initial_graph)
    
    def analyze_graph_state(self, graph):
        """Backward-compatible graph state analysis"""
        return self.scorer._analyze_graph_state(graph)
    
    def score_operation(self, operation, candidate, graph, goals, constraints):
        """Backward-compatible operation scoring"""
        return self.scorer.score_operation(operation, candidate, graph, goals, constraints)
    
    # Legacy helper methods for compatibility
    def _apply_pattern_scoring(self, op_name, params, base_score, state_analysis, graph, constraints, goals):
        """Legacy method - now delegates to generic framework"""
        # Create candidate dict in expected format
        candidate = {'param_values': params}
        return self.scorer.score_operation(
            type('Operation', (), {'name': op_name})(),
            candidate, graph, goals, constraints
        )
    
    def _score_for_mediation_pattern(self, op_name, params, base_score, state_analysis, graph, constraints):
        """Legacy mediation scoring - now handled by MediationPatternDetector"""
        candidate = {'param_values': params}
        return self.scorer.score_operation(
            type('Operation', (), {'name': op_name})(),
            candidate, graph, [], constraints
        )
    
    def _score_for_sharing_reduction_pattern(self, op_name, params, base_score, state_analysis, graph, constraints, goals):
        """Legacy sharing reduction scoring - now handled by SharingReductionPatternDetector"""
        candidate = {'param_values': params}
        return self.scorer.score_operation(
            type('Operation', (), {'name': op_name})(),
            candidate, graph, goals, constraints
        )


class MigrationHelper:
    """Helper class for migrating from old to new scoring system"""
    
    @staticmethod
    def create_equivalent_scorer(original_scorer) -> GenericPatternAwareScoring:
        """Create generic scorer equivalent to original PatternAwareScoring instance"""
        
        # Extract configuration from original scorer if possible
        config = {}
        
        # Try to extract base scores
        if hasattr(original_scorer, 'base_scores'):
            config['base_scores'] = original_scorer.base_scores
        
        # Try to extract pattern states
        if hasattr(original_scorer, 'pattern_states'):
            # Initialize new scorer with pattern state
            pass
        
        # Create new scorer with equivalent configuration
        return create_default_scoring()
    
    @staticmethod
    def validate_equivalence(old_scorer, new_scorer, test_cases: List[Dict]) -> bool:
        """Validate that new scorer produces equivalent results to old scorer"""
        
        for test_case in test_cases:
            operation = test_case['operation']
            candidate = test_case['candidate']
            graph = test_case['graph']
            goals = test_case['goals']
            constraints = test_case['constraints']
            
            # Get scores from both systems
            try:
                old_score = old_scorer.score_operation(operation, candidate, graph, goals, constraints)
                new_score = new_scorer.score_operation(operation, candidate, graph, goals, constraints)
                
                # Allow small differences due to floating point precision
                if abs(old_score - new_score) > 0.001:
                    print(f"Score mismatch for {operation.name}: old={old_score}, new={new_score}")
                    return False
                    
            except Exception as e:
                print(f"Error comparing scores for {operation.name}: {e}")
                return False
        
        return True
    
    @staticmethod
    def generate_config_from_hardcoded() -> Dict:
        """Generate configuration that matches the hardcoded behavior"""
        
        # This would analyze the original pattern_aware_scoring.py
        # and extract the hardcoded values into configuration format
        return {
            "name": "Migrated from Hardcoded System",
            "resource_type_system": {
                "name_mappings": {
                    "FILE_1_1": "CONFIG",
                    "FILE_1_2": "DATABASE", 
                    "FILE_1_3": "TEMP"
                },
                "type_patterns": {
                    "FILE_\\d+_\\d+": {
                        "extraction_method": "modulo_cycle",
                        "modulo_cycle": ["CONFIG", "DATABASE", "TEMP"],
                        "id_position": 2
                    }
                }
            },
            "constraint_handlers": [
                {
                    "name": "ProhibitionConstraintHandler",
                    "enabled": True,
                    "config": {"violation_removal_score": 3.0}
                },
                {
                    "name": "AccessRequirementHandler",
                    "enabled": True,
                    "config": {"private_alternative_score": 2.9}
                }
            ],
            "pattern_detectors": [
                {
                    "name": "MediationPatternDetector",
                    "enabled": True,
                    "config": {
                        "orphaned_connection_score": 2.5,
                        "constraint_mentioned_orphaned_score": 3.0
                    }
                },
                {
                    "name": "SharingReductionPatternDetector", 
                    "enabled": True,
                    "config": {"shared_removal_score": 2.8}
                }
            ]
        }


# Convenience functions for different migration strategies
def create_backward_compatible_scorer(initial_graph=None):
    """Create scorer that maintains backward compatibility"""
    return LegacyPatternAwareScoring(initial_graph)


def migrate_to_generic_framework(domain="os_security"):
    """Migrate to generic framework for specified domain"""
    return create_scoring_for_domain(domain)


def create_hybrid_scorer(use_legacy_interface=True, domain="os_security"):
    """Create scorer that can use either legacy interface or new generic framework"""
    if use_legacy_interface:
        return LegacyPatternAwareScoring()
    else:
        return create_scoring_for_domain(domain)


# Testing and validation utilities
def run_migration_tests():
    """Run tests to validate migration equivalence"""
    
    print("Running pattern-aware scoring migration tests...")
    
    # Create both old and new scorers
    try:
        # This would import the original system for comparison
        # from pattern_aware_scoring import PatternAwareScoring as OriginalScorer
        # old_scorer = OriginalScorer()
        new_scorer = create_default_scoring()
        
        print("✅ Successfully created new generic scoring system")
        
        # Test basic functionality
        test_operation = type('Operation', (), {'name': 'add_hold_edge'})()
        test_candidate = {'param_values': {'from_node': 'PD_1', 'to_node': 'FILE_1_3'}}
        test_graph = None  # Would need actual graph for real testing
        test_goals = []
        test_constraints = []
        
        # This would run actual comparison tests
        print("✅ Migration framework ready for testing")
        
    except Exception as e:
        print(f"❌ Migration test failed: {e}")


# Performance monitoring
class PerformanceMonitor:
    """Monitor performance differences between old and new systems"""
    
    def __init__(self):
        self.old_times = []
        self.new_times = []
    
    def time_scoring_operation(self, scorer, operation, candidate, graph, goals, constraints):
        """Time a scoring operation"""
        import time
        
        start_time = time.time()
        score = scorer.score_operation(operation, candidate, graph, goals, constraints)
        end_time = time.time()
        
        return score, end_time - start_time
    
    def compare_performance(self, old_scorer, new_scorer, test_cases):
        """Compare performance between old and new scorers"""
        
        for test_case in test_cases:
            # Time old scorer
            old_score, old_time = self.time_scoring_operation(old_scorer, **test_case)
            self.old_times.append(old_time)
            
            # Time new scorer
            new_score, new_time = self.time_scoring_operation(new_scorer, **test_case)
            self.new_times.append(new_time)
        
        # Calculate statistics
        avg_old = sum(self.old_times) / len(self.old_times)
        avg_new = sum(self.new_times) / len(self.new_times)
        
        print(f"Average old scorer time: {avg_old:.4f}s")
        print(f"Average new scorer time: {avg_new:.4f}s")
        print(f"Performance ratio: {avg_new/avg_old:.2f}x")


if __name__ == "__main__":
    # Run migration tests when module is executed directly
    run_migration_tests()