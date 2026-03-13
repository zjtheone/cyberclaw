# Skills 进化未生效问题诊断

## 🔍 诊断结果

经过深入检查，发现 **Skills 进化系统正在运行，但存在几个问题**：

---

## 📊 现状分析

### 1. ✅ 系统正在运行

**证据**：
```bash
# Skill 进化报告已生成
ls ~/.cyberclaw/workspace/.cyberclaw/skill_evolution/
# 输出：
report_20260309_183107.json
report_20260309_183251.json
report_20260309_223345.json
report_20260309_223418.json

# 工具统计已记录
cat ~/.cyberclaw/workspace/.cyberclaw/tool_stats.json
# 输出：
{
  "exec": {"total_calls": 9007, "success_rate": 1.0, ...},
  "read_file": {"total_calls": 9160, ...},
  "edit_file": {"total_calls": 2466, ...},
  ...
}
```

### 2. ❌ 问题：Skill 使用统计为空

**问题**：
```bash
cat ~/.cyberclaw/workspace/.cyberclaw/skill_usage.json
# 输出：
{}
```

**原因**：Skill 统计为空，导致进化报告内容为空。

### 3. ❌ 问题：进化报告内容为空

```json
{
  "timestamp": "2026-03-09T22:34:18.621795",
  "total_skills": 0,
  "active_skills": 0,
  "overall_health": 0.0,
  "skill_stats": {},
  "top_performers": [],
  "underperforming": [],
  "skill_gaps": [],
  "improvement_suggestions": [],
  "new_skill_recommendations": []
}
```

---

## 🐛 根本原因分析

### 问题 1: Skills 目录结构与预期不符

**预期结构**：
```
skills/
├── skill_name/
│   ├── skill.py         ← 缺失！
│   ├── __init__.py
│   └── ...
```

**实际结构**：
```
skills/
├── jdcloud/
│   ├── jdcloud_mongodb.py  ← 不标准的命名
│   └── ...
├── jdcloud-rds/
│   ├── __init__.py
│   └── test_skill.py
└── ...
```

**影响**：
- `SkillEvolutionAnalyzer` 无法识别这些为有效的 skills
- 统计时跳过这些目录

### 问题 2: Skill 追踪逻辑未正确识别

**代码位置**：`cyberclaw/agent/loop.py`

```python
# 当前代码追踪的是 tool 使用，不是 skill 使用
self.skill_analyzer.track_skill_usage(
    skill_name=name,  # ← 这里传的是 tool_name
    success=success,
    duration=duration,
    ...
)
```

**问题**：
- Tool 和 Skill 是不同概念
- Tool: 内置工具（read_file, edit_file, exec 等）
- Skill: 用户创建的自定义技能包

### 问题 3: Skill 加载机制可能未实现

**检查代码**：
```bash
grep -r "load.*skill\|import.*skill" cyberclaw/agent/loop.py
# 结果：没有找到显式的 skill 加载逻辑
```

**可能的情况**：
- Skills 目录下的自定义技能没有被动态加载
- 只追踪了内置工具的使用，未追踪自定义技能

---

## 🔧 解决方案

### 方案 1: 修复 Skill 识别逻辑

**修改**：`cyberclaw/agent/skill_evolution.py`

```python
def _discover_skills(self) -> list[str]:
    """发现所有可用的 skills"""
    skills = []
    if not self.skills_dir.exists():
        return skills
    
    for skill_dir in self.skills_dir.iterdir():
        if skill_dir.is_dir():
            # 检查是否有 __init__.py 或 skill.py
            if (skill_dir / "__init__.py").exists() or \
               (skill_dir / "skill.py").exists() or \
               list(skill_dir.glob("*.py")):  # ← 放宽条件
                skills.append(skill_dir.name)
    
    return skills
```

### 方案 2: 区分 Tool 和 Skill 统计

**修改**：`cyberclaw/agent/loop.py`

```python
# 在 _execute_tool 中添加 skill 识别
async def _execute_tool(self, name: str, arguments: dict, ...):
    # 判断是 tool 还是 skill
    is_skill = name in self._loaded_skills  # 需要维护 skill 列表
    
    if is_skill:
        # 追踪 skill 使用
        self.skill_analyzer.track_skill_usage(
            skill_name=name,
            success=success,
            ...
        )
    else:
        # 追踪 tool 使用（现有逻辑）
        self.tool_optimizer.record_tool_usage(
            tool_name=name,
            ...
        )
```

### 方案 3: 完善 Skill 加载机制

**新增**：`cyberclaw/agent/loop.py`

```python
def _load_custom_skills(self):
    """加载自定义技能"""
    skills_dir = self.workspace / "skills"
    if not skills_dir.exists():
        return
    
    loaded_skills = []
    for skill_path in skills_dir.iterdir():
        if skill_path.is_dir():
            # 尝试加载 skill
            try:
                # 动态导入 skill 模块
                skill_module = importlib.import_module(
                    f"skills.{skill_path.name}"
                )
                loaded_skills.append(skill_path.name)
                logger.info(f"Loaded custom skill: {skill_path.name}")
            except Exception as e:
                logger.warning(f"Failed to load skill {skill_path.name}: {e}")
    
    self._loaded_skills = set(loaded_skills)
```

---

## 💡 临时验证方法

### 手动触发 Skill 进化分析

```python
# 在 Python 中执行
from pathlib import Path
from cyberclaw.agent.skill_evolution import SkillEvolutionAnalyzer
from cyberclaw.agent.experience import ExperienceRepository
from cyberclaw.agent.metrics import MetricsTracker
from cyberclaw.agent.tool_optimizer import ToolOptimizer

workspace = Path.home() / ".cyberclaw" / "workspace"

# 初始化（需要其他组件）
analyzer = SkillEvolutionAnalyzer(
    workspace=workspace,
    experience_repo=ExperienceRepository(workspace),
    metrics_tracker=MetricsTracker(workspace),
    tool_optimizer=ToolOptimizer(workspace),
)

# 生成报告
report = analyzer.analyze_evolution()
print(f"Total skills: {report.total_skills}")
print(f"Top performers: {report.top_performers}")
print(f"Suggestions: {report.improvement_suggestions}")
```

### 检查 Skill 目录结构

```bash
# 查看所有 skill 目录
for dir in ~/.cyberclaw/workspace/skills/*/; do
  echo "=== $(basename $dir) ==="
  ls "$dir" | head -5
done
```

---

## 📋 总结

### 当前状态

| 功能 | 状态 | 问题 |
|------|------|------|
| Tool 统计 | ✅ 正常 | 9007+ 次调用已记录 |
| Skill 发现 | ❌ 异常 | 无法识别自定义 skills |
| Skill 统计 | ❌ 空 | skill_usage.json 为空 |
| 进化报告 | ⚠️ 部分正常 | 报告生成但内容为空 |
| Skill 加载 | ❌ 未实现 | 没有动态加载机制 |

### 需要修复的优先级

1. **P0 - 高优先级**
   - 修复 skill 发现逻辑（放宽识别条件）
   - 实现 skill 加载机制
   - 区分 tool 和 skill 统计

2. **P1 - 中优先级**
   - 完善 skill 目录结构规范
   - 添加 skill 创建模板
   - 文档化 skill 开发流程

3. **P2 - 低优先级**
   - 优化 skill 进化报告生成
   - 添加 skill 使用可视化
   - 实现 skill 自动优化建议

### 快速验证命令

```bash
# 1. 检查 skill 进化报告
cat ~/.cyberclaw/workspace/.cyberclaw/skill_evolution/*.json | jq '.'

# 2. 检查 tool 统计
cat ~/.cyberclaw/workspace/.cyberclaw/tool_stats.json | jq '.tools | keys'

# 3. 检查 skill 使用统计
cat ~/.cyberclaw/workspace/.cyberclaw/skill_usage.json

# 4. 检查 skills 目录
ls -la ~/.cyberclaw/workspace/skills/
```

---

**诊断时间**: 2026-03-10  
**状态**: ❌ Skill 进化系统未正确工作  
**原因**: Skill 识别和加载机制不完善  
**建议**: 按优先级修复 P0 问题
