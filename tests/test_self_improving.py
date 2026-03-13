#!/usr/bin/env python3
"""
Quick test for Self-Improving Agent features.

Run this to verify the reflection engine and experience repository work correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add cyberclaw to path
sys.path.insert(0, str(Path(__file__).parent))

from cyberclaw.agent.reflection import ReflectionEngine, ReflectionReport
from cyberclaw.agent.experience import ExperienceRepository, ExperienceType
from cyberclaw.agent.metrics import MetricsTracker


async def test_reflection_engine():
    """Test reflection engine basic functionality."""
    print("\n🧪 Testing Reflection Engine...")
    
    workspace = Path.cwd()
    # Mock provider for testing
    class MockProvider:
        async def chat(self, messages, **kwargs):
            from cyberclaw.providers.base import LLMResponse
            return LLMResponse(
                content='''{
                    "what_went_well": ["Test success"],
                    "what_went_poorly": ["Test issue"],
                    "root_causes": ["Test root cause"],
                    "lessons_learned": ["Test lesson"],
                    "suggested_improvements": ["Test improvement"],
                    "confidence_score": 0.85,
                    "patterns_detected": ["Test pattern"]
                }'''
            )
    
    provider = MockProvider()
    engine = ReflectionEngine(workspace, provider, "test-model")
    
    # Generate a test reflection
    report = await engine.generate_reflection(
        task_id="test_001",
        task_description="Test task for verification",
        status="success",
        duration=5.5,
        tool_calls=[
            {"tool_name": "read_file", "success": True, "duration": 0.5, "error": None},
            {"tool_name": "write_file", "success": True, "duration": 1.2, "error": None},
        ],
        tokens_used=500,
        errors=[],
    )
    
    assert isinstance(report, ReflectionReport)
    assert report.status == "success"
    assert report.confidence_score == 0.85
    print(f"  ✓ Generated reflection: {report.task_description}")
    print(f"  ✓ Confidence: {report.confidence_score}")
    print(f"  ✓ Status: {report.status}")
    
    # Test summary
    summary = engine.generate_summary_report()
    assert "Reflection" in summary
    print(f"  ✓ Generated summary report")
    
    return True


def test_experience_repository():
    """Test experience repository basic functionality."""
    print("\n🧪 Testing Experience Repository...")
    
    workspace = Path.cwd()
    repo = ExperienceRepository(workspace)
    
    # Add a test experience
    record = repo.add_experience(
        task_description="Test experience record",
        task_category="testing",
        success=True,
        input_context="Testing the experience repository",
        solution_approach="Used test-driven approach",
        tools_used=["test_tool", "mock_tool"],
        outcome_description="Successfully tested",
        key_insights=["Testing is important", "Mocking helps"],
        warnings=[],
        is_generalizable=True,
        confidence_score=0.9,
        tags=["test", "verification"],
    )
    
    assert record.id is not None
    assert record.success is True
    print(f"  ✓ Added experience: {record.id}")
    print(f"  ✓ Category: {record.task_category}")
    
    # Test search
    similar = repo.get_similar_experiences("test experience", category="testing", limit=5)
    assert len(similar) > 0
    print(f"  ✓ Found {len(similar)} similar experiences")
    
    # Test statistics
    stats = repo.get_statistics()
    assert stats["total_records"] > 0
    print(f"  ✓ Repository has {stats['total_records']} records")
    
    # Test summary
    summary = repo.generate_summary_report()
    assert "Experience" in summary
    print(f"  ✓ Generated summary report")
    
    return True


def test_metrics_failure_tracking():
    """Test metrics failure pattern tracking."""
    print("\n🧪 Testing Metrics Failure Tracking...")
    
    workspace = Path.cwd()
    metrics = MetricsTracker(workspace)
    
    # Record some failures
    metrics.record_tool_call("exec", success=False, duration=1.5, error="Permission denied: /etc/passwd")
    metrics.record_tool_call("exec", success=False, duration=1.2, error="Permission denied: /etc/shadow")
    metrics.record_tool_call("read_file", success=True, duration=0.5, error=None)
    metrics.record_tool_call("exec", success=False, duration=2.1, error="Command timeout after 30s")
    
    # Get failure patterns
    patterns = metrics.get_failure_patterns(limit=5)
    assert len(patterns) > 0
    print(f"  ✓ Tracked {len(patterns)} failure patterns")
    
    # Verify pattern counting
    for pattern, count in patterns:
        print(f"    - ({count}x) {pattern[:60]}...")
    
    # Test summary includes failure patterns
    summary = metrics.get_summary()
    assert "Failure" in summary or "failure" in summary
    print(f"  ✓ Summary includes failure patterns")
    
    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🚀 Self-Improving Agent Feature Tests")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Reflection Engine", await test_reflection_engine()))
    except Exception as e:
        print(f"  ✗ Reflection Engine failed: {e}")
        results.append(("Reflection Engine", False))
    
    try:
        results.append(("Experience Repository", test_experience_repository()))
    except Exception as e:
        print(f"  ✗ Experience Repository failed: {e}")
        results.append(("Experience Repository", False))
    
    try:
        results.append(("Metrics Failure Tracking", test_metrics_failure_tracking()))
    except Exception as e:
        print(f"  ✗ Metrics Failure Tracking failed: {e}")
        results.append(("Metrics Failure Tracking", False))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        icon = "✓" if result else "✗"
        print(f"  {icon} {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! Self-improving features are working.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
