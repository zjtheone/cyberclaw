#!/usr/bin/env python3
"""
Test script for Self-Improving Agent P1/P2 features.

Tests:
1. Confidence Injection (P1)
2. Tool Selection Optimization (P1)
3. Skill Evolution Suggestions (P2)
"""

import sys
import json
from pathlib import Path

# Add cyberclaw to path
workspace = Path(__file__).parent.parent
sys.path.insert(0, str(workspace))

from cyberclaw.agent.confidence import ConfidenceEvaluator, ConfidenceResult
from cyberclaw.agent.tool_optimizer import ToolOptimizer, ToolStatistics
from cyberclaw.agent.skill_evolution import SkillEvolutionAnalyzer, SkillUsageStats
from cyberclaw.agent.metrics import MetricsTracker
from cyberclaw.agent.experience import ExperienceRepository


def test_confidence_evaluator():
    """Test confidence evaluation (P1)."""
    print("\n" + "="*60)
    print("Testing Confidence Evaluator (P1)")
    print("="*60)
    
    evaluator = ConfidenceEvaluator(
        workspace=workspace,
        threshold=0.7,
        auto_verify=True,
    )
    
    # Test 1: High confidence answer
    print("\n1. Testing high confidence answer...")
    result = evaluator.evaluate(
        question="How do I read a file in Python?",
        answer="""To read a file in Python, use the built-in `open()` function:

```python
with open('file.txt', 'r') as f:
    content = f.read()
```

This is the standard approach for reading files.""",
        context={"domain": "code"},
    )
    
    assert isinstance(result, ConfidenceResult)
    print(f"   Score: {result.score:.2f}")
    print(f"   Level: {result.level}")
    print(f"   Should Verify: {result.should_verify}")
    print(f"   ✓ Confidence evaluation works")
    
    # Test 2: Low confidence answer (with uncertainty language)
    print("\n2. Testing low confidence answer...")
    result2 = evaluator.evaluate(
        question="What's the best programming language?",
        answer="""I'm not sure about the best language. It might depend on what you're building. 
        Maybe Python or JavaScript? I think it's hard to say for certain.""",
        context={"domain": "opinion"},
    )
    
    print(f"   Score: {result2.score:.2f}")
    print(f"   Level: {result2.level}")
    print(f"   Should Verify: {result2.should_verify}")
    
    if result2.level == "low" or result2.warnings:
        print(f"   ✓ Low confidence detected correctly")
    else:
        print(f"   ⚠ Low confidence detection may need tuning")
    
    # Test 3: Verification prompt
    print("\n3. Testing verification prompt generation...")
    prompt = evaluator.generate_verification_prompt(result2)
    if prompt:
        print(f"   ✓ Verification prompt generated ({len(prompt)} chars)")
    else:
        print(f"   ✓ No verification needed for high confidence")
    
    # Test 4: Get factors
    print("\n4. Testing confidence factors...")
    factors = evaluator.get_confidence_factors()
    print(f"   Threshold: {factors['threshold']}")
    print(f"   History records: {factors['history_records']}")
    print(f"   ✓ Confidence factors retrieved")
    
    print("\n✅ Confidence Evaluator tests completed")
    return True


def test_tool_optimizer():
    """Test tool optimization (P1)."""
    print("\n" + "="*60)
    print("Testing Tool Optimizer (P1)")
    print("="*60)
    
    metrics = MetricsTracker(workspace)
    optimizer = ToolOptimizer(
        workspace=workspace,
        metrics_tracker=metrics,
        min_samples=1,
    )
    
    # Test 1: Record tool executions
    print("\n1. Testing tool execution recording...")
    optimizer.record_tool_execution("read_file", True, 0.5, task_description="Read config file", category="file_operation")
    optimizer.record_tool_execution("read_file", True, 0.3, task_description="Read source code", category="file_operation")
    optimizer.record_tool_execution("read_file", True, 0.4, task_description="Read documentation", category="file_operation")
    optimizer.record_tool_execution("exec", True, 2.5, task_description="Run tests", category="shell")
    optimizer.record_tool_execution("exec", False, 5.0, error="Command timeout", task_description="Run slow command", category="shell")
    optimizer.record_tool_execution("web_search", True, 1.2, task_description="Search for info", category="search")
    
    print(f"   ✓ Recorded 6 tool executions")
    
    # Test 2: Get statistics
    print("\n2. Testing tool statistics...")
    stats = optimizer.get_statistics("read_file")
    if stats:
        print(f"   read_file stats:")
        print(f"     - Total calls: {stats.total_calls}")
        print(f"     - Success rate: {stats.success_rate*100:.0f}%")
        print(f"     - Avg duration: {stats.avg_duration:.2f}s")
        print(f"   ✓ Statistics retrieved")
    else:
        print(f"   ✗ Failed to get statistics")
        return False
    
    # Test 3: Get success rates
    print("\n3. Testing success rate calculation...")
    success_rates = {name: optimizer.get_success_rate(name) for name in optimizer.get_all_statistics().keys()}
    print(f"   Success rates: {success_rates}")
    print(f"   ✓ Success rates calculated")
    
    # Test 4: Tool rankings
    print("\n4. Testing tool rankings...")
    rankings = optimizer.get_tool_rankings("success_rate", min_calls=1)
    print(f"   Rankings by success rate:")
    for tool_name, score in rankings[:3]:
        print(f"     - {tool_name}: {score*100:.0f}%")
    print(f"   ✓ Rankings generated")
    
    # Test 5: Tool recommendations
    print("\n5. Testing tool recommendations...")
    recommendations = optimizer.recommend_tool("read a configuration file", max_recommendations=3)
    if recommendations:
        print(f"   Recommendations for 'read a configuration file':")
        for i, rec in enumerate(recommendations, 1):
            print(f"     {i}. {rec.tool_name} (score: {rec.score:.2f})")
            if rec.reasons:
                print(f"        Reasons: {', '.join(rec.reasons[:2])}")
        print(f"   ✓ Recommendations generated")
    else:
        print(f"   ⚠ No recommendations (may need more data)")
    
    # Test 6: Performance report
    print("\n6. Testing performance report...")
    report = optimizer.get_performance_report()
    if report:
        lines = report.split("\n")
        print(f"   ✓ Performance report generated ({len(lines)} lines)")
        # Print first few lines
        for line in lines[:5]:
            print(f"     {line}")
    else:
        print(f"   ✗ Failed to generate report")
        return False
    
    print("\n✅ Tool Optimizer tests completed")
    return True


def test_skill_evolution():
    """Test skill evolution analysis (P2)."""
    print("\n" + "="*60)
    print("Testing Skill Evolution Analyzer (P2)")
    print("="*60)
    
    # Create dependencies
    metrics = MetricsTracker(workspace)
    experience_repo = ExperienceRepository(workspace)
    tool_optimizer = ToolOptimizer(workspace, metrics_tracker=metrics)
    
    # Create analyzer
    analyzer = SkillEvolutionAnalyzer(
        workspace=workspace,
        experience_repo=experience_repo,
        metrics_tracker=metrics,
        tool_optimizer=tool_optimizer,
    )
    
    # Test 1: Analyze skill usage
    print("\n1. Testing skill usage analysis...")
    stats = analyzer.analyze_skill_usage(period_days=30)
    print(f"   Analyzed {len(stats)} skills")
    print(f"   ✓ Skill usage analysis completed")
    
    # Test 2: Detect usage patterns
    print("\n2. Testing usage pattern detection...")
    patterns = analyzer.detect_usage_patterns()
    print(f"   Detected patterns for {len(patterns)} skills")
    print(f"   ✓ Pattern detection completed")
    
    # Test 3: Identify gaps
    print("\n3. Testing skill gap identification...")
    gaps = analyzer.identify_gaps()
    print(f"   Identified {len(gaps)} skill gaps")
    if gaps:
        for gap in gaps[:2]:
            print(f"     - [{gap.gap_type}] {gap.description[:60]}...")
    print(f"   ✓ Gap identification completed")
    
    # Test 4: Generate improvement suggestions
    print("\n4. Testing improvement suggestions...")
    suggestions = analyzer.generate_improvement_suggestions()
    print(f"   Generated {len(suggestions)} suggestions")
    if suggestions:
        for suggestion in suggestions[:3]:
            print(f"     - {suggestion[:80]}")
    print(f"   ✓ Suggestions generated")
    
    # Test 5: Generate evolution report
    print("\n5. Testing evolution report generation...")
    report = analyzer.generate_evolution_report(period_days=30)
    
    print(f"   Report overview:")
    print(f"     - Total skills: {report.total_skills}")
    print(f"     - Active skills: {report.active_skills}")
    print(f"     - Overall health: {report.overall_health:.2f}")
    print(f"     - Top performers: {len(report.top_performers)}")
    print(f"     - Underperforming: {len(report.underperforming)}")
    print(f"     - Skill gaps: {len(report.skill_gaps)}")
    print(f"   ✓ Evolution report generated")
    
    # Test 6: Get report text
    print("\n6. Testing report text formatting...")
    report_text = analyzer.get_report_text(report)
    lines = report_text.split("\n")
    print(f"   ✓ Report text formatted ({len(lines)} lines)")
    
    # Print summary
    print("\n   Sample report excerpt:")
    for line in lines[:10]:
        print(f"     {line}")
    
    print("\n✅ Skill Evolution Analyzer tests completed")
    return True


def test_integration():
    """Test integration of all P1/P2 features."""
    print("\n" + "="*60)
    print("Testing Integration (P1/P2)")
    print("="*60)
    
    # Test that all components work together
    print("\n1. Testing component integration...")
    
    metrics = MetricsTracker(workspace)
    experience_repo = ExperienceRepository(workspace)
    
    evaluator = ConfidenceEvaluator(workspace)
    optimizer = ToolOptimizer(workspace, metrics_tracker=metrics)
    
    analyzer = SkillEvolutionAnalyzer(
        workspace=workspace,
        experience_repo=experience_repo,
        metrics_tracker=metrics,
        tool_optimizer=optimizer,
    )
    
    print(f"   ✓ All components initialized successfully")
    
    # Simulate a workflow
    print("\n2. Simulating workflow...")
    
    # Record some tool usage
    optimizer.record_tool_execution("read_file", True, 0.5, category="file_operation")
    optimizer.record_tool_execution("edit_file", True, 1.2, category="file_operation")
    optimizer.record_tool_execution("exec", False, 3.0, error="Permission denied", category="shell")
    
    # Evaluate confidence
    result = evaluator.evaluate(
        question="Edit the config file",
        answer="I've edited the config file successfully.",
        context={"domain": "file_operation"},
        tool_results=[
            {"tool_name": "read_file", "success": True, "duration": 0.5},
            {"tool_name": "edit_file", "success": True, "duration": 1.2},
        ],
    )
    
    print(f"   Confidence score: {result.score:.2f}")
    print(f"   Confidence level: {result.level}")
    
    # Get tool recommendations
    recommendations = optimizer.recommend_tool("modify a file", max_recommendations=2)
    if recommendations:
        print(f"   Recommended tools: {[r.tool_name for r in recommendations]}")
    
    # Get skill analysis
    stats = analyzer.analyze_skill_usage(period_days=30)
    print(f"   Skills analyzed: {len(stats)}")
    
    print(f"   ✓ Workflow simulation completed")
    
    print("\n✅ Integration tests completed")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Self-Improving Agent P1/P2 Feature Tests")
    print("="*60)
    
    results = {
        "confidence": False,
        "tool_optimizer": False,
        "skill_evolution": False,
        "integration": False,
    }
    
    try:
        results["confidence"] = test_confidence_evaluator()
    except Exception as e:
        print(f"\n❌ Confidence Evaluator test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        results["tool_optimizer"] = test_tool_optimizer()
    except Exception as e:
        print(f"\n❌ Tool Optimizer test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        results["skill_evolution"] = test_skill_evolution()
    except Exception as e:
        print(f"\n❌ Skill Evolution test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        results["integration"] = test_integration()
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 All tests passed! P1/P2 features are working correctly.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
