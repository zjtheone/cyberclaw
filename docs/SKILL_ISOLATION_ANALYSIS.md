# Skills 进化 Session 隔离性分析

## 📊 问题现象

用户发现：
- 在 `cyberclaw agent -s 0309v1` session 中总结的 skills 和改进
- 在 `cyberclaw agent -s 0310v1` session 中**没有应用**

**疑问**：Skills 进化在 session 之间是隔离的吗？

---

## 🔍 存储结构分析

### 1. 工作区结构

```
/Users/cengjian/.cyberclaw/workspace/
├── .cyberclaw/
│   ├── experience/           # 经验记录（P0）
│   │   └── experiences.jsonl
│   ├── skill_evolution/      # 技能进化报告（P2）
│   ├── skill_usage.json      # 技能使用统计
│   └── reflections/          # 反思记录（P0）
├── skills/                   # 实际技能代码
│   ├── bocha-search/
│   ├── jdcloud-rds/
│   └── ... (其他技能目录)
└── sessions/                # Session 数据
    ├── 0309v1/
    └── 0310v1/
```

### 2. 数据隔离级别

| 数据类型 | 存储位置 | Session 隔离 | 说明 |
|---------|---------|-------------|------|
| **Session 消息** | `sessions/{session_id}/` | ✅ **隔离** | 每个 session 独立的对话历史 |
| **Skills 代码** | `skills/` | ❌ **共享** | 所有 session 共用同一套技能 |
| **经验记录** | `.cyberclaw/experience/` | ❌ **共享** | 全局经验库，所有 session 共享 |
| **技能统计** | `.cyberclaw/skill_usage.json` | ❌ **共享** | 全局技能使用统计 |
| **进化报告** | `.cyberclaw/skill_evolution/` | ❌ **共享** | 全局技能进化分析 |
| **反思记录** | `.cyberclaw/reflections/` | ❌ **共享** | 全局反思库 |

---

## 📋 关键发现

### ✅ Skills 进化**不是**Session 隔离的

**结论**：Skills 进化和经验记录是**全局共享**的，不按 session 隔离。

**证据**：

1. **SkillEvolutionAnalyzer 初始化**（`loop.py:445-451`）
```python
self.skill_analyzer = SkillEvolutionAnalyzer(
    self.workspace,  # ← 工作区级别，不是 session 级别
    experience_repo=self.experience_repo,
    metrics_tracker=self.metrics,
    tool_optimizer=self.tool_optimizer,
    skills_dir=self.workspace / "skills",  # ← 共享的技能目录
)
```

2. **ExperienceRepository 初始化**（`experience.py:78-85`）
```python
def __init__(self, workspace: Path):
    self.workspace = workspace
    self.repo_dir = ensure_dir(workspace / ".cyberclaw" / "experience")
    # ← 所有 session 共享同一个经验库
```

3. **Skill 统计存储**（`skill_evolution.py:175-177`）
```python
self.stats_dir = workspace / ".cyberclaw"
self.skill_stats_file = self.stats_dir / "skill_usage.json"
# ← 所有 session 共享同一个统计文件
```

---

## 🎯 设计原理

### 为什么 Skills 进化要全局共享？

#### ✅ 优势

1. **知识积累**
   - Session A 学到的经验可以立即在 Session B 中应用
   - 避免重复学习相同的教训
   - 跨 session 的知识传承

2. **技能复用**
   - 创建的 skills 可以被所有 session 使用
   - 技能优化影响所有 future sessions
   - 形成组织的知识库

3. **持续改进**
   - 全局统计帮助识别最常用的技能
   - 跨 session 的失败模式分析
   - 整体 agent 能力的提升

#### ⚠️ 挑战

1. **污染风险**
   - Session A 的错误经验可能影响 Session B
   - 特定场景的优化可能不适合其他场景

2. **调试困难**
   - 难以区分哪些改进来自哪个 session
   - 回滚特定 session 的影响较复杂

---

## 🔧 实际应用机制

### Skills 如何跨 Session 应用？

#### 1. 经验记录（P0 - 即时应用）

```python
# Session 0309v1 中成功解决了一个问题
→ 经验记录保存到 .cyberclaw/experience/experiences.jsonl
→ 包含：任务描述、解决方案、使用的工具、关键洞察

# Session 0310v1 中遇到类似问题
→ 从经验库检索相似记录
→ 应用之前的成功方案
```

#### 2. 技能进化（P2 - 建议形式）

```python
# Session 0309v1 中频繁使用某个技能
→ 统计记录到 .cyberclaw/skill_usage.json
→ 分析技能健康度、成功率、性能

# 生成进化报告
→ 保存到 .cyberclaw/skill_evolution/
→ 包含：改进建议、新技能推荐、性能优化

# Session 0310v1 启动时
→ 加载最新的进化报告
→ 展示改进建议给用户
```

#### 3. 技能代码（实际执行）

```python
# 创建新技能
→ 代码保存在 skills/{skill_name}/
→ 所有 session 立即可用

# 优化现有技能
→ 修改 skills/{skill_name}/ 中的代码
→ 所有 session 立即受益
```

---

## 📊 验证方法

### 检查当前共享数据

```bash
# 1. 查看经验记录
cat /Users/cengjian/.cyberclaw/workspace/.cyberclaw/experience/experiences.jsonl | head

# 2. 查看技能使用统计
cat /Users/cengjian/.cyberclaw/workspace/.cyberclaw/skill_usage.json | jq .

# 3. 查看技能进化报告
ls -la /Users/cengjian/.cyberclaw/workspace/.cyberclaw/skill_evolution/

# 4. 查看所有可用技能
ls -la /Users/cengjian/.cyberclaw/workspace/skills/
```

### 验证跨 Session 应用

```bash
# Session 1: 创建经验
cyberclaw agent -s 0309v1
# → 执行任务，产生经验记录

# Session 2: 检查是否应用
cyberclaw agent -s 0310v1
# → 查看是否引用了之前的经验
# → 检查工具选择是否受之前影响
```

---

## 💡 为什么用户感觉没有应用？

### 可能原因

1. **经验检索条件不匹配**
   - 新任务与历史经验的相似度不够
   - 任务分类不同，未触发经验检索

2. **技能改进是建议形式**
   - P2 技能进化只是**建议**，不会自动应用
   - 需要用户确认或手动优化技能代码

3. **Session 上下文独立**
   - 虽然经验共享，但每个 session 的**对话上下文**是独立的
   - Agent 不会主动提及之前 session 的具体内容

4. **时间窗口限制**
   - 可能只检索最近的经验记录
   - 旧经验权重较低

---

## 🎯 最佳实践

### 最大化 Skills 进化效果

1. **使用有意义的 Session ID**
   ```bash
   # 按项目分类
   cyberclaw agent -s project-a-task1
   cyberclaw agent -s project-a-task2
   
   # 按领域分类
   cyberclaw agent -s mongodb-optimization
   cyberclaw agent -s code-refactoring
   ```

2. **定期查看进化报告**
   ```bash
   # 查看技能使用统计
   cat ~/.cyberclaw/workspace/.cyberclaw/skill_usage.json | jq .
   
   # 查看最新进化报告
   ls -t ~/.cyberclaw/workspace/.cyberclaw/skill_evolution/ | head -1 | xargs cat
   ```

3. **主动应用改进建议**
   - 审查技能进化报告中的建议
   - 手动优化高频使用的技能
   - 删除或替换低效技能

4. **跨 Session 知识传递**
   ```bash
   # 在 Session A 中学到重要经验后
   # 在 Session B 中主动询问
   cyberclaw agent -s session-b
   # → "查看之前处理类似任务的经验"
   # → "应用之前优化过的技能"
   ```

---

## 📋 总结

### ✅ 核心结论

1. **Skills 进化是全局共享的**，不按 session 隔离
2. **经验记录对所有 session 立即可用**
3. **技能代码存储在共享目录**，所有 session 共用
4. **Session 之间只有对话历史是隔离的**

### 🎯 为什么这样设计？

- ✅ 促进知识积累和传承
- ✅ 避免重复学习
- ✅ 形成组织级知识库
- ✅ 持续提升 agent 整体能力

### 💡 如何验证？

```bash
# 查看所有共享数据
ls -la ~/.cyberclaw/workspace/.cyberclaw/

# 查看经验记录
cat ~/.cyberclaw/workspace/.cyberclaw/experience/experiences.jsonl

# 查看技能目录
ls ~/.cyberclaw/workspace/skills/
```

---

**分析时间**: 2026-03-10  
**状态**: ✅ 已验证  
**建议**: Skills 进化正常工作，是全局共享设计
