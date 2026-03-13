# Cyberclaw Agent Team 配置与使用指南

> 本文档介绍如何配置和使用 Cyberclaw 的 Agent Team 功能来运行复杂的多步骤任务。

---

## 📋 目录

- [快速开始](#-快速开始)
- [配置说明](#-配置说明)
- [Agent 角色](#-agent-角色)
- [路由规则](#-路由规则)
- [Team 功能](#-team-功能)
- [使用示例](#-使用示例)
- [高级用法](#-高级用法)
- [监控与调试](#-监控与调试)
- [最佳实践](#-最佳实践)
- [故障排查](#-故障排查)

---

## 🚀 快速开始

### 1. 配置文件位置

```bash
~/.cyberclaw/config.json
```

### 2. 启动多 Agent 模式

```bash
# 单 Agent 模式（传统方式）
cyberclaw agent

# 多 Agent 模式（推荐，支持智能路由）
cyberclaw gateway --multi
```

### 3. 验证配置

```bash
# 列出所有配置的 teams
cyberclaw teams list

# 查看特定 team 详情
cyberclaw teams info dev-team

# 验证 team 配置是否有效
cyberclaw teams validate dev-team
```

---

## 📖 配置说明

### 完整配置示例

```json
{
  "agents": {
    "defaults": {
      "id": "main",
      "workspace": "~/.cyberclaw/workspace",
      "model": "qwen3.5-plus",
      "temperature": 0.5,
      "max_tokens": 8192,
      "max_tool_iterations": 100,
      "context_window": 400000,
      "auto_verify": true,
      "sandbox": {},
      "permission_mode": "auto",
      "thinking_budget": 1024,
      "frequency_penalty": 0.5,
      "subagents": {
        "max_spawn_depth": 3,
        "max_children_per_agent": 10,
        "max_concurrent": 16,
        "run_timeout_seconds": 900,
        "archive_after_minutes": 60
      }
    },
    "default_agent": "orchestrator",
    "agent_list": [
      {
        "id": "orchestrator",
        "name": "任务协调者",
        "workspace": "~/.cyberclaw/workspace-orchestrator",
        "model": "qwen3.5-plus",
        "temperature": 0.6,
        "max_tokens": 16384,
        "max_tool_iterations": 150,
        "subagents": {
          "max_spawn_depth": 3,
          "max_children_per_agent": 15,
          "max_concurrent": 20
        }
      },
      {
        "id": "main",
        "name": "主助手",
        "workspace": "~/.cyberclaw/workspace-main"
      },
      {
        "id": "coding",
        "name": "编程助手",
        "workspace": "~/.cyberclaw/workspace-coding",
        "temperature": 0.3
      },
      {
        "id": "research",
        "name": "研究助手",
        "workspace": "~/.cyberclaw/workspace-research",
        "temperature": 0.7
      },
      {
        "id": "reviewer",
        "name": "代码审查助手",
        "workspace": "~/.cyberclaw/workspace-reviewer",
        "temperature": 0.2
      },
      {
        "id": "debugger",
        "name": "调试助手",
        "workspace": "~/.cyberclaw/workspace-debugger",
        "temperature": 0.4
      }
    ],
    "bindings": [
      {
        "agent_id": "coding",
        "keywords": ["代码", "编程", "实现", "开发", "function", "class"],
        "priority": 50
      },
      {
        "agent_id": "research",
        "keywords": ["搜索", "查找", "研究", "调研", "资料"],
        "priority": 50
      },
      {
        "agent_id": "orchestrator",
        "keywords": ["复杂", "完整", "全栈", "系统", "架构"],
        "priority": 60
      },
      {
        "agent_id": "main",
        "channels": [],
        "priority": 0
      }
    ],
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
  },
  "tools": {
    "agent_to_agent": {
      "enabled": true,
      "allow": ["orchestrator", "main", "coding", "research", "reviewer", "debugger"],
      "deny": [],
      "max_ping_pong_turns": 10
    },
    "sessions": {
      "visibility": "tree"
    }
  }
}
```

---

## 🤖 Agent 角色

### Agent 职责说明

| Agent ID | 名称 | 职责 | 适用场景 | 推荐温度 |
|----------|------|------|---------|---------|
| `orchestrator` | 任务协调者 | 分解复杂任务，协调多个 worker | 全栈开发、系统设计、多步骤项目 | 0.6 |
| `main` | 主助手 | 通用任务处理 | 日常对话、简单查询、fallback | 0.5 |
| `coding` | 编程助手 | 代码编写和实现 | 功能开发、算法实现、API 开发 | 0.3 |
| `research` | 研究助手 | 信息收集和调研 | 文献搜索、技术分析、竞品调研 | 0.7 |
| `reviewer` | 代码审查助手 | 代码审查和优化建议 | Code Review、性能优化、安全审计 | 0.2 |
| `debugger` | 调试助手 | 问题诊断和修复 | Bug 修复、错误分析、单元测试 | 0.4 |

### 推荐配置参数

```json
{
  "coding": {
    "temperature": 0.3,
    "max_tokens": 16384,
    "max_tool_iterations": 200
  },
  "research": {
    "temperature": 0.7,
    "max_tokens": 16384,
    "max_tool_iterations": 150
  },
  "reviewer": {
    "temperature": 0.2,
    "max_tokens": 8192,
    "max_tool_iterations": 100
  },
  "debugger": {
    "temperature": 0.4,
    "max_tokens": 16384,
    "max_tool_iterations": 200
  },
  "orchestrator": {
    "temperature": 0.6,
    "max_tokens": 16384,
    "max_tool_iterations": 150,
    "subagents": {
      "max_spawn_depth": 3,
      "max_children_per_agent": 15,
      "max_concurrent": 20
    }
  }
}
```

---

## 🎯 路由规则

### Binding 配置结构

```json
{
  "agent_id": "coding",
  "comment": "编程相关任务",
  "channels": ["cli", "telegram"],
  "chat_ids": ["123456"],
  "chat_pattern": "^group_.*",
  "keywords": ["代码", "编程", "function"],
  "priority": 50
}
```

### 匹配条件说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `agent_id` | string | 目标 agent ID | `"coding"` |
| `channels` | string[] | 匹配的 channel 列表 | `["cli", "telegram"]` |
| `chat_ids` | string[] | 匹配的 chat_id 列表 | `["123456", "789012"]` |
| `chat_pattern` | string | chat_id 正则表达式 | `"^group_.*"` |
| `keywords` | string[] | 消息内容关键词 | `["代码", "编程"]` |
| `priority` | number | 优先级（越大越优先） | `50` |

### 匹配逻辑

1. **按优先级排序**: 高优先级的 binding 先匹配
2. **AND 逻辑**: 所有指定条件都必须满足
3. **空列表 = 不限制**: `channels: []` 表示匹配所有 channel
4. **第一条匹配**: 命中第一条规则后即停止

### 路由规则示例

```json
{
  "bindings": [
    {
      "agent_id": "vip",
      "chat_ids": ["vip_user_123"],
      "priority": 100
    },
    {
      "agent_id": "urgent",
      "keywords": ["紧急", "urgent", "急"],
      "priority": 80
    },
    {
      "agent_id": "coding",
      "keywords": ["代码", "编程", "实现"],
      "channels": ["cli"],
      "priority": 50
    },
    {
      "agent_id": "research",
      "keywords": ["搜索", "研究", "调研"],
      "priority": 50
    },
    {
      "agent_id": "orchestrator",
      "keywords": ["复杂", "完整", "全栈", "系统"],
      "priority": 60
    },
    {
      "agent_id": "main",
      "channels": [],
      "priority": 0
    }
  ]
}
```

---

## 👥 Team 功能

### Team 配置结构

```json
{
  "name": "dev-team",
  "members": ["coding", "reviewer", "debugger"],
  "leader": "coding",
  "strategy": "parallel"
}
```

### 执行策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `parallel` | 并行执行所有成员 | 独立任务，需要快速响应 |
| `sequential` | 顺序执行每个成员 | 依赖前一个结果的任务 |
| `leader_delegate` | 仅 leader 执行 | 有明确负责人的场景 |

### 预设 Teams

```json
{
  "teams": [
    {
      "name": "dev-team",
      "comment": "开发团队 - 并行处理编码任务",
      "members": ["coding", "reviewer", "debugger"],
      "leader": "coding",
      "strategy": "parallel"
    },
    {
      "name": "research-team",
      "comment": "研究团队 - 并行收集信息",
      "members": ["research", "main"],
      "leader": "research",
      "strategy": "parallel"
    },
    {
      "name": "fullstack-team",
      "comment": "全栈团队 - 顺序执行完整流程",
      "members": ["research", "coding", "reviewer", "debugger"],
      "leader": "orchestrator",
      "strategy": "sequential"
    },
    {
      "name": "code-review-team",
      "comment": "代码审查团队 - 多维度审查",
      "members": ["reviewer", "debugger", "coding"],
      "leader": "reviewer",
      "strategy": "parallel"
    }
  ]
}
```

---

## 💬 使用示例

### 场景 1: 简单编码任务

```
用户：帮我写一个快速排序算法

→ 自动路由到 coding agent（关键词"排序算法"匹配）
```

### 场景 2: 研究任务

```
用户：搜索一下 React 性能优化的最佳实践

→ 自动路由到 research agent（关键词"搜索"匹配）
```

### 场景 3: 复杂全栈任务

```
用户：帮我开发一个完整的待办事项应用，包括前端和后端

→ 路由到 orchestrator agent（关键词"完整"匹配）
→ Orchestrator 自动分解:
   1. spawn research: 调研类似应用的最佳实践
   2. spawn coding: 实现后端 API 和数据库
   3. spawn coding: 实现前端界面
   4. spawn reviewer: 审查代码质量
   5. spawn debugger: 测试和修复问题
→ 聚合所有结果，生成完整报告
```

### 场景 4: 代码审查

```
用户：请审查这个 PR 的性能问题

→ 路由到 reviewer agent
→ 或使用 broadcast 工具:
   {
     "tool": "broadcast",
     "parameters": {
       "team": "code-review-team",
       "message": "审查这个 PR 的性能问题",
       "strategy": "parallel"
     }
   }
```

### 场景 5: 批量 Spawn Workers

```python
# Agent 内部使用 spawn 工具
{
  "tool": "spawn",
  "parameters": {
    "batch": [
      {"task": "搜索 React 最佳实践", "label": "react-research"},
      {"task": "搜索 Vue 最佳实践", "label": "vue-research"},
      {"task": "搜索 Angular 最佳实践", "label": "angular-research"}
    ],
    "wait": true,
    "timeout": 600
  }
}
```

---

## 🔧 高级用法

### 1. 错误重试配置

```python
{
  "tool": "spawn",
  "parameters": {
    "task": "复杂的数据处理任务",
    "max_retries": 3,
    "retry_delay": 5.0,
    "timeout": 300
  }
}
```

### 2. Token Budget 控制

```python
from cyberclaw.agent.team.budget import TokenBudgetTracker

tracker = TokenBudgetTracker(
    daily_limit=100000,      # 每日 10 万 token
    per_task_limit=10000     # 每任务 1 万 token
)

# 检查预算
allowed, msg = tracker.check_budget("coding", 5000)

# 记录用量
tracker.record_usage("coding", "task-001", 3000, 1000)
```

### 3. Rate Limiting

```python
# 检查速率限制
decision = policy_engine.check_rate_limit(
    agent_id="coding",
    max_spawns_per_minute=10,
    max_concurrent=8
)

if not decision.is_allowed:
    print(f"速率限制：{decision.message}")
```

### 4. 等待子任务完成

```python
from cyberclaw.agent.announce_chain import AnnounceChainManager

manager = AnnounceChainManager()

# 等待所有子任务完成
result = await manager.wait_for_children(
    parent_session_key="orchestrator:session1",
    timeout=600,
    poll_interval=1.0
)

if result:
    print(f"完成 {len(result.children)} 个子任务")
```

---

## 📊 监控与调试

### 查看详细日志

```bash
cyberclaw gateway --multi --verbose
```

### 查看路由信息

```python
from cyberclaw.gateway.manager import MultiAgentGateway

gw = MultiAgentGateway(config, bus)
info = gw.get_router_info()
print(info)
# {
#   "default_agent": "orchestrator",
#   "rules": [
#     {"agent_id": "coding", "priority": 50, "keywords": [...]},
#     {"agent_id": "research", "priority": 50, "keywords": [...]}
#   ]
# }
```

### 健康检查

```python
status = await gw.health_check()
print(status)
# {"orchestrator": "healthy", "coding": "healthy", ...}
```

### 获取 Agent 实例

```python
agent = gw.get_agent("coding")
if agent:
    response = await agent.process_message(msg)
```

---

## ✅ 最佳实践

### 1. 任务描述清晰

```
❌ "帮我做一个电商平台"
✅ "帮我设计电商平台的数据库架构，然后实现用户登录模块"
```

### 2. 合理设置优先级

```json
{
  "bindings": [
    {"agent_id": "vip", "chat_ids": ["vip_123"], "priority": 100},
    {"agent_id": "urgent", "keywords": ["紧急"], "priority": 80},
    {"agent_id": "coding", "keywords": ["代码"], "priority": 50},
    {"agent_id": "main", "channels": [], "priority": 0}
  ]
}
```

### 3. 选择合适的 Team

```
简单编码任务 → coding
代码审查 → code-review-team
完整项目 → fullstack-team
研究调研 → research-team
```

### 4. 设置合理的超时

```
简单任务: timeout=60
中等任务: timeout=300
复杂任务: timeout=900
```

### 5. 利用 Orchestrator

对于多步骤任务，让 orchestrator 自动分解：

```
用户：帮我完成一个完整的数据分析项目

Orchestrator 自动分解:
1. 收集数据 → spawn research
2. 数据清洗 → spawn coding
3. 分析建模 → spawn coding
4. 可视化 → spawn coding
5. 验证结果 → spawn debugger
```

---

## 🛡️ 容错机制

### 错误类型与恢复策略

| 错误类型 | 是否可重试 | 恢复策略 |
|---------|-----------|---------|
| `NETWORK` | ✅ | 重试 3 次，5s 间隔 |
| `TIMEOUT` | ✅ | 重试 3 次，指数退避 |
| `RATE_LIMIT` | ✅ | 重试 5 次，30s 间隔 |
| `API_LIMIT` | ❌ | 通知父 agent |
| `BUDGET_EXCEEDED` | ❌ | 中止并通知 |
| `CANCELLED` | ❌ | 中止 |
| `LOGIC` | ❌ | 通知父 agent |

### 错误通知

子 agent 失败时自动通知父 agent:

```
❌ Subagent [research-1] failed: Connection timeout
  错误类型：timeout (可重试)
  已重试 3 次，最终失败
```

### Fallback 机制

如果指定的 agent 不可用，自动 fallback 到 default agent（orchestrator）

---

## 🔍 故障排查

### 问题 1: 路由不生效

**检查项**:
```bash
# 1. 确认使用 --multi 参数
cyberclaw gateway --multi

# 2. 查看 binding 配置
cat ~/.cyberclaw/config.json | jq '.agents.bindings'

# 3. 查看日志
cyberclaw gateway --multi --verbose
```

### 问题 2: Team 无法使用

**检查项**:
```bash
# 1. 验证 team 配置
cyberclaw teams validate dev-team

# 2. 检查 members 是否都存在
cyberclaw teams info dev-team

# 3. 确认 agent_to_agent 已启用
cat ~/.cyberclaw/config.json | jq '.tools.agent_to_agent.enabled'
```

### 问题 3: Spawn 失败

**检查项**:
```bash
# 1. 检查 spawn depth 限制
cat ~/.cyberclaw/config.json | jq '.agents.defaults.subagents.max_spawn_depth'

# 2. 检查并发限制
cat ~/.cyberclaw/config.json | jq '.agents.defaults.subagents.max_concurrent'

# 3. 查看错误日志
tail -f ~/.cyberclaw/logs/agent.log
```

### 问题 4: Token 预算超限

**解决方法**:
```python
# 1. 查看当前用量
report = tracker.get_usage_report("coding")
print(report)

# 2. 增加预算限制
tracker = TokenBudgetTracker(daily_limit=200000)

# 3. 重置用量
tracker.reset_daily()
```

---

## 📚 参考文档

| 文档 | 说明 |
|------|------|
| `AGENT_TEAM_IMPLEMENTATION_PLAN.md` | 完整实施计划 |
| `cyberclaw/gateway/router.py` | 路由引擎源码 |
| `cyberclaw/gateway/manager.py` | Gateway 管理器源码 |
| `cyberclaw/agent/tools/broadcast.py` | Broadcast 工具源码 |
| `tests/test_gateway_router.py` | 路由测试用例 |
| `tests/test_multi_agent_gateway.py` | Gateway 测试用例 |

---

## 🎓 示例工作流

### 完整项目开发流程

```
1. 用户：帮我开发一个博客系统

2. orchestrator 接收任务，自动分解:
   ├─ research: 调研博客系统最佳实践
   ├─ coding: 设计数据库 schema
   ├─ coding: 实现用户认证
   ├─ coding: 实现文章 CRUD
   ├─ coding: 实现前端界面
   ├─ reviewer: 审查代码质量
   └─ debugger: 测试和修复问题

3. 聚合所有结果，生成:
   - 技术选型报告
   - 数据库设计文档
   - 完整源代码
   - 测试报告
   - 部署指南
```

### 代码审查流程

```
1. 用户：请审查这个 PR

2. code-review-team 执行:
   ├─ reviewer: 代码风格和规范审查
   ├─ debugger: 潜在 bug 和安全问题检查
   └─ coding: 性能优化建议

3. 输出综合审查报告
```

---

## 📝 更新日志

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-04 | 初始版本，包含完整的 Agent Team 功能 |

---

**最后更新**: 2026-03-04
