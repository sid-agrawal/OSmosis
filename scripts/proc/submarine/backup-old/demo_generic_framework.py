"""
Generic Framework Demonstration

This script demonstrates the capabilities of the new generic pattern-aware
scoring framework and shows how it replaces the hardcoded system.
"""

import json
from pathlib import Path

# Import the new framework components
from generic_scoring_factory import (
    create_default_scoring, create_scoring_for_domain, 
    ScoringSystemFactory, validate_config
)
from generic_resource_type_system import ResourceTypeSystem
from generic_constraint_framework import (
    ProhibitionConstraintHandler, AccessRequirementHandler
)
from generic_pattern_detectors import (
    MediationPatternDetector, SharingReductionPatternDetector
)
from scoring_integration_patch import enable_generic_scoring, get_integration_status


def demo_basic_usage():
    """Demonstrate basic usage of the generic framework"""
    
    print("=== Generic Framework Basic Usage Demo ===\n")
    
    # 1. Create default scoring system
    print("1. Creating default scoring system...")
    scorer = create_default_scoring()
    print(f"   ✅ Created scorer with {len(scorer.constraint_handlers)} constraint handlers")
    print(f"   ✅ Created scorer with {len(scorer.pattern_detectors)} pattern detectors")
    
    # 2. Create domain-specific scoring systems
    print("\n2. Creating domain-specific scoring systems...")
    
    os_scorer = create_scoring_for_domain("os_security")
    print(f"   ✅ OS Security scorer: {len(os_scorer.pattern_detectors)} detectors")
    
    network_scorer = create_scoring_for_domain("network_security") 
    print(f"   ✅ Network Security scorer: {len(network_scorer.pattern_detectors)} detectors")
    
    # 3. Demonstrate resource type system
    print("\n3. Testing resource type system...")
    resource_system = scorer.resource_type_system
    
    test_resources = ["FILE_1_1", "FILE_1_2", "FILE_1_3", "MEMORY_2_1", "UNKNOWN_RESOURCE"]
    for resource in test_resources:
        resource_type = resource_system.infer_type(resource)
        print(f"   {resource} → {resource_type}")


def demo_configuration_system():
    """Demonstrate the configuration system"""
    
    print("\n=== Configuration System Demo ===\n")
    
    # 1. Load and validate default configuration
    print("1. Loading default configuration...")
    factory = ScoringSystemFactory()
    
    config_valid, errors = validate_config("default_scoring_config.json")
    if config_valid:
        print("   ✅ Default configuration is valid")
    else:
        print(f"   ❌ Configuration errors: {errors}")
    
    # 2. Create custom configuration
    print("\n2. Creating custom configuration...")
    custom_config = {
        "name": "Custom Demo Configuration",
        "constraint_handlers": [
            {
                "name": "ProhibitionConstraintHandler",
                "enabled": True,
                "priority_level": 1,
                "config": {"violation_removal_score": 5.0}  # Higher than default
            }
        ],
        "pattern_detectors": [
            {
                "name": "MediationPatternDetector", 
                "enabled": True,
                "priority_level": 2,
                "config": {"mediator_creation_score": 2.0}  # Higher than default
            }
        ],
        "scoring_policies": {
            "combination_method": "weighted_sum",
            "weights": {"constraint": 0.8, "pattern": 0.2}
        }
    }
    
    # Save custom configuration
    config_path = Path("config/custom_demo_config.json")
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(custom_config, f, indent=2)
    
    print(f"   ✅ Saved custom configuration to {config_path}")
    
    # 3. Create scorer from custom configuration
    custom_scorer = factory.create_custom("custom_demo_config.json")
    print(f"   ✅ Created custom scorer with {len(custom_scorer.constraint_handlers)} handlers")


def demo_extensibility():
    """Demonstrate how to extend the framework"""
    
    print("\n=== Extensibility Demo ===\n")
    
    # 1. Create custom constraint handler
    print("1. Creating custom constraint handler...")
    
    from generic_constraint_framework import ConstraintHandler
    
    class CustomSecurityHandler(ConstraintHandler):
        """Custom handler for demonstration"""
        
        def applies_to(self, constraint):
            return hasattr(constraint, 'constraint_type') and 'security_level' in constraint.constraint_type
        
        def score_operation(self, operation, params, graph, constraint, context):
            if operation.name == "add_pd":
                return 1.5  # Boost PD creation for security constraints
            return None
        
        def get_priority_level(self):
            return 1  # High priority
    
    # 2. Create custom pattern detector
    print("2. Creating custom pattern detector...")
    
    from generic_pattern_detectors import PatternDetector
    
    class CustomEncryptionPatternDetector(PatternDetector):
        """Custom detector for demonstration"""
        
        def is_active(self, context):
            # Active if any goals mention encryption
            return any('encrypt' in str(goal).lower() for goal in context.goals)
        
        def score_operation(self, operation, candidate, context):
            if operation.name == "add_file_resource":
                return 2.0  # Boost encrypted resource creation
            return None
    
    # 3. Create scorer with custom components
    print("3. Creating scorer with custom components...")
    
    from generic_pattern_aware_scoring import GenericPatternAwareScoring
    
    custom_handlers = [CustomSecurityHandler(), ProhibitionConstraintHandler()]
    custom_detectors = [CustomEncryptionPatternDetector(), MediationPatternDetector()]
    
    custom_scorer = GenericPatternAwareScoring(
        constraint_handlers=custom_handlers,
        pattern_detectors=custom_detectors
    )
    
    print(f"   ✅ Created scorer with custom components")
    print(f"   📋 Handlers: {[h.__class__.__name__ for h in custom_handlers]}")
    print(f"   📋 Detectors: {[d.__class__.__name__ for d in custom_detectors]}")


def demo_integration():
    """Demonstrate integration with existing code"""
    
    print("\n=== Integration Demo ===\n")
    
    # 1. Show integration status
    print("1. Current integration status:")
    status = get_integration_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # 2. Enable generic scoring
    print("\n2. Enabling generic scoring framework...")
    enable_generic_scoring("os_security")
    
    new_status = get_integration_status()
    print(f"   ✅ Generic scoring enabled: {new_status['using_generic']}")
    print(f"   📋 Domain: {new_status['domain']}")
    
    # 3. Test scoring with mock data
    print("\n3. Testing scoring with mock data...")
    
    # This would use actual graph data in real scenario
    print("   ⚠️  Mock scoring test (requires actual graph data for real results)")


def demo_performance_features():
    """Demonstrate performance and debugging features"""
    
    print("\n=== Performance and Debugging Demo ===\n")
    
    # 1. Scoring explanation
    print("1. Demonstrating scoring explanation...")
    
    scorer = create_default_scoring()
    
    # Mock objects for demonstration
    class MockOperation:
        def __init__(self, name):
            self.name = name
    
    class MockGraph:
        def __init__(self):
            self.g = type('Graph', (), {'nodes': lambda data=False: [], 'edges': lambda data=False: []})()
    
    operation = MockOperation("add_hold_edge")
    candidate = {'param_values': {'from_node': 'PD_1', 'to_node': 'FILE_1_3'}}
    graph = MockGraph()
    goals = []
    constraints = []
    
    try:
        explanation = scorer.get_scoring_explanation(operation, candidate, graph, goals, constraints)
        print(f"   ✅ Final score: {explanation['final_score']}")
        print(f"   📋 Base score: {explanation['base_score']}")
        print(f"   📋 Combination method: {explanation['combination_method']}")
        print(f"   📋 Active patterns: {explanation['active_patterns']}")
    except Exception as e:
        print(f"   ⚠️  Explanation demo requires actual graph: {e}")
    
    # 2. Configuration validation
    print("\n2. Configuration validation demo...")
    
    valid, errors = validate_config("default_scoring_config.json")
    if valid:
        print("   ✅ Configuration validation passed")
    else:
        print(f"   ❌ Validation errors: {errors}")


def demo_migration_benefits():
    """Show the benefits of the new framework"""
    
    print("\n=== Migration Benefits Summary ===\n")
    
    benefits = [
        "✅ Extensibility: Add new constraint types without modifying core code",
        "✅ Configurability: Change scoring behavior through configuration files", 
        "✅ Reusability: Same framework works for different domains (OS, network, etc.)",
        "✅ Maintainability: Clean separation of concerns, easier testing",
        "✅ Debuggability: Detailed scoring explanations and validation",
        "✅ Backward Compatibility: Drop-in replacement for existing code",
        "✅ Performance: Efficient caching and optimized algorithms",
        "✅ Flexibility: Multiple scoring combination methods (priority, weighted, max)"
    ]
    
    print("Key benefits of the generic framework:")
    for benefit in benefits:
        print(f"  {benefit}")
    
    print("\nFramework components:")
    print("  📦 generic_constraint_framework.py - Pluggable constraint handlers")
    print("  📦 generic_resource_type_system.py - Configurable resource type inference")
    print("  📦 generic_pattern_detectors.py - Extensible pattern detection")
    print("  📦 generic_pattern_aware_scoring.py - Main scoring engine")
    print("  📦 generic_scoring_factory.py - Configuration loading and factory")
    print("  📦 pattern_aware_scoring_v2.py - Backward compatibility layer")
    print("  📦 scoring_integration_patch.py - Integration with existing code")


def run_full_demo():
    """Run complete demonstration of the framework"""
    
    print("🚀 Generic Pattern-Aware Scoring Framework Demo")
    print("=" * 60)
    
    try:
        demo_basic_usage()
        demo_configuration_system()
        demo_extensibility()
        demo_integration()
        demo_performance_features()
        demo_migration_benefits()
        
        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("1. Review the generated configuration files in config/")
        print("2. Try creating custom constraint handlers and pattern detectors")
        print("3. Integrate with your existing isosearch scenarios")
        print("4. Monitor performance and adjust configurations as needed")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_full_demo()