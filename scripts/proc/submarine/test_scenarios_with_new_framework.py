#!/usr/bin/env python3
"""
Test Scenarios with New Generic Framework

This script tests the existing submarine scenarios with the new generic framework
to ensure compatibility and compare results.
"""

import sys
import os
import traceback
from typing import Dict, List, Any

# Add current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import the integration layer
from scoring_integration_patch import enable_generic_scoring, disable_generic_scoring, get_integration_status

# Import scenario handling
try:
    from scenarios import SCENARIOS
    from isosearch import BeamSearchExploration, ComputeMetrics, GoalsMet
    print("✅ Successfully imported existing scenario infrastructure")
except ImportError as e:
    print(f"❌ Failed to import scenario infrastructure: {e}")
    sys.exit(1)


class ScenarioTester:
    """Test scenarios with both old and new frameworks for comparison"""
    
    def __init__(self):
        self.results = {}
        self.test_scenarios = [
            "basic_sharing",
            "basic_sharing_primitive", 
            "mediator_test_indirect",
            "mediator_test_primitive"
        ]
    
    def test_scenario_with_framework(self, scenario_name: str, use_generic: bool = True) -> Dict[str, Any]:
        """Test a scenario with specified framework"""
        
        print(f"\n{'='*60}")
        print(f"Testing scenario: {scenario_name}")
        print(f"Framework: {'Generic' if use_generic else 'Original'}")
        print(f"{'='*60}")
        
        # Configure framework
        if use_generic:
            enable_generic_scoring("os_security")
        else:
            disable_generic_scoring()
        
        # Check integration status
        status = get_integration_status()
        print(f"Integration status: {status}")
        
        try:
            # Get scenario
            if scenario_name not in SCENARIOS:
                return {"error": f"Scenario {scenario_name} not found"}
            
            scenario = SCENARIOS[scenario_name]
            
            # Run beam search exploration
            print(f"\n🔍 Running beam search exploration...")
            mechanisms = BeamSearchExploration(scenario, beam_width=3)
            
            # Analyze results
            result = {
                "scenario_name": scenario_name,
                "framework_type": "generic" if use_generic else "original",
                "mechanisms_found": len(mechanisms),
                "mechanisms": []
            }
            
            print(f"📊 Found {len(mechanisms)} mechanisms")
            
            # Analyze each mechanism
            for i, mechanism in enumerate(mechanisms):
                print(f"\n📋 Mechanism {i+1}:")
                
                # Compute metrics
                try:
                    metrics = ComputeMetrics(mechanism['graph'])
                    goals_met = GoalsMet(metrics, scenario.goals)
                    
                    mechanism_result = {
                        "mechanism_id": i+1,
                        "metrics": metrics,
                        "goals_met": goals_met,
                        "iteration": mechanism.get('iteration', 'unknown'),
                        "discovery_method": mechanism.get('discovery_method', 'beam_search')
                    }
                    
                    result["mechanisms"].append(mechanism_result)
                    
                    print(f"   Metrics: {metrics}")
                    print(f"   Goals met: {goals_met}")
                    print(f"   Discovery iteration: {mechanism.get('iteration', 'unknown')}")
                    
                except Exception as e:
                    print(f"   ❌ Error computing metrics: {e}")
                    mechanism_result = {
                        "mechanism_id": i+1,
                        "error": str(e)
                    }
                    result["mechanisms"].append(mechanism_result)
            
            return result
            
        except Exception as e:
            print(f"❌ Error testing scenario {scenario_name}: {e}")
            traceback.print_exc()
            return {
                "scenario_name": scenario_name,
                "framework_type": "generic" if use_generic else "original", 
                "error": str(e)
            }
    
    def compare_frameworks(self, scenario_name: str) -> Dict[str, Any]:
        """Compare results between original and generic frameworks"""
        
        print(f"\n🔄 Comparing frameworks for scenario: {scenario_name}")
        
        # Test with original framework (if available)
        print("\n1️⃣ Testing with original framework...")
        try:
            original_result = self.test_scenario_with_framework(scenario_name, use_generic=False)
        except Exception as e:
            print(f"⚠️  Original framework test failed: {e}")
            original_result = {"error": f"Original framework unavailable: {e}"}
        
        # Test with generic framework
        print("\n2️⃣ Testing with generic framework...")
        generic_result = self.test_scenario_with_framework(scenario_name, use_generic=True)
        
        # Compare results
        comparison = {
            "scenario_name": scenario_name,
            "original_result": original_result,
            "generic_result": generic_result,
            "comparison": self._analyze_comparison(original_result, generic_result)
        }
        
        return comparison
    
    def _analyze_comparison(self, original: Dict, generic: Dict) -> Dict[str, Any]:
        """Analyze differences between framework results"""
        
        analysis = {}
        
        # Check if both succeeded
        original_success = "error" not in original
        generic_success = "error" not in generic
        
        analysis["both_succeeded"] = original_success and generic_success
        analysis["original_success"] = original_success
        analysis["generic_success"] = generic_success
        
        if not analysis["both_succeeded"]:
            if not original_success:
                analysis["original_error"] = original.get("error", "Unknown error")
            if not generic_success:
                analysis["generic_error"] = generic.get("error", "Unknown error")
            return analysis
        
        # Compare mechanism counts
        original_count = original.get("mechanisms_found", 0)
        generic_count = generic.get("mechanisms_found", 0)
        
        analysis["mechanism_count_match"] = original_count == generic_count
        analysis["original_mechanism_count"] = original_count
        analysis["generic_mechanism_count"] = generic_count
        
        # Compare goals met
        original_goals_met = any(m.get("goals_met", False) for m in original.get("mechanisms", []))
        generic_goals_met = any(m.get("goals_met", False) for m in generic.get("mechanisms", []))
        
        analysis["goals_achievement_match"] = original_goals_met == generic_goals_met
        analysis["original_goals_met"] = original_goals_met
        analysis["generic_goals_met"] = generic_goals_met
        
        # Overall compatibility
        analysis["compatible"] = (
            analysis["mechanism_count_match"] and 
            analysis["goals_achievement_match"]
        )
        
        return analysis
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all scenario tests"""
        
        print("🚀 Running comprehensive scenario tests with new generic framework")
        print("="*80)
        
        all_results = {
            "test_summary": {
                "total_scenarios": len(self.test_scenarios),
                "successful_tests": 0,
                "failed_tests": 0,
                "compatible_scenarios": 0
            },
            "scenario_results": {}
        }
        
        for scenario_name in self.test_scenarios:
            print(f"\n📋 Testing scenario: {scenario_name}")
            
            try:
                # Test with generic framework only (since original may not be available)
                result = self.test_scenario_with_framework(scenario_name, use_generic=True)
                
                all_results["scenario_results"][scenario_name] = result
                
                if "error" not in result:
                    all_results["test_summary"]["successful_tests"] += 1
                    print(f"✅ {scenario_name}: SUCCESS")
                else:
                    all_results["test_summary"]["failed_tests"] += 1
                    print(f"❌ {scenario_name}: FAILED - {result['error']}")
                    
            except Exception as e:
                print(f"❌ {scenario_name}: EXCEPTION - {e}")
                all_results["scenario_results"][scenario_name] = {"error": str(e)}
                all_results["test_summary"]["failed_tests"] += 1
        
        # Print summary
        summary = all_results["test_summary"]
        print(f"\n{'='*80}")
        print("📊 TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total scenarios tested: {summary['total_scenarios']}")
        print(f"Successful tests: {summary['successful_tests']}")
        print(f"Failed tests: {summary['failed_tests']}")
        print(f"Success rate: {summary['successful_tests']/summary['total_scenarios']*100:.1f}%")
        
        return all_results
    
    def test_specific_scenario(self, scenario_name: str):
        """Test a specific scenario in detail"""
        
        if scenario_name not in SCENARIOS:
            print(f"❌ Scenario '{scenario_name}' not found")
            print(f"Available scenarios: {list(SCENARIOS.keys())}")
            return
        
        print(f"🔍 Detailed test of scenario: {scenario_name}")
        result = self.test_scenario_with_framework(scenario_name, use_generic=True)
        
        # Print detailed results
        if "error" not in result:
            print(f"\n✅ Test completed successfully!")
            print(f"📊 Mechanisms found: {result['mechanisms_found']}")
            
            if result['mechanisms_found'] > 0:
                print(f"\n📋 Mechanism details:")
                for mech in result['mechanisms']:
                    print(f"  Mechanism {mech['mechanism_id']}:")
                    print(f"    Goals met: {mech.get('goals_met', 'unknown')}")
                    print(f"    Iteration: {mech.get('iteration', 'unknown')}")
                    if 'metrics' in mech:
                        print(f"    Metrics: {mech['metrics']}")
        else:
            print(f"❌ Test failed: {result['error']}")


def main():
    """Main test function"""
    
    tester = ScenarioTester()
    
    # Check if specific scenario requested
    if len(sys.argv) > 1:
        scenario_name = sys.argv[1]
        tester.test_specific_scenario(scenario_name)
    else:
        # Run all tests
        results = tester.run_all_tests()
        
        # Save results to file
        import json
        results_file = "scenario_test_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Detailed results saved to: {results_file}")


if __name__ == "__main__":
    main()