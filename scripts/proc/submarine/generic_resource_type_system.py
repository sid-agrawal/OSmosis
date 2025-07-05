"""
Generic Resource Type System

This module provides configurable resource type inference and matching,
replacing hardcoded resource type mappings with flexible configuration.
"""

import json
import re
from typing import Dict, List, Optional, Any, Union
from pathlib import Path


class ResourceTypeSystem:
    """Configurable resource type inference and matching system"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.type_patterns: Dict[str, Dict] = {}
        self.name_mappings: Dict[str, str] = {}
        self.attribute_extractors: Dict[str, str] = {}
        self.default_config_loaded = False
        
        if config_file:
            self.load_config(config_file)
        else:
            self.load_default_config()
    
    def load_config(self, config_file: str):
        """Load resource type configuration from file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Pattern-based type inference
            self.type_patterns = config.get('type_patterns', {})
            # Direct name mappings
            self.name_mappings = config.get('name_mappings', {})
            # Attribute extraction rules
            self.attribute_extractors = config.get('attribute_extractors', {})
            
            print(f"Loaded resource type configuration from {config_file}")
        except FileNotFoundError:
            print(f"Warning: Config file {config_file} not found, using default configuration")
            self.load_default_config()
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {config_file}: {e}, using default configuration")
            self.load_default_config()
    
    def load_default_config(self):
        """Load default resource type configuration matching current system"""
        if self.default_config_loaded:
            return
            
        # Default configuration that matches current hardcoded behavior
        self.type_patterns = {
            r"FILE_\d+_\d+": {
                "extraction_method": "modulo_cycle",
                "modulo_cycle": ["CONFIG", "DATABASE", "TEMP"],
                "id_position": 2,  # Position of ID in split('_')
                "default_type": "FILE"
            },
            r"MEMORY_\d+_\d+": {
                "extraction_method": "modulo_cycle", 
                "modulo_cycle": ["HEAP", "STACK", "SHARED"],
                "id_position": 2,
                "default_type": "MEMORY"
            },
            r"NETWORK_\d+_\d+": {
                "extraction_method": "modulo_cycle",
                "modulo_cycle": ["TCP", "UDP", "SOCKET"],
                "id_position": 2,
                "default_type": "NETWORK"
            }
        }
        
        # Direct name mappings for specific resources
        self.name_mappings = {
            "FILE_1_1": "CONFIG",
            "FILE_1_2": "DATABASE", 
            "FILE_1_3": "TEMP",
            "SPECIAL_CONFIG": "CONFIG",
            "SYSTEM_DATABASE": "DATABASE"
        }
        
        # Attribute extraction methods
        self.attribute_extractors = {
            "size_kb": "extract_from_graph_metadata",
            "permissions": "extract_from_edge_properties",
            "file_type": "extract_from_type_inference"
        }
        
        self.default_config_loaded = True
    
    def infer_type(self, resource_name: str, graph_context=None) -> str:
        """Infer resource type using configured rules"""
        
        # Try direct name mapping first (highest priority)
        if resource_name in self.name_mappings:
            return self.name_mappings[resource_name]
        
        # Try pattern matching
        for pattern, type_info in self.type_patterns.items():
            if self._matches_pattern(resource_name, pattern):
                return self._extract_type(resource_name, type_info)
        
        # Try graph context analysis if available
        if graph_context:
            return self._infer_from_context(resource_name, graph_context)
        
        return 'UNKNOWN'
    
    def matches_requirement(self, resource_name: str, constraint) -> bool:
        """Check if resource matches constraint requirement"""
        resource_type = self.infer_type(resource_name)
        
        # Extract required type from constraint
        required_type = self._extract_required_type(constraint)
        if not required_type:
            return False
        
        return resource_type.upper() == required_type.upper()
    
    def provides_alternative(self, pd: str, resource: str, context) -> bool:
        """Check if resource provides alternative that satisfies constraints"""
        # Find constraints for this PD
        pd_constraints = self._get_pd_constraints(pd, context)
        
        for constraint in pd_constraints:
            if self.matches_requirement(resource, constraint):
                # Check if there's a shared resource of same type
                resource_type = self.infer_type(resource)
                shared_resources = context.pattern_state.get('shared_resources', [])
                
                for shared_resource in shared_resources:
                    if self.infer_type(shared_resource) == resource_type:
                        return True  # This is a private alternative
        
        return False
    
    def get_resources_by_type(self, graph, resource_type: str) -> List[str]:
        """Get all resources of specified type from graph"""
        resources = []
        
        # Get all resource nodes from graph
        for node, data in graph.g.nodes(data=True):
            if data.get('type') == 'RESOURCE':
                if self.infer_type(node).upper() == resource_type.upper():
                    resources.append(node)
        
        return resources
    
    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches pattern (regex)"""
        try:
            return bool(re.match(pattern, name))
        except re.error:
            return False
    
    def _extract_type(self, name: str, type_info: Dict) -> str:
        """Extract type using configured extraction logic"""
        extraction_method = type_info.get('extraction_method', 'modulo_cycle')
        
        if extraction_method == 'modulo_cycle':
            return self._extract_modulo_cycle(name, type_info)
        elif extraction_method == 'direct_mapping':
            return type_info.get('type', type_info.get('default_type', 'UNKNOWN'))
        elif extraction_method == 'regex_capture':
            return self._extract_regex_capture(name, type_info)
        else:
            return type_info.get('default_type', 'UNKNOWN')
    
    def _extract_modulo_cycle(self, name: str, type_info: Dict) -> str:
        """Extract type using modulo cycle logic"""
        try:
            parts = name.split('_')
            id_position = type_info.get('id_position', 2)
            
            if len(parts) > id_position:
                resource_id = int(parts[id_position])
                cycle = type_info.get('modulo_cycle', [])
                
                if cycle:
                    return cycle[(resource_id - 1) % len(cycle)]
        except (ValueError, IndexError):
            pass
        
        return type_info.get('default_type', 'UNKNOWN')
    
    def _extract_regex_capture(self, name: str, type_info: Dict) -> str:
        """Extract type using regex capture groups"""
        pattern = type_info.get('capture_pattern')
        if not pattern:
            return type_info.get('default_type', 'UNKNOWN')
        
        try:
            match = re.match(pattern, name)
            if match:
                capture_group = type_info.get('capture_group', 1)
                return match.group(capture_group)
        except (re.error, IndexError):
            pass
        
        return type_info.get('default_type', 'UNKNOWN')
    
    def _infer_from_context(self, resource_name: str, graph_context) -> str:
        """Infer type from graph context (edges, metadata, etc.)"""
        # Analyze edges and metadata to infer type
        # This is a placeholder for more sophisticated context analysis
        
        # Check edge properties for type hints
        for from_node, to_node, edge_data in graph_context.g.edges(data=True):
            if to_node == resource_name:
                edge_type = edge_data.get('resource_type')
                if edge_type:
                    return edge_type.upper()
        
        # Check node metadata
        node_data = graph_context.g.nodes.get(resource_name, {})
        metadata_type = node_data.get('inferred_type') or node_data.get('resource_type')
        if metadata_type:
            return metadata_type.upper()
        
        return 'UNKNOWN'
    
    def _extract_required_type(self, constraint) -> Optional[str]:
        """Extract required type from constraint"""
        # Check constraint properties
        if hasattr(constraint, 'properties') and constraint.properties:
            return constraint.properties.get('file_type') or constraint.properties.get('resource_type')
        
        # Check constraint resource_info
        if hasattr(constraint, 'resource_info') and isinstance(constraint.resource_info, str):
            # Try to extract type from resource_info if it's a type name
            if constraint.resource_info.upper() in ['CONFIG', 'DATABASE', 'TEMP', 'FILE', 'MEMORY', 'NETWORK']:
                return constraint.resource_info.upper()
        
        return None
    
    def _get_pd_constraints(self, pd: str, context) -> List:
        """Get constraints that apply to specified PD"""
        pd_constraints = []
        
        # Extract PD ID from name (e.g., "PD_1" -> 1)
        try:
            pd_id = int(pd.split('_')[1])
        except (ValueError, IndexError):
            return pd_constraints
        
        # Find constraints for this PD
        for goal in context.goals:
            # Goals aren't constraints, but included for completeness
            pass
        
        # This would be passed in context in real implementation
        # For now, return empty list
        return pd_constraints
    
    def save_config(self, config_file: str):
        """Save current configuration to file"""
        config = {
            'type_patterns': self.type_patterns,
            'name_mappings': self.name_mappings,
            'attribute_extractors': self.attribute_extractors
        }
        
        # Ensure directory exists
        Path(config_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"Saved resource type configuration to {config_file}")
    
    def add_type_pattern(self, pattern: str, config: Dict):
        """Add a new type pattern"""
        self.type_patterns[pattern] = config
    
    def add_name_mapping(self, name: str, type_name: str):
        """Add a direct name-to-type mapping"""
        self.name_mappings[name] = type_name
    
    def get_supported_types(self) -> List[str]:
        """Get list of all supported resource types"""
        types = set()
        
        # From name mappings
        types.update(self.name_mappings.values())
        
        # From pattern configurations
        for pattern_config in self.type_patterns.values():
            if 'modulo_cycle' in pattern_config:
                types.update(pattern_config['modulo_cycle'])
            if 'default_type' in pattern_config:
                types.add(pattern_config['default_type'])
        
        return sorted(list(types))


# Convenience function for creating default resource type system
def create_default_resource_type_system() -> ResourceTypeSystem:
    """Create a resource type system with default configuration"""
    return ResourceTypeSystem()


# Configuration generator for common scenarios
def generate_config_for_scenario(scenario_name: str) -> Dict:
    """Generate resource type configuration for common scenarios"""
    
    if scenario_name == "os_security":
        return {
            "type_patterns": {
                r"FILE_\d+_\d+": {
                    "extraction_method": "modulo_cycle",
                    "modulo_cycle": ["CONFIG", "DATABASE", "TEMP"],
                    "id_position": 2,
                    "default_type": "FILE"
                },
                r"MEMORY_\d+_\d+": {
                    "extraction_method": "modulo_cycle",
                    "modulo_cycle": ["HEAP", "STACK", "SHARED"],
                    "id_position": 2,
                    "default_type": "MEMORY"
                }
            },
            "name_mappings": {
                "FILE_1_3": "TEMP",
                "SYSTEM_CONFIG": "CONFIG"
            }
        }
    
    elif scenario_name == "network_security":
        return {
            "type_patterns": {
                r"PORT_\d+": {
                    "extraction_method": "regex_capture",
                    "capture_pattern": r"PORT_(\d+)",
                    "capture_group": 1,
                    "default_type": "NETWORK"
                },
                r"SOCKET_\d+_\d+": {
                    "extraction_method": "modulo_cycle",
                    "modulo_cycle": ["TCP", "UDP", "UNIX"],
                    "id_position": 2,
                    "default_type": "SOCKET"
                }
            }
        }
    
    else:
        # Return default configuration
        return create_default_resource_type_system().type_patterns