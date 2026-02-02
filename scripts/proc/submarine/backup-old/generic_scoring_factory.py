"""
Generic Scoring Factory

This module provides factory functions and configuration loading for creating
pattern-aware scoring systems with different configurations.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from generic_pattern_aware_scoring import GenericPatternAwareScoring
from generic_resource_type_system import ResourceTypeSystem
from generic_constraint_framework import (
    ConstraintHandler, ProhibitionConstraintHandler, AccessRequirementHandler,
    ExistenceConstraintHandler, CommunicationConstraintHandler
)
from generic_pattern_detectors import (
    PatternDetector, MediationPatternDetector, SharingReductionPatternDetector,
    IsolationViolationDetector, PrivilegeEscalationPreventionDetector
)


class ScoringConfigurationLoader:
    """Loads and manages scoring system configurations"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.handler_registry = self._build_handler_registry()
        self.detector_registry = self._build_detector_registry()
    
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        config_path = self.config_dir / config_file
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Warning: Config file {config_path} not found, using default")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {config_path}: {e}, using default")
            return self._get_default_config()
    
    def create_scoring_system(self, config: Dict) -> GenericPatternAwareScoring:
        """Create pattern-aware scoring system from configuration"""
        
        # Create resource type system
        resource_type_config = config.get('resource_type_system', {})
        resource_type_system = self._create_resource_type_system(resource_type_config)
        
        # Create constraint handlers
        constraint_handlers = self._create_constraint_handlers(
            config.get('constraint_handlers', [])
        )
        
        # Create pattern detectors
        pattern_detectors = self._create_pattern_detectors(
            config.get('pattern_detectors', [])
        )
        
        # Create scoring system
        return GenericPatternAwareScoring(
            resource_type_system=resource_type_system,
            constraint_handlers=constraint_handlers,
            pattern_detectors=pattern_detectors,
            config=config
        )
    
    def create_for_domain(self, domain: str, config_file: Optional[str] = None) -> GenericPatternAwareScoring:
        """Create scoring system configured for specific domain"""
        
        # Load base configuration
        if config_file:
            config = self.load_config(config_file)
        else:
            config = self.load_config("default_scoring_config.json")
        
        # Apply domain-specific settings
        domain_config = config.get('domains', {}).get(domain, {})
        if domain_config:
            config = self._apply_domain_config(config, domain_config)
        
        return self.create_scoring_system(config)
    
    def _create_resource_type_system(self, config: Dict) -> ResourceTypeSystem:
        """Create resource type system from configuration"""
        resource_system = ResourceTypeSystem()
        
        # Set type patterns
        if 'type_patterns' in config:
            resource_system.type_patterns = config['type_patterns']
        
        # Set name mappings  
        if 'name_mappings' in config:
            resource_system.name_mappings = config['name_mappings']
        
        # Set attribute extractors
        if 'attribute_extractors' in config:
            resource_system.attribute_extractors = config['attribute_extractors']
        
        return resource_system
    
    def _create_constraint_handlers(self, handler_configs: List[Dict]) -> List[ConstraintHandler]:
        """Create constraint handlers from configuration"""
        handlers = []
        
        for handler_config in handler_configs:
            if not handler_config.get('enabled', True):
                continue
            
            handler_name = handler_config['name']
            if handler_name in self.handler_registry:
                handler_class = self.handler_registry[handler_name]
                handler = handler_class()
                
                # Apply configuration to handler if it supports it
                if hasattr(handler, 'configure') and 'config' in handler_config:
                    handler.configure(handler_config['config'])
                
                handlers.append(handler)
            else:
                print(f"Warning: Unknown constraint handler: {handler_name}")
        
        return handlers
    
    def _create_pattern_detectors(self, detector_configs: List[Dict]) -> List[PatternDetector]:
        """Create pattern detectors from configuration"""
        detectors = []
        
        for detector_config in detector_configs:
            if not detector_config.get('enabled', True):
                continue
            
            detector_name = detector_config['name']
            if detector_name in self.detector_registry:
                detector_class = self.detector_registry[detector_name]
                detector = detector_class()
                
                # Apply configuration to detector if it supports it
                if hasattr(detector, 'configure') and 'config' in detector_config:
                    detector.configure(detector_config['config'])
                
                detectors.append(detector)
            else:
                print(f"Warning: Unknown pattern detector: {detector_name}")
        
        return detectors
    
    def _apply_domain_config(self, base_config: Dict, domain_config: Dict) -> Dict:
        """Apply domain-specific configuration overrides"""
        config = base_config.copy()
        
        # Filter constraint handlers
        enabled_constraints = domain_config.get('enabled_constraints', [])
        if enabled_constraints:
            filtered_handlers = []
            for handler in config.get('constraint_handlers', []):
                if handler['name'] in enabled_constraints:
                    filtered_handlers.append(handler)
            config['constraint_handlers'] = filtered_handlers
        
        # Filter pattern detectors
        enabled_patterns = domain_config.get('enabled_patterns', [])
        if enabled_patterns:
            filtered_detectors = []
            for detector in config.get('pattern_detectors', []):
                if detector['name'] in enabled_patterns:
                    filtered_detectors.append(detector)
            config['pattern_detectors'] = filtered_detectors
        
        return config
    
    def _build_handler_registry(self) -> Dict[str, type]:
        """Build registry of available constraint handlers"""
        return {
            'ProhibitionConstraintHandler': ProhibitionConstraintHandler,
            'AccessRequirementHandler': AccessRequirementHandler,
            'ExistenceConstraintHandler': ExistenceConstraintHandler,
            'CommunicationConstraintHandler': CommunicationConstraintHandler
        }
    
    def _build_detector_registry(self) -> Dict[str, type]:
        """Build registry of available pattern detectors"""
        return {
            'MediationPatternDetector': MediationPatternDetector,
            'SharingReductionPatternDetector': SharingReductionPatternDetector,
            'IsolationViolationDetector': IsolationViolationDetector,
            'PrivilegeEscalationPreventionDetector': PrivilegeEscalationPreventionDetector
        }
    
    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            "name": "Default Configuration",
            "resource_type_system": {},
            "constraint_handlers": [
                {"name": "ProhibitionConstraintHandler", "enabled": True, "priority_level": 1},
                {"name": "AccessRequirementHandler", "enabled": True, "priority_level": 2}
            ],
            "pattern_detectors": [
                {"name": "MediationPatternDetector", "enabled": True, "priority_level": 2},
                {"name": "SharingReductionPatternDetector", "enabled": True, "priority_level": 2}
            ],
            "scoring_policies": {
                "combination_method": "priority_override"
            },
            "base_scores": {}
        }


class ScoringSystemFactory:
    """Factory for creating preconfigured scoring systems"""
    
    def __init__(self, config_dir: str = "config"):
        self.loader = ScoringConfigurationLoader(config_dir)
    
    def create_default(self) -> GenericPatternAwareScoring:
        """Create default pattern-aware scoring system"""
        return self.loader.create_for_domain("os_security")
    
    def create_for_os_security(self) -> GenericPatternAwareScoring:
        """Create scoring system optimized for OS security scenarios"""
        return self.loader.create_for_domain("os_security")
    
    def create_for_network_security(self) -> GenericPatternAwareScoring:
        """Create scoring system optimized for network security scenarios"""
        return self.loader.create_for_domain("network_security")
    
    def create_for_privilege_separation(self) -> GenericPatternAwareScoring:
        """Create scoring system optimized for privilege separation scenarios"""
        return self.loader.create_for_domain("privilege_separation")
    
    def create_custom(self, config_file: str) -> GenericPatternAwareScoring:
        """Create scoring system from custom configuration file"""
        config = self.loader.load_config(config_file)
        return self.loader.create_scoring_system(config)
    
    def create_minimal(self) -> GenericPatternAwareScoring:
        """Create minimal scoring system with basic handlers only"""
        config = {
            "constraint_handlers": [
                {"name": "ProhibitionConstraintHandler", "enabled": True}
            ],
            "pattern_detectors": [
                {"name": "MediationPatternDetector", "enabled": True}
            ],
            "scoring_policies": {
                "combination_method": "priority_override"
            }
        }
        return self.loader.create_scoring_system(config)


# Convenience functions for common use cases
def create_default_scoring() -> GenericPatternAwareScoring:
    """Create default pattern-aware scoring system"""
    factory = ScoringSystemFactory()
    return factory.create_default()


def create_scoring_for_domain(domain: str) -> GenericPatternAwareScoring:
    """Create scoring system for specific domain"""
    factory = ScoringSystemFactory()
    return factory.loader.create_for_domain(domain)


def create_scoring_from_config(config_file: str) -> GenericPatternAwareScoring:
    """Create scoring system from configuration file"""
    factory = ScoringSystemFactory()
    return factory.create_custom(config_file)


# Integration helper for existing code
def get_pattern_aware_score(transition, candidate, graph, goals, constraints, initial_graph=None):
    """
    Drop-in replacement for existing pattern_aware_scoring.get_pattern_aware_score
    Uses the generic framework with default configuration
    """
    # Create default scoring system (cached for performance)
    if not hasattr(get_pattern_aware_score, '_cached_scorer'):
        get_pattern_aware_score._cached_scorer = create_default_scoring()
    
    scorer = get_pattern_aware_score._cached_scorer
    return scorer.score_operation(transition, candidate, graph, goals, constraints)


# Configuration validation
def validate_config(config_file: str) -> tuple[bool, List[str]]:
    """Validate a scoring configuration file"""
    loader = ScoringConfigurationLoader()
    
    try:
        config = loader.load_config(config_file)
        errors = []
        
        # Check required sections
        required_sections = ['constraint_handlers', 'pattern_detectors']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        # Validate handler names
        if 'constraint_handlers' in config:
            for handler in config['constraint_handlers']:
                if 'name' not in handler:
                    errors.append("Constraint handler missing 'name' field")
                elif handler['name'] not in loader.handler_registry:
                    errors.append(f"Unknown constraint handler: {handler['name']}")
        
        # Validate detector names
        if 'pattern_detectors' in config:
            for detector in config['pattern_detectors']:
                if 'name' not in detector:
                    errors.append("Pattern detector missing 'name' field")
                elif detector['name'] not in loader.detector_registry:
                    errors.append(f"Unknown pattern detector: {detector['name']}")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        return False, [f"Configuration validation error: {str(e)}"]