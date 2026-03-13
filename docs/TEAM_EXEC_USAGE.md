# cyberclaw teams exec - Team 任务执行命令

## 🎉 新功能

现在可以使用 `cyberclaw teams exec` 命令**明确触发** team 模式执行任务！

---

## 📋 命令格式

```bash
cyberclaw teams exec <team-name> "<task-description>" [options]
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `team-name` | Team 名称（必须是配置的 team） | 必填 |
| `task-description` | 任务描述 | 必填 |
| `--timeout`, `-t` | 超时时间（秒） | 600 |
| `--wait`, `-w` | 等待完成 | True |

---

## 🚀 使用示例

### 示例 1: 开发团队

```bash
cyberclaw teams exec dev-team "实现一个完整的库房管理系统，后端用 FastAPI，前端用 Streamlit"
```

**预期行为**:
1. Orchestrator 接收任务
2. 分解为子任务：
   - backend-worker: 实现 FastAPI 后端
   - frontend-worker: 实现 Streamlit 前端
   - test-worker: 编写测试
3. 并行执行所有 workers
4. 聚合结果

---

### 示例 2: 研究团队

```bash
cyberclaw teams exec research-team "调研 2026 年 AI 编程助手的最佳实践"
```

**预期行为**:
1. research-worker: 搜索 AI 编程助手
2. analysis-worker: 分析最佳实践
3. report-worker: 生成调研报告

---

### 示例 3: 代码审查团队

```bash
cyberclaw teams exec code-review-team "审查这个 PR 的性能问题和安全隐患"
```

**预期行为**:
1. reviewer: 代码质量审查
2. debugger: 安全问题检查
3. coding: 性能优化建议

---

### 示例 4: 全栈团队（顺序执行）

```bash
cyberclaw teams exec fullstack-team "从零开始构建一个博客系统"
```

**预期行为**:
1. research: 调研博客系统最佳实践
2. coding: 实现后端 API
3. reviewer: 审查代码
4. debugger: 测试验证

---

## 📊 配置的 Teams

查看可用的 teams：

```bash
cyberclaw teams list
```

**示例输出**:
```
┌────────────────────┬───────────────────────────┬─────────┬────────────┐
│ Name               │ Members                   │ Leader  │ Strategy   │
├────────────────────┼───────────────────────────┼─────────┼────────────┤
│ dev-team           │ coding, reviewer, debugger│ coding  │ parallel   │
│ research-team      │ research, main            │ research│ parallel   │
│ fullstack-team     │ research, coding, ...     │ orchestrator │ sequential │
│ code-review-team   │ reviewer, debugger, coding│ reviewer│ parallel   │
└────────────────────┴───────────────────────────┴─────────┴────────────┘
```

---

## 🔍 工作原理

### 执行流程

```
用户: cyberclaw teams exec dev-team "实现库房管理系统"
        │
        ▼
┌─────────────────────────────────┐
│ 1. 验证 Team 配置                │
│    - 检查 team 是否存在          │
│    - 显示 team 信息              │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 2. 启动 Gateway                  │
│    - 创建 MessageBus            │
│    - 启动所有 agents            │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 3. Orchestrator 分解任务         │
│    - 分析任务需求               │
│    - 分解为子任务               │
│    - 使用 spawn 创建 workers     │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 4. Workers 并行执行              │
│    - research-worker: 调研      │
│    - backend-worker: 实现后端   │
│    - frontend-worker: 实现前端  │
│    - test-worker: 编写测试      │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 5. 聚合结果                      │
│    - 整合所有 workers 的输出     │
│    - 生成完整报告/代码          │
└─────────────────────────────────┘
        │
        ▼
    ✅ 完成任务
```

---

## 📝 日志输出

### 启动阶段

```
🚀 Executing task with team: dev-team
Task: 实现一个完整的库房管理系统...

✓ Team: dev-team
  Members: coding, reviewer, debugger
  Strategy: parallel
  Timeout: 600s
```

### 执行阶段

```
📋 Decomposing task...
⚙️  Executing with workers...

📥 [ORCHESTRATOR] Routing message from cli:team-exec
🤖 [orchestrator] Processing: Task: 实现...

🔄 [orchestrator] Tool call: spawn(batch=[
  {"task": "调研最佳实践", "label": "research-worker"},
  {"task": "实现后端 API", "label": "backend-worker"},
  {"task": "实现前端界面", "label": "frontend-worker"}
])

# Workers 开始工作
📥 [RESEARCH-WORKER] Routing message
🤖 [research-worker] Processing: ...
🔄 [research-worker] Tool call: web_search({...})

📥 [BACKEND-WORKER] Routing message
🤖 [backend-worker] Processing: ...
🔄 [backend-worker] Tool call: write_file({...})
```

### 完成阶段

```
✅ Task completed!

Result:
已完成库房管理系统的实现，包括：
1. FastAPI 后端 API
2. Streamlit 前端界面
3. 数据库模型
4. 单元测试
```

---

## ⚙️ 配置 Teams

在 `~/.cyberclaw/config.json` 中配置 teams：

```json
{
  "agents": {
    "teams": [
      {
        "name": "dev-team",
        "members": ["coding", "reviewer", "debugger"],
        "leader": "coding",
        "strategy": "parallel"
      },
      {
        "name": "research-team",
        "members": ["research", "main"],
        "leader": "research",
        "strategy": "parallel"
      },
      {
        "name": "fullstack-team",
        "members": ["research", "coding", "reviewer", "debugger"],
        "leader": "orchestrator",
        "strategy": "sequential"
      }
    ]
  }
}
```

---

## 🎯 最佳实践

### 何时使用 teams exec

✅ **适合使用**:
- 复杂全栈任务（需要多方面专业知识）
- 需要调研 + 实现 + 测试的完整流程
- 大型项目（预计耗时 >30 分钟）

❌ **不适合**:
- 简单任务（直接 `cyberclaw agent`）
- 单一技能任务（用特定 agent）
- 快速查询

### 选择合适的 Team

| 任务类型 | 推荐 Team |
|---------|----------|
| 全栈开发 | fullstack-team |
| 后端开发 | dev-team |
| 前端开发 | dev-team |
| 调研报告 | research-team |
| 代码审查 | code-review-team |
| 数据分析 | research-team |

---

## 🔧 故障排查

### 问题 1: Team 不存在

```bash
# 错误: ❌ Team 'xxx' not found

# 解决：查看可用 teams
cyberclaw teams list

# 或者添加新 team 到 config
```

### 问题 2: 超时

```bash
# 错误: Task timeout

# 解决：增加超时时间
cyberclaw teams exec dev-team "任务" --timeout 1200
```

### 问题 3: Orchestrator 不 spawn workers

**原因**: LLM 选择直接完成任务

**解决**: 
- 任务描述更明确，强调需要多 agent 协作
- 或者等待后续版本修复（增强 orchestrator 强制逻辑）

---

## 📚 相关文档

- `AGENT_TEAM_CONFIG.md` - Team 配置指南
- `GATEWAY_INTERACTIVE_USAGE.md` - Gateway 使用
- `ORCHESTRATOR_FINAL_FIX.md` - Orchestrator 修复

---

**最后更新**: 2026-03-05  
**版本**: 1.0  
**状态**: ✅ 生产就绪

