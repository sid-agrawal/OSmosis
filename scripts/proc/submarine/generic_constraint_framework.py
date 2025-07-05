"""
Generic Constraint Framework for Pattern-Aware Scoring

This module provides a flexible, extensible framework for constraint handling
that replaces hardcoded constraint logic with pluggable handlers.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union


class ScoringContext:
    """Context information passed to constraint handlers and pattern detectors"""
    
    def __init__(self, graph, goals, resource_type_system, pattern_state):
        self.graph = graph
        self.goals = goals
        self.resource_type_system = resource_type_system
        self.pattern_state = pattern_state


class ConstraintHandler(ABC):
    """Base class for constraint-specific scoring logic"""
    
    @abstractmethod
    def applies_to(self, constraint) -> bool:
        """Return True if this handler can process the constraint"""
        pass
    
    @abstractmethod
    def score_operation(self, operation, params: Dict, graph, constraint, context: ScoringContext) -> Optional[float]:
        """Return score adjustment for this constraint, or None if no adjustment"""
        pass
    
    def get_priority_level(self) -> int:
        """Return priority tier (1=highest, 4=lowest)"""
        return 3  # Default to medium priority


class ProhibitionConstraintHandler(ConstraintHandler):
    """Handles any prohibition-type constraint (prohibit_direct_hold, etc.)"""
    
    def applies_to(self, constraint) -> bool:
        return hasattr(constraint, 'constraint_type') and constraint.constraint_type.startswith('prohibit_')
    
    def score_operation(self, operation, params: Dict, graph, constraint, context: ScoringContext) -> Optional[float]:
        if operation.name == "remove_hold_edge":
            if self._violates_prohibition(params, constraint):
                return 3.0  # Maximum priority for removing violations
        elif operation.name == "add_hold_edge":
            if self._would_violate_prohibition(params, constraint):
                return 0.0  # Block operations that would create violations
        return None
    
    def get_priority_level(self) -> int:
        return 1  # Highest priority
    
    def _violates_prohibition(self, params: Dict, constraint) -> bool:
        """Check if the operation removes a prohibited edge"""
        prohibited_pd = f"PD_{constraint.pd_id}"
        prohibited_resource = constraint.resource_info
        
        from_pd = params.get('from_node') or params.get('pd')
        to_resource = params.get('to_node') or params.get('resource')
        
        return (from_pd == prohibited_pd and to_resource == prohibited_resource)
    
    def _would_violate_prohibition(self, params: Dict, constraint) -> bool:
        """Check if the operation would create a prohibited edge"""
        return self._violates_prohibition(params, constraint)


class AccessRequirementHandler(ConstraintHandler):
    """Handles any access requirement constraint (requires_file_access, etc.)"""
    
    def applies_to(self, constraint) -> bool:
        return (hasattr(constraint, 'constraint_type') and 
                constraint.constraint_type.startswith('requires_') and 
                'access' in constraint.constraint_type)
    
    def score_operation(self, operation, params: Dict, graph, constraint, context: ScoringContext) -> Optional[float]:
        # Check if operation helps satisfy access requirements
        if operation.name == "add_hold_edge":
            if self._satisfies_access_requirement(params, constraint, context):
                # Check if this is a private alternative to shared resource
                if self._is_private_alternative(params, constraint, context):
                    return 2.9  # Very high priority for private alternatives
                else:
                    return 1.5  # Medium-high priority for requirement satisfaction
        
        elif operation.name == "add_request_edge":
            if self._enables_indirect_access(params, constraint, context):
                return 1.8  # High priority for indirect access
        
        return None
    
    def get_priority_level(self) -> int:
        return 2  # High priority
    
    def _satisfies_access_requirement(self, params: Dict, constraint, context: ScoringContext) -> bool:
        """Check if operation satisfies the access requirement"""
        pd = params.get('from_node') or params.get('pd')
        resource = params.get('to_node') or params.get('resource')
        
        # Check if this PD has this constraint
        if f"PD_{constraint.pd_id}" != pd:
            return False
        
        # Use resource type system to validate
        return context.resource_type_system.matches_requirement(resource, constraint)
    
    def _is_private_alternative(self, params: Dict, constraint, context: ScoringContext) -> bool:
        """Check if this creates a private alternative to a shared resource"""
        resource = params.get('to_node') or params.get('resource')
        
        # Check if resource is not shared and satisfies constraint
        if resource not in context.pattern_state.get('shared_resources', []):
            return self._satisfies_access_requirement(params, constraint, context)
        
        return False
    
    def _enables_indirect_access(self, params: Dict, constraint, context: ScoringContext) -> bool:
        """Check if REQUEST edge enables indirect access to required resources"""
        from_pd = params.get('from_pd') or params.get('from_node')
        to_pd = params.get('to_pd') or params.get('to_node')
        
        # Check if this connects a constrained PD to a potential mediator
        if f"PD_{constraint.pd_id}" == from_pd:
            # Check if to_pd has access to required resources
            return to_pd in context.pattern_state.get('potential_mediators', [])
        
        return False


class ExistenceConstraintHandler(ConstraintHandler):
    """Handles resource existence constraints (requires_resource_exists, etc.)"""
    
    def applies_to(self, constraint) -> bool:
        return (hasattr(constraint, 'constraint_type') and 
                'exists' in constraint.constraint_type)
    
    def score_operation(self, operation, params: Dict, graph, constraint, context: ScoringContext) -> Optional[float]:
        # Prevent removal of required resources
        if operation.name in ["remove_file_resource", "remove_resource_space"]:
            resource = params.get('resource') or params.get('to_node')
            if self._is_required_resource(resource, constraint):
                return 0.0  # Block removal of required resources
        
        # Boost creation of required resources
        elif operation.name in ["add_file_resource", "add_resource_space"]:
            if self._satisfies_existence_requirement(params, constraint, context):
                return 1.2  # Boost creation of required resources
        
        return None
    
    def get_priority_level(self) -> int:
        return 2  # High priority
    
    def _is_required_resource(self, resource: str, constraint) -> bool:
        """Check if resource is required by constraint"""
        return hasattr(constraint, 'resource_info') and constraint.resource_info == resource
    
    def _satisfies_existence_requirement(self, params: Dict, constraint, context: ScoringContext) -> bool:
        """Check if operation creates a required resource"""
        # Implementation depends on specific constraint structure
        return False  # Placeholder


class CommunicationConstraintHandler(ConstraintHandler):
    """Handles communication requirement constraints"""
    
    def applies_to(self, constraint) -> bool:
        return (hasattr(constraint, 'constraint_type') and 
                'communication' in constraint.constraint_type)
    
    def score_operation(self, operation, params: Dict, graph, constraint, context: ScoringContext) -> Optional[float]:
        if operation.name == "add_request_edge":
            if self._satisfies_communication_requirement(params, constraint):
                return 1.0  # Medium priority for communication
        return None
    
    def get_priority_level(self) -> int:
        return 3  # Medium priority
    
    def _satisfies_communication_requirement(self, params: Dict, constraint) -> bool:
        """Check if REQUEST edge satisfies communication requirement"""
        from_pd = params.get('from_pd') or params.get('from_node')
        to_pd = params.get('to_pd') or params.get('to_node')
        
        required_from = f"PD_{constraint.pd_id}"
        required_to = f"PD_{constraint.target_pd}" if hasattr(constraint, 'target_pd') else None
        
        return from_pd == required_from and (required_to is None or to_pd == required_to)


class DefaultConstraintHandlerRegistry:
    """Registry of default constraint handlers"""
    
    @staticmethod
    def get_default_handlers() -> List[ConstraintHandler]:
        """Return list of default constraint handlers"""
        return [
            ProhibitionConstraintHandler(),
            AccessRequirementHandler(),
            ExistenceConstraintHandler(),
            CommunicationConstraintHandler()
        ]