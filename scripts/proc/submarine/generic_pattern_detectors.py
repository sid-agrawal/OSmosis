"""
Generic Pattern Detection Framework

This module provides a flexible framework for detecting and scoring
security patterns, replacing hardcoded pattern logic with configurable detectors.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union


class PatternDetector(ABC):
    """Base class for pattern detection and scoring"""
    
    @abstractmethod
    def is_active(self, context) -> bool:
        """Return True if this pattern is relevant to current state"""
        pass
    
    @abstractmethod
    def score_operation(self, operation, candidate: Dict, context) -> Optional[float]:
        """Return score for operation if it helps this pattern, None otherwise"""
        pass
    
    def get_pattern_name(self) -> str:
        """Return name of this pattern for logging/debugging"""
        return self.__class__.__name__
    
    def get_priority_level(self) -> int:
        """Return priority level for pattern scoring (1=highest, 4=lowest)"""
        return 2  # Default to high priority


class MediationPatternDetector(PatternDetector):
    """Detects and scores mediation patterns"""
    
    def is_active(self, context) -> bool:
        """Mediation is active when orphaned resources exist or sharing needs reduction"""
        pattern_state = context.pattern_state
        
        # Active if orphaned resources exist
        if pattern_state.get('orphaned_resources'):
            return True
        
        # Active if shared resources exist and we have goals that benefit from mediation
        if pattern_state.get('shared_resources'):
            # Check for goals that benefit from mediation (RSI reduction, TCB reduction)
            for goal in context.goals:
                if goal.metric_name in ['RSI', 'TCB']:
                    return True
        
        return False
    
    def score_operation(self, operation, candidate: Dict, context) -> Optional[float]:
        """Score operations that contribute to mediation patterns"""
        pattern_state = context.pattern_state
        orphaned_resources = pattern_state.get('orphaned_resources', [])
        potential_mediators = pattern_state.get('potential_mediators', [])
        
        # Phase 1: Infrastructure creation when orphaned resources exist
        if operation.name == "add_pd" and orphaned_resources:
            return 1.5  # Boost PD creation as potential mediator
        
        # Phase 2: Connect mediators to orphaned resources
        if operation.name == "add_hold_edge":
            to_resource = candidate.get('to_node') or candidate.get('resource')
            from_pd = candidate.get('from_node') or candidate.get('pd')
            
            if to_resource in orphaned_resources:
                # Check if connecting PD could be a mediator
                if self._could_be_mediator(from_pd, context):
                    # Extra boost if resource is constraint-mentioned
                    if self._is_constraint_mentioned(to_resource, context):
                        return 3.0  # Maximum priority for constraint-required resources
                    else:
                        return 2.5  # High priority for orphaned resources
        
        # Phase 3: Complete mediation with REQUEST edges
        if operation.name == "add_request_edge":
            if self._completes_mediation_pattern(candidate, context):
                return 1.8  # High priority for completing mediation
        
        # Phase 4: Remove shared edges to create orphaned resources
        if operation.name == "remove_hold_edge":
            to_resource = candidate.get('to_node') or candidate.get('resource')
            if self._is_shared_resource(to_resource, context):
                return 1.0  # Medium priority for creating mediation opportunities
        
        return None
    
    def _could_be_mediator(self, pd: str, context) -> bool:
        """Check if PD could serve as a mediator"""
        # Check if PD is newly created (not original)
        original_pds = context.pattern_state.get('original_pds', [])
        if pd not in original_pds:
            return True  # Newly created PDs can be mediators
        
        # Check if PD has fewer dependencies (good mediator candidate)
        pd_dependencies = self._get_pd_dependencies(pd, context)
        return len(pd_dependencies) <= 1
    
    def _is_constraint_mentioned(self, resource: str, context) -> bool:
        """Check if resource is mentioned in constraints"""
        # This would need access to constraints through context
        # For now, use heuristic based on resource name
        return resource in ['FILE_1_3', 'SYSTEM_CONFIG', 'CRITICAL_DB']
    
    def _completes_mediation_pattern(self, candidate: Dict, context) -> bool:
        """Check if REQUEST edge completes a mediation pattern"""
        from_pd = candidate.get('from_pd') or candidate.get('from_node')
        to_pd = candidate.get('to_pd') or candidate.get('to_node')
        
        # Check if to_pd has resources that from_pd needs
        to_pd_resources = self._get_pd_resources(to_pd, context)
        orphaned_resources = context.pattern_state.get('orphaned_resources', [])
        
        # If to_pd has orphaned resources, this could complete mediation
        return bool(set(to_pd_resources) & set(orphaned_resources))
    
    def _is_shared_resource(self, resource: str, context) -> bool:
        """Check if resource is shared by multiple PDs"""
        shared_resources = context.pattern_state.get('shared_resources', [])
        return resource in shared_resources
    
    def _get_pd_dependencies(self, pd: str, context) -> List[str]:
        """Get PDs that this PD depends on via REQUEST edges"""
        dependencies = []
        for from_node, to_node, edge_data in context.graph.g.edges(data=True):
            if from_node == pd and edge_data.get('type') == 'REQUEST':
                dependencies.append(to_node)
        return dependencies
    
    def _get_pd_resources(self, pd: str, context) -> List[str]:
        """Get resources held by PD via HOLD edges"""
        resources = []
        for from_node, to_node, edge_data in context.graph.g.edges(data=True):
            if from_node == pd and edge_data.get('type') == 'HOLD':
                resources.append(to_node)
        return resources


class SharingReductionPatternDetector(PatternDetector):
    """Detects and scores sharing reduction patterns"""
    
    def is_active(self, context) -> bool:
        """Sharing reduction is active when RSI goals exist and shared resources are present"""
        # Check for RSI or sharing-related goals
        has_sharing_goals = any(
            goal.metric_name in ['RSI', 'shared_resource_count', 'ASR'] 
            for goal in context.goals
        )
        
        # Check for shared resources
        has_shared_resources = len(context.pattern_state.get('shared_resources', [])) > 0
        
        return has_sharing_goals and has_shared_resources
    
    def score_operation(self, operation, candidate: Dict, context) -> Optional[float]:
        """Score operations that reduce sharing"""
        shared_resources = context.pattern_state.get('shared_resources', [])
        
        # High priority: Remove shared resource connections
        if operation.name == "remove_hold_edge":
            to_resource = candidate.get('to_node') or candidate.get('resource')
            if to_resource in shared_resources:
                return 2.8  # Very high priority for reducing sharing
        
        # Very high priority: Connect to private alternatives
        if operation.name == "add_hold_edge":
            to_resource = candidate.get('to_node') or candidate.get('resource')
            from_pd = candidate.get('from_node') or candidate.get('pd')
            
            # Penalize adding more sharing
            if to_resource in shared_resources:
                return 0.1  # Strong penalty for increasing sharing
            
            # Boost private alternatives that satisfy constraints
            if self._is_private_alternative_for_constraints(from_pd, to_resource, context):
                return 2.9  # Very high priority for private constraint alternatives
            
            # Moderate boost for any private resource use
            if to_resource not in shared_resources:
                return 1.2  # Encourage private resource use
        
        # Boost creating alternative private resources
        if operation.name in ["add_file_resource", "add_resource_space"]:
            if self._needs_private_alternatives(context):
                return 1.5  # High boost for creating alternatives
        
        return None
    
    def _is_private_alternative_for_constraints(self, pd: str, resource: str, context) -> bool:
        """Check if resource provides private alternative that satisfies constraints"""
        # Use resource type system to check if this satisfies PD's constraints
        return context.resource_type_system.provides_alternative(pd, resource, context)
    
    def _needs_private_alternatives(self, context) -> bool:
        """Check if private alternatives are needed for constraint satisfaction"""
        shared_resources = context.pattern_state.get('shared_resources', [])
        
        # Get types of shared resources
        shared_types = set()
        for resource in shared_resources:
            resource_type = context.resource_type_system.infer_type(resource)
            shared_types.add(resource_type)
        
        # Check if any shared types are required by constraints
        # This would need access to constraints through context
        # For now, return True if we have shared resources
        return len(shared_types) > 0


class IsolationViolationDetector(PatternDetector):
    """Detects isolation violations and scores corrective operations"""
    
    def is_active(self, context) -> bool:
        """Active when isolation goals exist or violations are detected"""
        # Check for isolation-related goals
        has_isolation_goals = any(
            goal.metric_name in ['TCB', 'isolation_index', 'fault_radius']
            for goal in context.goals
        )
        
        return has_isolation_goals
    
    def score_operation(self, operation, candidate: Dict, context) -> Optional[float]:
        """Score operations that improve isolation"""
        
        # Boost removing unnecessary connections that hurt isolation
        if operation.name == "remove_request_edge":
            if self._reduces_unnecessary_dependencies(candidate, context):
                return 1.5  # Boost isolation improvement
        
        # Boost creating isolated alternatives
        if operation.name == "add_pd":
            if self._creates_isolated_component(candidate, context):
                return 1.3  # Boost isolation through separation
        
        return None
    
    def _reduces_unnecessary_dependencies(self, candidate: Dict, context) -> bool:
        """Check if removing REQUEST edge reduces unnecessary dependencies"""
        # Placeholder - would analyze dependency graphs
        return False
    
    def _creates_isolated_component(self, candidate: Dict, context) -> bool:
        """Check if creating PD improves isolation"""
        # Placeholder - would analyze isolation impact
        return True


class PrivilegeEscalationPreventionDetector(PatternDetector):
    """Detects and prevents privilege escalation patterns"""
    
    def is_active(self, context) -> bool:
        """Active when authority-related goals exist"""
        has_authority_goals = any(
            goal.metric_name in ['TCB', 'authority_concentration', 'privilege_separation']
            for goal in context.goals
        )
        
        return has_authority_goals
    
    def score_operation(self, operation, candidate: Dict, context) -> Optional[float]:
        """Score operations that prevent privilege escalation"""
        
        # Penalize operations that concentrate authority
        if operation.name == "add_request_edge":
            if self._concentrates_authority(candidate, context):
                return 0.3  # Penalty for authority concentration
        
        # Boost operations that distribute authority
        if operation.name in ["add_pd", "add_hold_edge"]:
            if self._distributes_authority(candidate, context):
                return 1.4  # Boost authority distribution
        
        return None
    
    def _concentrates_authority(self, candidate: Dict, context) -> bool:
        """Check if operation concentrates too much authority"""
        # Placeholder - would analyze authority distribution
        return False
    
    def _distributes_authority(self, candidate: Dict, context) -> bool:
        """Check if operation improves authority distribution"""
        # Placeholder - would analyze authority impact
        return False


class DefaultPatternDetectorRegistry:
    """Registry of default pattern detectors"""
    
    @staticmethod
    def get_default_detectors() -> List[PatternDetector]:
        """Return list of default pattern detectors"""
        return [
            MediationPatternDetector(),
            SharingReductionPatternDetector(),
            IsolationViolationDetector(),
            PrivilegeEscalationPreventionDetector()
        ]
    
    @staticmethod
    def get_detectors_for_domain(domain: str) -> List[PatternDetector]:
        """Return pattern detectors appropriate for specific domain"""
        if domain == "os_security":
            return [
                MediationPatternDetector(),
                SharingReductionPatternDetector(),
                IsolationViolationDetector()
            ]
        elif domain == "network_security":
            return [
                IsolationViolationDetector(),
                PrivilegeEscalationPreventionDetector()
            ]
        elif domain == "privilege_separation":
            return [
                MediationPatternDetector(),
                PrivilegeEscalationPreventionDetector()
            ]
        else:
            return DefaultPatternDetectorRegistry.get_default_detectors()