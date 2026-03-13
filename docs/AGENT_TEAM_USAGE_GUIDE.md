# Cyberclaw Agent Team 使用指南

> 完整的多 Agent 系统使用和监控指南

---

## 🚀 快速开始

### 1. 启动 Multi-Agent Gateway

```bash
cyberclaw gateway --multi
```

**输出**:
```
🦞 Starting cyberclaw gateway in MULTI-AGENT mode on port 18790...
Configured agents: ['orchestrator', 'main', 'coding', 'research', 'reviewer', 'debugger']
Default agent: orchestrator
Routing rules: 6

2026-03-04 19:02:01 | INFO | Agent orchestrator ready
2026-03-04 19:02:01 | INFO | Agent main ready
2026-03-04 19:02:01 | INFO | Agent coding ready
2026-03-04 19:02:01 | INFO | Agent research ready
2026-03-04 19:02:01 | INFO | Agent reviewer ready
2026-03-04 19:02:01 | INFO | Agent debugger ready
```

### 2. 发送任务

**新开终端窗口**:
```bash
cyberclaw agent

> 帮我写个快速排序算法
```

### 3. 查看状态

```bash
cyberclaw status
```

---

## 📋 Agent 角色说明

| Agent | 职责 | 触发关键词 |
|-------|------|-----------|
| 👑 **orchestrator** | 任务协调者 | 复杂、完整、全栈、系统、架构 |
| **main** | 主助手 | fallback（无匹配时） |
| **coding** | 编程助手 | 代码、编程、实现、开发、function |
| **research** | 研究助手 | 搜索、查找、研究、调研、资料 |
| **reviewer** | 代码审查 | 审查、review、检查、优化、重构 |
| **debugger** | 调试助手 | 调试、debug、修复、报错、错误 |

---

## 🎯 路由规则

### 优先级系统

```
priority: 60 → orchestrator (复杂任务)
priority: 50 → coding, research (专业任务)
priority: 45 → debugger (调试任务)
priority: 40 → reviewer (审查任务)
priority:  0 → main (fallback)
```

### 匹配逻辑

1. **按优先级排序**: 高优先级先匹配
2. **关键词匹配**: 消息内容包含关键词
3. **第一条命中**: 匹配成功即停止

---

## 👥 Teams 功能

### 预设 Teams

| Team | 成员 | 策略 | Leader |
|------|------|------|--------|
| **dev-team** | coding, reviewer, debugger | parallel | coding |
| **research-team** | research, main | parallel | research |
| **fullstack-team** | research, coding, reviewer, debugger | sequential | orchestrator |
| **code-review-team** | reviewer, debugger, coding | parallel | reviewer |

### 使用 Broadcast 工具

```python
# Agent 内部使用
{
  "tool": "broadcast",
  "parameters": {
    "team": "dev-team",
    "message": "审查这个 PR 的性能问题",
    "strategy": "parallel",
    "timeout": 300
  }
}
```

---

## 📊 监控 Gateway 状态

### 方法 1: CLI Status 命令（推荐）⭐

```bash
cyberclaw status
```

**输出**:
```
🦞 cyberclaw Status

Config: ✓
Workspace: ✓
Model: qwen3.5-plus
DashScope: ✓

Multi-Agent Gateway:
  Status: ● Running (PID: 65614)
  Agents: 6 configured
  Default: orchestrator
  Routing Rules: 6
  Teams: 4

  Configured Agents:
    👑 orchestrator    (任务协调者)
    main            (主助手)
    coding          (编程助手)
    research        (研究助手)
    reviewer        (代码审查助手)
    debugger        (调试助手)

  Teams:
    • dev-team             [parallel] (leader: coding)
      Members: coding, reviewer, debugger
    • research-team        [parallel] (leader: research)
      Members: research, main
    ...
```

### 方法 2: Python 脚本

```bash
python check_gateway_status.py
```

**更详细的信息**:
- Gateway PID
- 所有 Agent 配置
- Teams 详情
- 路由规则详情

### 方法 3: Gateway 终端日志（实时）⭐

**保持 Gateway 运行的终端窗口可见**:

```bash
cyberclaw gateway --multi

# 实时日志输出:
2026-03-04 19:02:01 | INFO | Agent orchestrator ready
...
2026-03-04 19:15:00 | DEBUG | Routing message from cli:user123 to agent coding
2026-03-04 19:15:05 | INFO  | Agent coding completed task in 5.2s
```

### 方法 4: tmux 分屏监控

```bash
# 创建 tmux 会话
tmux new -s cyberclaw

# 左侧：Gateway
cyberclaw gateway --multi

# 分屏（Ctrl+b, %）

# 右侧：发送任务
cyberclaw agent

# 随时查看日志（Ctrl+b, q）
```

---

## 💬 使用示例

### 示例 1: 简单编码任务

```
用户：帮我写个快速排序算法

→ 自动路由到 coding agent
→ 返回快速排序代码实现
```

### 示例 2: 研究任务

```
用户：搜索一下 React 性能优化的最佳实践

→ 自动路由到 research agent
→ 返回搜索结果和总结
```

### 示例 3: 复杂全栈任务

```
用户：帮我开发一个完整的待办事项应用

→ 路由到 orchestrator agent
→ 自动分解任务:
   1. spawn research: 调研最佳实践
   2. spawn coding: 实现后端 API
   3. spawn coding: 实现前端界面
   4. spawn reviewer: 审查代码
   5. spawn debugger: 测试修复
→ 聚合所有结果
```

### 示例 4: 代码审查

```
用户：审查这个 PR 的性能问题

→ 路由到 reviewer agent
或使用 broadcast:
→ broadcast to code-review-team
→ 收集多个 agent 的审查意见
```

---

## 🔧 配置文件

### 位置
```
~/.cyberclaw/config.json
```

### 关键配置

```json
{
  "agents": {
    "default_agent": "orchestrator",
    "agent_list": [
      {"id": "orchestrator", "name": "任务协调者", ...},
      {"id": "main", "name": "主助手", ...},
      {"id": "coding", "name": "编程助手", ...},
      {"id": "research", "name": "研究助手", ...},
      {"id": "reviewer", "name": "代码审查助手", ...},
      {"id": "debugger", "name": "调试助手", ...}
    ],
    "bindings": [
      {"agent_id": "coding", "keywords": ["代码", "编程"], "priority": 50},
      {"agent_id": "research", "keywords": ["搜索", "研究"], "priority": 50},
      {"agent_id": "debugger", "keywords": ["调试", "debug"], "priority": 45},
      {"agent_id": "reviewer", "keywords": ["审查", "review"], "priority": 40},
      {"agent_id": "orchestrator", "keywords": ["复杂", "完整"], "priority": 60},
      {"agent_id": "main", "keywords": [], "priority": 0}
    ],
    "teams": [
      {"name": "dev-team", "members": ["coding", "reviewer", "debugger"], "strategy": "parallel"},
      {"name": "research-team", "members": ["research", "main"], "strategy": "parallel"},
      {"name": "fullstack-team", "members": ["research", "coding", "reviewer", "debugger"], "strategy": "sequential"},
      {"name": "code-review-team", "members": ["reviewer", "debugger", "coding"], "strategy": "parallel"}
    ]
  }
}
```

---

## 🛡️ 容错机制

### 错误类型与恢复

| 错误类型 | 可重试 | 恢复策略 |
|---------|-------|---------|
| NETWORK | ✅ | 重试 3 次 |
| TIMEOUT | ✅ | 重试 3 次，指数退避 |
| RATE_LIMIT | ✅ | 重试 5 次，30s 间隔 |
| BUDGET_EXCEEDED | ❌ | 中止并通知 |
| LOGIC | ❌ | 通知父 agent |

### 自动重试配置

```python
await spawn(
    task="复杂任务",
    max_retries=3,
    retry_delay=5.0,
    timeout=300
)
```

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| `AGENT_TEAM_CONFIG.md` | 完整配置指南 |
| `GATEWAY_STATUS_USAGE.md` | 状态监控指南 |
| `GATEWAY_FIX_REPORT.md` | Gateway 修复报告 |
| `check_gateway_status.py` | Python 状态检查脚本 |

---

## ❓ 常见问题

### Q1: 如何知道消息路由到了哪个 agent？

**答**: 查看 Gateway 运行终端的日志：
```
DEBUG | Routing message from cli:user123 to agent coding
```

### Q2: 如何让特定 agent 处理？

**答**: 使用关键词触发，或在消息中指定：
```
@coding 帮我写个排序算法
```

### Q3: Gateway 离线怎么办？

**答**: 
```bash
# 检查状态
cyberclaw status

# 重新启动
cyberclaw gateway --multi
```

### Q4: 如何停止 Gateway？

**答**: 
```bash
# Ctrl+C 停止前台运行
# 或后台运行时：
kill $(pgrep -f "cyberclaw gateway")
```

---

## 🎯 最佳实践

1. **保持 Gateway 终端可见** - 实时监控 agent 活动
2. **使用 tmux 分屏** - 同时查看日志和发送任务
3. **合理配置优先级** - 确保路由准确
4. **定期查看状态** - `cyberclaw status` 或 `python check_gateway_status.py`

---

**最后更新**: 2026-03-04
