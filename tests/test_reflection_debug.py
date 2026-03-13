#!/usr/bin/env python3
"""
Test script to debug the reflection engine.
Directly tests the ReflectionEngine to see if it can generate reports.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add cyberclaw to path
sys.path.insert(0, str(Path(__file__).parent))

from cyberclaw.agent.reflection import ReflectionEngine, ReflectionReport
from cyberclaw.config import Config, load_config


async def test_reflection_engine():
    """Test the reflection engine directly."""
    
    print("=" * 60)
    print("🔍 Testing Reflection Engine")
    print("=" * 60)
    
    # Load config
    workspace = Path(__file__).parent
    config = load_config()
    
    print(f"\n📁 Workspace: {workspace}")
    print(f"🤖 Model: {config.agents.defaults.model}")
    
    # Initialize reflection engine
    print("\n⚙️  Initializing ReflectionEngine...")
    try:
        from cyberclaw.providers.litellm_provider import LiteLLMProvider
        
        # Get provider config
        provider_config, provider_name = config._match_provider()
        print(f"   Provider: {provider_name}")
        
        provider = LiteLLMProvider(
            api_key=provider_config.api_key if provider_config else None,
            api_base=provider_config.api_base if provider_config else None,
            default_model=config.agents.defaults.model,
            provider_name=provider_name,
        )
        
        engine = ReflectionEngine(
            workspace=workspace,
            provider=provider,
            model=config.agents.defaults.model,
        )
        
        print("✅ ReflectionEngine initialized successfully")
        
    except Exception as e:
        print(f"❌ Failed to initialize ReflectionEngine: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check existing reports
    reports_file = workspace / ".cyberclaw" / "reflections" / "reflection_reports.jsonl"
    if reports_file.exists():
        count = sum(1 for _ in open(reports_file))
        print(f"📊 Existing reports: {count}")
    else:
        print("📊 No existing reports found")
    
    # Test case 1: Simple successful task
    print("\n" + "=" * 60)
    print("📝 Test 1: Simple successful task (weather query)")
    print("=" * 60)
    
    tool_calls = [
        {"tool_name": "exec", "arguments": {"command": "curl wttr.in/杭州"}, "result": "success", "duration": 2.5},
        {"tool_name": "read_file", "arguments": {"path": "test.txt"}, "result": "success", "duration": 0.001},
    ]
    
    try:
        report = await engine.generate_reflection(
            task_id=f"test_{int(datetime.now().timestamp())}",
            task_description="Query weather for Hangzhou",
            status="success",
            duration=3.2,
            tool_calls=tool_calls,
            tokens_used=1500,
            errors=[],
        )
        
        print(f"\n✅ Report generated successfully!")
        print(f"   - Status: {report.status}")
        print(f"   - Confidence: {report.confidence_score:.2f}")
        print(f"   - What went well: {len(report.what_went_well)} items")
        print(f"   - What went poorly: {len(report.what_went_poorly)} items")
        print(f"   - Lessons learned: {len(report.lessons_learned)} items")
        
        if report.what_went_well:
            print(f"\n   📌 What went well:")
            for item in report.what_went_well[:3]:
                print(f"      - {item}")
        
    except Exception as e:
        print(f"\n❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test case 2: Failed task
    print("\n" + "=" * 60)
    print("📝 Test 2: Failed task (network error)")
    print("=" * 60)
    
    tool_calls_fail = [
        {"tool_name": "web_fetch", "arguments": {"url": "https://example.com"}, "result": "failed", "error": "Connection timeout", "duration": 30.0},
        {"tool_name": "web_search", "arguments": {"query": "test"}, "result": "failed", "error": "API error", "duration": 5.0},
    ]
    
    try:
        report = await engine.generate_reflection(
            task_id=f"test_fail_{int(datetime.now().timestamp())}",
            task_description="Fetch weather data from web service",
            status="failure",
            duration=35.5,
            tool_calls=tool_calls_fail,
            tokens_used=800,
            errors=["Connection timeout", "API error"],
        )
        
        print(f"\n✅ Report generated successfully!")
        print(f"   - Status: {report.status}")
        print(f"   - Confidence: {report.confidence_score:.2f}")
        print(f"   - What went poorly: {len(report.what_went_poorly)} items")
        print(f"   - Root causes: {len(report.root_causes)} items")
        
        if report.what_went_poorly:
            print(f"\n   📌 What went poorly:")
            for item in report.what_went_poorly[:3]:
                print(f"      - {item}")
        
    except Exception as e:
        print(f"\n❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test case 3: Complex task (coding)
    print("\n" + "=" * 60)
    print("📝 Test 3: Complex task (writing code)")
    print("=" * 60)
    
    tool_calls_complex = [
        {"tool_name": "read_file", "arguments": {"path": "main.py"}, "result": "success", "duration": 0.001},
        {"tool_name": "grep", "arguments": {"pattern": "def test", "path": "."}, "result": "success", "duration": 0.5},
        {"tool_name": "write_file", "arguments": {"path": "test.py"}, "result": "success", "duration": 0.1},
        {"tool_name": "exec", "arguments": {"command": "pytest test.py"}, "result": "success", "duration": 5.2},
        {"tool_name": "edit_file", "arguments": {"path": "test.py"}, "result": "success", "duration": 0.2},
        {"tool_name": "exec", "arguments": {"command": "pytest test.py"}, "result": "success", "duration": 4.8},
    ]
    
    try:
        report = await engine.generate_reflection(
            task_id=f"test_complex_{int(datetime.now().timestamp())}",
            task_description="Write and test a Python function",
            status="success",
            duration=15.3,
            tool_calls=tool_calls_complex,
            tokens_used=5000,
            errors=[],
        )
        
        print(f"\n✅ Report generated successfully!")
        print(f"   - Status: {report.status}")
        print(f"   - Confidence: {report.confidence_score:.2f}")
        print(f"   - Complexity: {report.complexity_score:.2f}")
        print(f"   - Lessons learned: {len(report.lessons_learned)} items")
        print(f"   - Improvements: {len(report.suggested_improvements)} items")
        
        if report.lessons_learned:
            print(f"\n   📌 Lessons learned:")
            for item in report.lessons_learned[:3]:
                print(f"      - {item}")
        
    except Exception as e:
        print(f"\n❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    if reports_file.exists():
        count = sum(1 for _ in open(reports_file))
        print(f"✅ Total reports saved: {count}")
        print(f"📁 Reports file: {reports_file}")
        
        # Show last report
        print(f"\n📝 Last report preview:")
        with open(reports_file) as f:
            lines = f.readlines()
            if lines:
                last_report = json.loads(lines[-1])
                print(f"   - Task: {last_report.get('task_description', 'N/A')[:50]}")
                print(f"   - Status: {last_report.get('status', 'N/A')}")
                print(f"   - Confidence: {last_report.get('confidence_score', 0):.2f}")
    else:
        print("❌ No reports were saved!")
    
    print("\n" + "=" * 60)
    print("✅ Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_reflection_engine())
