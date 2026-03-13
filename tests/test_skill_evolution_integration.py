#!/usr/bin/env python3
"""
Test script to verify skill evolution integration with reflection engine.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

# Setup paths
workspace = Path(__file__).parent.parent
print(f"Workspace: {workspace}")

# Import components
from cyberclaw.agent.skill_evolution import SkillEvolutionAnalyzer, SkillUsageStats
from cyberclaw.agent.experience import ExperienceRepository
from cyberclaw.agent.metrics import MetricsTracker
from cyberclaw.agent.tool_optimizer import ToolOptimizer

async def test_skill_evolution_integration():
    """Test skill evolution analyzer integration."""
    
    print("\n" + "="*60)
    print("🧪 Testing Skill Evolution Integration")
    print("="*60)
    
    # Initialize components
    print("\n1. Initializing components...")
    
    experience_repo = ExperienceRepository(workspace)
    metrics_tracker = MetricsTracker(workspace)
    tool_optimizer = ToolOptimizer(workspace, metrics_tracker)
    
    skill_analyzer = SkillEvolutionAnalyzer(
        workspace=workspace,
        experience_repo=experience_repo,
        metrics_tracker=metrics_tracker,
        tool_optimizer=tool_optimizer,
        skills_dir=workspace / "skills",
    )
    
    print("✅ Components initialized successfully")
    
    # Test 1: Track skill usage manually
    print("\n2. Testing skill usage tracking...")
    
    test_skills = [
        ("weather", True, 1.5, "查询杭州天气", ""),
        ("weather", True, 1.2, "查询北京天气", ""),
        ("weather", False, 2.0, "查询上海天气", "Network timeout"),
        ("github", True, 3.5, "获取 trending 项目", ""),
        ("github", True, 2.8, "搜索仓库", ""),
        ("cron", True, 0.5, "设置定时任务", ""),
        ("memory", True, 0.8, "搜索记忆", ""),
        ("memory", False, 1.0, "写入记忆", "Permission denied"),
    ]
    
    for skill_name, success, duration, task, error in test_skills:
        skill_analyzer.track_skill_usage(
            skill_name=skill_name,
            success=success,
            duration=duration,
            task_description=task,
            error_message=error,
        )
        print(f"  ✓ Tracked: {skill_name} (success={success}, duration={duration:.1f}s)")
    
    # Test 2: Analyze skill usage
    print("\n3. Analyzing skill usage...")
    
    skill_stats = skill_analyzer.analyze_skill_usage(period_days=30)
    
    print(f"\n📊 Skill Statistics:")
    print(f"  Total skills tracked: {len(skill_stats)}")
    
    for name, stats in skill_stats.items():
        health_icon = "✅" if stats.health_score >= 0.7 else "⚠️" if stats.health_score >= 0.5 else "❌"
        print(f"\n  {health_icon} **{name}**:")
        print(f"     - Uses: {stats.total_uses}")
        print(f"     - Success Rate: {stats.success_rate*100:.0f}%")
        print(f"     - Health Score: {stats.health_score:.2f}")
        print(f"     - Avg Duration: {stats.avg_duration:.2f}s")
        if stats.failure_patterns:
            print(f"     - Failures: {len(stats.failure_patterns)}")
    
    # Test 3: Detect usage patterns
    print("\n4. Detecting usage patterns...")
    
    patterns = skill_analyzer.detect_usage_patterns()
    
    for skill_name, skill_patterns in patterns.items():
        if skill_patterns:
            print(f"\n  📈 {skill_name}:")
            for pattern in skill_patterns[:3]:
                print(f"     - {pattern}")
    
    # Test 4: Identify skill gaps
    print("\n5. Identifying skill gaps...")
    
    gaps = skill_analyzer.identify_gaps()
    
    if gaps:
        print(f"\n  Found {len(gaps)} skill gaps:")
        for gap in gaps:
            impact_icon = "🔴" if gap.impact == "high" else "🟡"
            print(f"\n  {impact_icon} **{gap.gap_type}**:")
            print(f"     - {gap.description}")
            print(f"     - Recommendation: {gap.recommendation}")
    else:
        print("\n  ✅ No critical skill gaps identified")
    
    # Test 5: Generate evolution report
    print("\n6. Generating evolution report...")
    
    report = skill_analyzer.generate_report(period_days=30)
    
    print(f"\n📄 Evolution Report Summary:")
    print(f"  - Timestamp: {report.timestamp}")
    print(f"  - Analysis Period: {report.analysis_period_days} days")
    print(f"  - Total Skills: {report.total_skills}")
    print(f"  - Active Skills: {report.active_skills}")
    print(f"  - Overall Health: {report.overall_health:.2f}")
    
    if report.top_performers:
        print(f"\n  🏆 Top Performers:")
        for name in report.top_performers[:3]:
            stats = report.skill_stats.get(name)
            if stats:
                print(f"     - {name}: {stats.success_rate*100:.0f}% success, health: {stats.health_score:.2f}")
    
    if report.underperforming:
        print(f"\n  ⚠️  Needs Improvement:")
        for name in report.underperforming[:3]:
            stats = report.skill_stats.get(name)
            if stats:
                print(f"     - {name}: {stats.success_rate*100:.0f}% success, health: {stats.health_score:.2f}")
    
    if report.improvement_suggestions:
        print(f"\n  💡 Improvement Suggestions:")
        for suggestion in report.improvement_suggestions[:5]:
            print(f"     - {suggestion}")
    
    # Test 6: Save and verify report
    print("\n7. Saving report...")
    
    skill_analyzer._save_report(report)
    
    # Verify report file exists
    reports_dir = workspace / ".cyberclaw" / "skill_evolution"
    report_files = list(reports_dir.glob("report_*.json"))
    
    if report_files:
        latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
        print(f"\n  ✅ Report saved: {latest_report}")
        
        # Read and display report structure
        with open(latest_report, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        print(f"\n  📋 Report Structure:")
        print(f"     - Keys: {', '.join(report_data.keys())}")
        print(f"     - Skill Stats: {len(report_data.get('skill_stats', {}))} skills")
        print(f"     - Skill Gaps: {len(report_data.get('skill_gaps', []))} gaps")
    else:
        print("\n  ❌ Report file not found!")
    
    # Test 7: Get text report
    print("\n8. Generating text report...")
    
    text_report = skill_analyzer.get_report_text(report)
    print("\n" + "="*60)
    print(text_report)
    print("="*60)
    
    print("\n✅ All tests completed successfully!")
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_skill_evolution_integration())
    except Exception as e:
        print(f"\n❌ Test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
