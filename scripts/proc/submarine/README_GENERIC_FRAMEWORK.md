# Generic Pattern-Aware Scoring Framework

This document describes the new generic pattern-aware scoring framework that replaces the hardcoded constraint and pattern logic with a flexible, extensible system.

## Overview

The generic framework transforms the submarine scoring system from hardcoded logic to a configurable, plugin-based architecture while maintaining the same intelligent scoring behavior and backward compatibility.

### Key Benefits

- **Extensibility**: Add new constraint types and patterns without modifying core code
- **Configurability**: Change scoring behavior through JSON configuration files
- **Reusability**: Same framework works for different domains (OS security, network security, etc.)
- **Maintainability**: Clean separation of concerns, easier testing and debugging
- **Backward Compatibility**: Drop-in replacement for existing pattern_aware_scoring.py

## Framework Components

### Core Modules

1. **`generic_constraint_framework.py`** - Pluggable constraint handlers
2. **`generic_resource_type_system.py`** - Configurable resource type inference
3. **`generic_pattern_detectors.py`** - Extensible pattern detection
4. **`generic_pattern_aware_scoring.py`** - Main scoring engine
5. **`generic_scoring_factory.py`** - Configuration loading and factory methods

### Integration Modules

6. **`pattern_aware_scoring_v2.py`** - Backward compatibility layer
7. **`scoring_integration_patch.py`** - Integration with existing isosearch.py

### Configuration and Demo

8. **`config/default_scoring_config.json`** - Default configuration
9. **`demo_generic_framework.py`** - Comprehensive demonstration

## Quick Start

### Basic Usage

```python
# Create default scoring system
from generic_scoring_factory import create_default_scoring
scorer = create_default_scoring()

# Use in existing code (drop-in replacement)
score = scorer.score_operation(operation, candidate, graph, goals, constraints)
```

### Domain-Specific Usage

```python
# Create scoring system for specific domain
from generic_scoring_factory import create_scoring_for_domain

os_scorer = create_scoring_for_domain("os_security")
network_scorer = create_scoring_for_domain("network_security")
```

### Integration with Existing Code

```python
# Enable generic framework in existing isosearch.py
from scoring_integration_patch import enable_generic_scoring
enable_generic_scoring("os_security")

# Now isosearch.py will use the generic framework automatically
```

## Architecture

### Constraint Handlers

The framework includes pluggable constraint handlers:

- **ProhibitionConstraintHandler**: Handles `prohibit_*` constraints
- **AccessRequirementHandler**: Handles `requires_*_access` constraints  
- **ExistenceConstraintHandler**: Handles `requires_*_exists` constraints
- **CommunicationConstraintHandler**: Handles communication requirements

### Pattern Detectors

Pattern detectors identify and score security patterns:

- **MediationPatternDetector**: Detects mediation opportunities
- **SharingReductionPatternDetector**: Identifies sharing reduction patterns
- **IsolationViolationDetector**: Detects isolation improvements
- **PrivilegeEscalationPreventionDetector**: Prevents privilege escalation

### Resource Type System

Configurable resource type inference:

```python
# Pattern-based inference
"FILE_\\d+_\\d+": {
  "extraction_method": "modulo_cycle",
  "modulo_cycle": ["CONFIG", "DATABASE", "TEMP"],
  "id_position": 2
}

# Direct name mappings
"FILE_1_3": "TEMP"
```

## Configuration

### Configuration Structure

```json
{
  "resource_type_system": {
    "type_patterns": { ... },
    "name_mappings": { ... }
  },
  "constraint_handlers": [
    {
      "name": "ProhibitionConstraintHandler",
      "enabled": true,
      "priority_level": 1,
      "config": { "violation_removal_score": 3.0 }
    }
  ],
  "pattern_detectors": [
    {
      "name": "MediationPatternDetector", 
      "enabled": true,
      "priority_level": 2,
      "config": { "orphaned_connection_score": 2.5 }
    }
  ],
  "scoring_policies": {
    "combination_method": "priority_override"
  }
}
```

### Scoring Combination Methods

- **priority_override**: Highest priority score wins (default, matches original behavior)
- **weighted_sum**: Weighted combination of constraint, pattern, and base scores
- **maximum**: Take maximum of all scores

## Extensibility

### Creating Custom Constraint Handlers

```python
from generic_constraint_framework import ConstraintHandler

class CustomConstraintHandler(ConstraintHandler):
    def applies_to(self, constraint):
        return constraint.constraint_type == "custom_constraint"
    
    def score_operation(self, operation, params, graph, constraint, context):
        if operation.name == "custom_operation":
            return 2.5  # Custom scoring logic
        return None
```

### Creating Custom Pattern Detectors

```python
from generic_pattern_detectors import PatternDetector

class CustomPatternDetector(PatternDetector):
    def is_active(self, context):
        return len(context.pattern_state['custom_condition']) > 0
    
    def score_operation(self, operation, candidate, context):
        if operation.name == "relevant_operation":
            return 1.8  # Pattern-specific scoring
        return None
```

### Adding to Configuration

```json
{
  "constraint_handlers": [
    {
      "name": "CustomConstraintHandler",
      "enabled": true,
      "priority_level": 2
    }
  ],
  "pattern_detectors": [
    {
      "name": "CustomPatternDetector",
      "enabled": true,
      "priority_level": 3
    }
  ]
}
```

## Migration Guide

### Step 1: Basic Migration

Replace existing pattern_aware_scoring imports:

```python
# Old way
from pattern_aware_scoring import get_pattern_aware_score

# New way  
from pattern_aware_scoring_v2 import get_pattern_aware_score
```

### Step 2: Enable Generic Framework

```python
# Enable for entire session
from scoring_integration_patch import enable_generic_scoring
enable_generic_scoring("os_security")
```

### Step 3: Custom Configuration

1. Copy `config/default_scoring_config.json` to your custom config
2. Modify handlers, detectors, and scoring policies as needed
3. Load with custom configuration:

```python
from generic_scoring_factory import create_scoring_from_config
scorer = create_scoring_from_config("my_custom_config.json")
```

## Performance

The generic framework maintains performance through:

- **Efficient caching**: Pattern state and resource type inference caching
- **Early filtering**: Constraint handlers filter by `applies_to()` before scoring
- **Lazy evaluation**: Pattern detectors only activate when relevant
- **Optimized algorithms**: Same core algorithms as original system

## Debugging and Validation

### Scoring Explanations

```python
explanation = scorer.get_scoring_explanation(operation, candidate, graph, goals, constraints)
print(f"Final score: {explanation['final_score']}")
print(f"Active patterns: {explanation['active_patterns']}")
print(f"Constraint scores: {explanation['constraint_scores']}")
```

### Configuration Validation

```python
from generic_scoring_factory import validate_config
valid, errors = validate_config("my_config.json")
if not valid:
    print(f"Configuration errors: {errors}")
```

## Testing

Run the comprehensive demo:

```bash
python demo_generic_framework.py
```

Run integration tests:

```bash
python scoring_integration_patch.py
```

## Comparison: Old vs New

| Aspect | Old System | New System |
|--------|------------|------------|
| **Constraint Types** | Hardcoded in `_is_prohibited_edge()` | Pluggable handlers |
| **Resource Types** | Hardcoded FILE_1_X mappings | Configurable patterns |
| **Pattern Detection** | Embedded in scoring function | Separate detector classes |
| **Extensibility** | Requires core code changes | Configuration-driven |
| **Testing** | Difficult to isolate components | Individual component testing |
| **Debugging** | Limited visibility | Detailed explanations |
| **Reusability** | OS security specific | Multi-domain support |

## Future Extensions

The framework enables easy addition of:

- **New domains**: Network security, IoT security, cloud security
- **Advanced patterns**: Delegation chains, capability systems, defense-in-depth
- **Complex constraints**: Temporal constraints, conditional constraints
- **Multi-objective optimization**: Pareto-optimal scoring
- **Machine learning integration**: Learned pattern recognition

## Files Overview

```
submarine/
├── generic_constraint_framework.py     # Base constraint handler framework
├── generic_resource_type_system.py     # Configurable resource type system  
├── generic_pattern_detectors.py        # Pattern detection framework
├── generic_pattern_aware_scoring.py    # Main scoring engine
├── generic_scoring_factory.py          # Configuration and factory
├── pattern_aware_scoring_v2.py         # Backward compatibility
├── scoring_integration_patch.py        # Integration with existing code
├── demo_generic_framework.py           # Comprehensive demo
├── config/
│   └── default_scoring_config.json     # Default configuration
└── README_GENERIC_FRAMEWORK.md         # This documentation
```

## Support

For questions, issues, or contributions related to the generic framework:

1. Review the demo script for comprehensive examples
2. Check configuration validation for common issues  
3. Use scoring explanations for debugging unexpected behavior
4. Test custom components with the migration helper utilities

The framework maintains full backward compatibility while providing a foundation for future extensions and improvements to the pattern-aware scoring system.