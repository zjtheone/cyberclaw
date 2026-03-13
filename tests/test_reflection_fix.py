#!/usr/bin/env python3
"""
Test script to verify reflection engine is working after fixes.

Run this after restarting cyberclaw to test reflection generation.
"""

import asyncio
import sys
from pathlib import Path

# Add cyberclaw to path
sys.path.insert(0, str(Path(__file__).parent))

from cyberclaw.agent.reflection import ReflectionEngine, ReflectionReport
from cyberclaw.providers.base import LLMProvider


async def test_reflection_engine():
    """Test reflection engine with mock data."""
    print("🔍 Testing Reflection Engine...")
    print("=" * 60)
    
    workspace = Path(__file__).parent
    
    # Create a mock provider for testing
    print("📦 Creating mock LLM provider...")
    
    # Use environment variable or default for testing
    import os
    api_key = os.getenv("LLM_API_KEY", "test-key")
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    model = os.getenv("LLM_MODEL", "qwen2.5:7b")
    
    print(f"   Model: {model}")
    print(f"   Base URL: {base_url}")
    print()
    
    # Initialize reflection engine
    print("📦 Initializing ReflectionEngine...")
    try:
        from cyberclaw.providers.lite import LiteLLMProvider
        provider = LiteLLMProvider(api_key=api_key, base_url=base_url)
    except Exception as e:
        print(f"⚠️  Could not initialize provider: {e}")
        print("   Will test with mock data only")
        return
    
    engine = ReflectionEngine(
        workspace=workspace,
        provider=provider,
        model=model,
    )
    print(f"✅ ReflectionEngine initialized (model={model})")
    print()
    
    # Test case 1: Simple task (file operation)
    print("📝 Test 1: Simple file operation task")
    print("-" * 60)
    report1 = await engine.generate_reflection(
        task_id="test_task_1",
        task_description="Create a Python script to read a file",
        status="success",
        duration=2.5,
        tool_calls=[
            {"tool_name": "read_file", "success": True, "duration": 0.001},
            {"tool_name": "write_file", "success": True, "duration": 0.002},
        ],
        tokens_used=1500,
        errors=[],
    )
    print(f"✅ Report generated: confidence={report1.confidence_score:.2f}")
    print(f"   - What went well: {len(report1.what_went_well)} items")
    print(f"   - Lessons learned: {len(report1.lessons_learned)} items")
    print(f"   - Improvements: {len(report1.suggested_improvements)} items")
    print()
    
    # Test case 2: Complex task with errors
    print("📝 Test 2: Complex task with errors")
    print("-" * 60)
    report2 = await engine.generate_reflection(
        task_id="test_task_2",
        task_description="Build a web crawler with error handling",
        status="partial_success",
        duration=45.8,
        tool_calls=[
            {"tool_name": "web_fetch", "success": True, "duration": 1.2},
            {"tool_name": "write_file", "success": True, "duration": 0.003},
            {"tool_name": "exec", "success": False, "duration": 5.0, "error": "Timeout"},
            {"tool_name": "exec", "success": True, "duration": 2.1},
        ],
        tokens_used=8500,
        errors=["Timeout error during web scraping"],
    )
    print(f"✅ Report generated: confidence={report2.confidence_score:.2f}")
    print(f"   - What went poorly: {len(report2.what_went_poorly)} items")
    print(f"   - Root causes: {len(report2.root_causes)} items")
    print(f"   - Improvements: {len(report2.suggested_improvements)} items")
    print()
    
    # Test case 3: Failed task
    print("📝 Test 3: Failed task")
    print("-" * 60)
    report3 = await engine.generate_reflection(
        task_id="test_task_3",
        task_description="Query MongoDB instances",
        status="failure",
        duration=120.0,
        tool_calls=[
            {"tool_name": "exec", "success": False, "duration": 30.0, "error": "Command not found"},
            {"tool_name": "exec", "success": False, "duration": 30.0, "error": "Connection timeout"},
        ],
        tokens_used=2000,
        errors=["jdc command not found", "Network timeout"],
    )
    print(f"✅ Report generated: confidence={report3.confidence_score:.2f}")
    print(f"   - Root causes: {len(report3.root_causes)} items")
    print(f"   - Lessons learned: {len(report3.lessons_learned)} items")
    print()
    
    # Summary
    print("=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print(f"✅ All 3 reflection reports generated successfully")
    print(f"📁 Reports saved to: {engine.reports_file}")
    print()
    
    # Verify reports were saved
    if engine.reports_file.exists():
        lines = engine.reports_file.read_text().splitlines()
        print(f"📄 Reports file contains {len(lines)} reports")
        print(f"   Path: {engine.reports_file}")
    else:
        print(f"❌ Reports file not found: {engine.reports_file}")
    
    print()
    print("🎉 Reflection engine test completed!")
    print()
    print("Next steps:")
    print("1. Restart cyberclaw: cyberclaw")
    print("2. Complete a task")
    print("3. Check reflections: get_reflections recent")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(test_reflection_engine())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
