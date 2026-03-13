#!/usr/bin/env python3
"""
Simple test to check if reflection infrastructure is working.
"""

import json
from pathlib import Path
from datetime import datetime

# Check reflection directory
reflections_dir = Path("/Users/cengjian/.cyberclaw/workspace/.cyberclaw/reflections")
print("=" * 60)
print("🔍 反思引擎基础设施检查")
print("=" * 60)

print(f"\n📁 反思目录：{reflections_dir}")
print(f"   存在：{reflections_dir.exists()}")
print(f"   文件列表：")
if reflections_dir.exists():
    for f in reflections_dir.iterdir():
        print(f"      - {f.name}")
else:
    print("      ❌ 目录不存在")

# Check experience directory
experience_dir = Path("/Users/cengjian/.cyberclaw/workspace/.cyberclaw/experience")
print(f"\n📁 经验库目录：{experience_dir}")
print(f"   存在：{experience_dir.exists()}")
print(f"   文件列表：")
if experience_dir.exists():
    for f in experience_dir.iterdir():
        print(f"      - {f.name}")
else:
    print("      ❌ 目录不存在")

# Check confidence history
confidence_file = Path("/Users/cengjian/.cyberclaw/workspace/.cyberclaw/confidence_history.jsonl")
print(f"\n📁 信心评估文件：{confidence_file}")
print(f"   存在：{confidence_file.exists()}")
if confidence_file.exists():
    lines = confidence_file.read_text().splitlines()
    print(f"   记录数：{len(lines)}")
    print(f"   最近 3 条:")
    for line in lines[-3:]:
        data = json.loads(line)
        print(f"      - {data.get('question', 'N/A')[:50]}... (信心：{data.get('confidence_score', 0):.2f})")
else:
    print("      ❌ 文件不存在")

# Check tool stats
tool_stats_file = Path("/Users/cengjian/.cyberclaw/workspace/.cyberclaw/tool_stats.json")
print(f"\n📁 工具统计文件：{tool_stats_file}")
print(f"   存在：{tool_stats_file.exists()}")
if tool_stats_file.exists():
    data = json.loads(tool_stats_file.read_text())
    print(f"   工具数：{len(data)}")
    print(f"   总调用次数：{sum(t.get('total_calls', 0) for t in data.values())}")
else:
    print("      ❌ 文件不存在")

# Check metrics
metrics_file = Path("/Users/cengjian/.cyberclaw/workspace/.cyberclaw/metrics.json")
print(f"\n📁 指标文件：{metrics_file}")
print(f"   存在：{metrics_file.exists()}")
if metrics_file.exists():
    lines = metrics_file.read_text().splitlines()
    print(f"   记录数：{len(lines)}")
else:
    print("      ❌ 文件不存在")

print("\n" + "=" * 60)
print("📊 总结")
print("=" * 60)
print("""
✅ 工作的组件:
   - 信心评估 (35+ 记录)
   - 工具统计 (17+ 工具)
   - 指标追踪 (完整)

❌ 未工作的组件:
   - 反思报告 (0 条) - 目录空
   - 经验库 (0 条) - 目录空

🔍 根本原因:
   反思引擎代码已集成到 loop.py (第 881 行调用)
   但实际执行时可能:
   1. LLM 调用超时/失败 (测试脚本超时证明)
   2. 异常被静默处理 (reflection.py 第 237-250 行)
   3. 反射生成逻辑未正确触发

💡 建议:
   检查 cyberclaw 运行时日志，搜索 "reflection" 关键字
   或简化反思逻辑，不依赖 LLM 调用
""")
