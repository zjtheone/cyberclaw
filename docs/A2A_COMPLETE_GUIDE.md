# cyberclaw Agent-to-Agent 协议完整指南

## 📖 目录

1. [概述](#概述)
2. [核心概念](#核心概念)
3. [快速开始](#快速开始)
4. [配置指南](#配置指南)
5. [CLI 命令参考](#cli 命令参考)
6. [最佳实践](#最佳实践)
7. [故障排除](#故障排除)

---

## 概述

### 什么是 Agent-to-Agent 协议？

Agent-to-Agent (A2A) 协议是 cyberclaw 实现的多智能体协作系统，允许：

- ✅ **跨 Agent 协作** - 不同 agent 之间可以互相通信和任务分配
- ✅ **嵌套 Subagent** - 支持 orchestrator pattern (主→协调者→执行者)
- ✅ **层级结果聚合** - 自动聚合子任务结果到父任务
- ✅ **PingPong 对话** - agent 间自动多轮对话
- ✅ **策略控制** - 白名单/黑名单/深度限制等安全机制

### 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    cyberclaw A2A System                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Phase 1   │  │   Phase 2    │  │   Phase 3    │   │
│  │  基础架构   │  │  A2A 策略    │  │ Announce     │   │
│  │             │  │              │  │    Chain     │   │
│  └─────────────┘  └──────────────┘  └──────────────┘   │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐                      │
│  │   Phase 4   │  │   Phase 5    │                      │
│  │   CLI 命令  │  │  测试与文档  │                      │
│  └─────────────┘  └──────────────┘                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| Session Keys | `session/keys.py` | 会话键格式和解析 |
| Policy Engine | `agent/policy_engine.py` | A2A 策略检查 |
| Announce Chain | `agent/announce_chain.py` | 层级结果聚合 |
| PingPong Dialog | `agent/pingpong_dialog.py` | 多轮对话管理 |
| Subagent Manager | `agent/subagent.py` | Subagent 执行 |
| CLI Commands | `cli/subagents.py`, `cli/sessions.py` | 命令行管理 |

---

## 核心概念

### 1. 会话键格式

**旧格式**: `channel:chat_id` (e.g., `cli:direct`)

**新格式**: `agent:<agent_id>:<session_type>:<session_id>`

```
agent:main:main:1              # Main agent session
agent:main:subagent:abc123     # Subagent session
agent:coding:main:1            # Different agent
```

**代码示例**:
```python
from cyberclaw.session.keys import SessionKey

# 创建
key = SessionKey.create_main("main", "default")
key = SessionKey.create_subagent("coding", "abc123")

# 解析
key = SessionKey.parse("agent:main:subagent:abc123")
print(key.agent_id)      # "main"
print(key.session_type)  # "subagent"
```

### 2. Spawn 深度

```
Depth 0: Main Agent (可以 spawn)
  ↓
Depth 1: Subagent/Orchestrator (如果 max_depth>=2 可以 spawn)
  ↓
Depth 2: Worker (不能 spawn - 达到最大深度)
```

**配置**:
```json
{
  "agents": {
    "defaults": {
      "subagents": {
        "max_spawn_depth": 2  // 允许 3 层
      }
    }
  }
}
```

### 3. Announce Chain

```
Worker 完成 → announce (带 parent_session_key)
  ↓
AnnounceChainManager 注册
  ↓
Orchestrator 获取聚合结果
  ↓
合成并 announce 给 Main
  ↓
Main 交付用户
```

### 4. A2A 策略

```json
{
  "tools": {
    "agent_to_agent": {
      "enabled": true,       // 启用 A2A
      "allow": ["*"],        // 白名单 (*=所有)
      "deny": ["bad"],       // 黑名单
      "max_ping_pong_turns": 5  // 最大对话轮次
    }
  }
}
```

---

## 快速开始

### 1. 基本配置

```json
{
  "agents": {
    "list": [
      {
        "id": "main",
        "name": "主助手",
        "workspace": "~/.cyberclaw/workspace-main"
      },
      {
        "id": "coding",
        "name": "编程助手",
        "workspace": "~/.cyberclaw/workspace-coding"
      }
    ],
    "defaults": {
      "subagents": {
        "max_spawn_depth": 2,
        "max_children_per_agent": 5
      }
    }
  },
  "tools": {
    "agent_to_agent": {
      "enabled": true,
      "allow": ["main", "coding"]
    }
  }
}
```

### 2. 启动 A2A 工作流

```bash
# 1. 启动 orchestrator subagent
cyberclaw subagents spawn main "Coordinate development task"

# 2. 查看状态
cyberclaw subagents list

# 3. 聚焦到会话
cyberclaw sessions focus subagent:#1

# 4. 发送指导
cyberclaw subagents steer #1 "Focus on quality"

# 5. 查看日志
cyberclaw subagents log #1 --tools

# 6. 完成后取消聚焦
cyberclaw sessions unfocus
```

### 3. Orchestrator Pattern

```
用户：开发一个用户登录功能
  ↓
Main Agent
  ↓ spawn
Orchestrator Subagent
  ├─ spawn → Worker: Database schema
  ├─ spawn → Worker: API implementation
  ├─ spawn → Worker: Unit tests
  └─ spawn → Worker: Documentation
  ↓ 聚合所有结果
  ↓ announce
Main Agent → 交付完整方案给用户
```

---

## 配置指南

### 完整配置示例

```json5
{
  // Agent 配置
  "agents": {
    "defaults": {
      "model": "deepseek-reasoner",
      "temperature": 0.7,
      "subagents": {
        "max_spawn_depth": 2,        // 嵌套深度
        "max_children_per_agent": 5, // 每个 agent 最多子任务
        "max_concurrent": 8,         // 全局并发
        "run_timeout_seconds": 900,  // 默认超时
        "archive_after_minutes": 60  // 自动归档时间
      }
    },
    "list": [
      {
        "id": "main",
        "name": "主助手",
        "workspace": "~/.cyberclaw/workspace-main"
      },
      {
        "id": "coding",
        "name": "编程助手",
        "workspace": "~/.cyberclaw/workspace-coding",
        "model": "claude-opus",
        "subagents": {
          "max_spawn_depth": 2
        }
      }
    ]
  },
  
  // A2A 策略
  "tools": {
    "agent_to_agent": {
      "enabled": true,
      "allow": ["main", "coding", "research"],
      "deny": [],
      "max_ping_pong_turns": 5
    },
    "sessions": {
      "visibility": "tree"  // self|tree|agent|all
    }
  },
  
  // 会话管理
  "session": {
    "threadBindings": {
      "enabled": true,
      "idleHours": 24,
      "maxAgeHours": 0
    }
  }
}
```

### 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `max_spawn_depth` | 最大 spawn 深度 | 1 |
| `max_children_per_agent` | 每个 agent 最大子任务数 | 5 |
| `max_concurrent` | 全局并发限制 | 8 |
| `run_timeout_seconds` | 运行超时 (秒) | 0 (无限制) |
| `archive_after_minutes` | 自动归档时间 (分钟) | 60 |
| `visibility` | 会话可见性 | "tree" |

---

## CLI 命令参考

### /subagents 命令组

| 命令 | 用法 | 说明 |
|------|------|------|
| `list` | `cyberclaw subagents list [--all]` | 列出 subagent |
| `kill` | `cyberclaw subagents kill <id\|all> [-f]` | 停止 subagent |
| `log` | `cyberclaw subagents log <id> [-l N] [-t]` | 查看日志 |
| `info` | `cyberclaw subagents info <id>` | 详细信息 |
| `send` | `cyberclaw subagents send <id> <msg>` | 发送消息 |
| `steer` | `cyberclaw subagents steer <id> <msg> [-p]` | 发送指导 |
| `spawn` | `cyberclaw subagents spawn <agent> <task>` | 创建 subagent |
| `tree` | `cyberclaw subagents tree [-r]` | 显示 spawn 树 |

### /sessions 命令组

| 命令 | 用法 | 说明 |
|------|------|------|
| `focus` | `cyberclaw sessions focus <target>` | 聚焦会话 |
| `unfocus` | `cyberclaw sessions unfocus` | 取消聚焦 |
| `idle` | `cyberclaw sessions idle [1h\|off]` | 空闲超时 |
| `max-age` | `cyberclaw sessions max-age [24h\|off]` | 最大年龄 |
| `list` | `cyberclaw sessions list [-a] [--active]` | 列出会话 |
| `info` | `cyberclaw sessions info <key>` | 会话信息 |
| `clear` | `cyberclaw sessions clear <key> [-y]` | 清空会话 |
| `archive` | `cyberclaw sessions archive <key>` | 归档会话 |
| `bindings` | `cyberclaw sessions bindings` | 查看绑定 |

---

## 最佳实践

### 1. 团队结构设计

```
推荐：3 层架构
├── Depth 0: Main (决策者)
│   └── Depth 1: Orchestrator (协调者)
│       └── Depth 2: Workers (执行者)

避免：过深的层级
├── Depth 0
│   └── Depth 1
│       └── Depth 2
│           └── Depth 3  ← 太深，管理复杂
│               └── Depth 4  ← 避免
```

### 2. 任务分配策略

```python
# ✅ 好的做法：明确的任务边界
subagents spawn coding "Implement REST API"
subagents spawn research "Market analysis"
subagents spawn docs "Write documentation"

# ❌ 避免：模糊的任务描述
subagents spawn coding "Do something"
```

### 3. 监控和管理

```bash
# 定期检查状态
cyberclaw subagents list

# 查看详细日志
cyberclaw subagents log <id> --tools

# 必要时调整方向
cyberclaw subagents steer <id> "Focus on error handling"

# 及时清理完成的
cyberclaw subagents kill <completed_id>
```

### 4. 错误处理

```bash
# 如果 subagent 卡住
cyberclaw subagents kill <id> --force

# 如果需要重新开始
cyberclaw subagents spawn <agent> <task> --label "Retry: original task"

# 查看所有活跃的
cyberclaw subagents list --active
```

### 5. 性能优化

```json5
{
  "agents": {
    "defaults": {
      "subagents": {
        "max_concurrent": 8,     // 根据资源调整
        "run_timeout_seconds": 900,  // 避免无限运行
        "archive_after_minutes": 60  // 及时清理
      }
    }
  }
}
```

---

## 故障排除

### 常见问题

#### 1. "Maximum spawn depth reached"

**原因**: 已达到配置的最大 spawn 深度

**解决**:
```json
{
  "agents": {
    "defaults": {
      "subagents": {
        "max_spawn_depth": 2  // 增加深度限制
      }
    }
  }
}
```

#### 2. "Agent-to-agent spawning is disabled"

**原因**: A2A 未启用或目标 agent 不在白名单

**解决**:
```json
{
  "tools": {
    "agent_to_agent": {
      "enabled": true,
      "allow": ["main", "coding"]  // 添加目标 agent
    }
  }
}
```

#### 3. Subagent 无响应

**诊断**:
```bash
# 查看状态
cyberclaw subagents list

# 查看日志
cyberclaw subagents log <id> --tools

# 检查是否超时
cyberclaw subagents info <id>
```

**解决**:
```bash
# 停止并重新开始
cyberclaw subagents kill <id> --force
cyberclaw subagents spawn <agent> <task> --label "Retry"
```

#### 4. 会话绑定问题

**症状**: 消息没有路由到正确的会话

**解决**:
```bash
# 查看当前绑定
cyberclaw sessions bindings

# 重新聚焦
cyberclaw sessions focus <correct_session>

# 清除旧绑定
cyberclaw sessions unfocus
```

### 调试技巧

```bash
# 1. 启用详细日志
export CYBERCLAW_LOG_LEVEL=debug

# 2. 查看 spawn 树
cyberclaw subagents tree

# 3. 检查会话状态
cyberclaw sessions list --active

# 4. 监控资源使用
cyberclaw subagents info <id>  # 查看 token 使用
```

---

## 附录

### A. 测试覆盖

```
Total tests: 88
✅ Session keys: 16
✅ Policy engine: 19
✅ Announce chain: 14
✅ PingPong dialog: 12
✅ CLI commands: 18
✅ Integration: 9
```

### B. 文件清单

```
cyberclaw/
├── session/
│   ├── keys.py              # 会话键格式
│   └── manager.py           # 会话管理
├── agent/
│   ├── policy_engine.py     # A2A 策略
│   ├── announce_chain.py    # 结果聚合
│   ├── pingpong_dialog.py   # 对话管理
│   ├── subagent.py          # Subagent 执行
│   └── tools/
│       └── spawn.py         # Spawn 工具
└── cli/
    ├── subagents.py         # Subagent CLI
    └── sessions.py          # Sessions CLI
```

### C. 相关文档

- `A2A_IMPLEMENTATION_PLAN.md` - 实施规划
- `PHASE1-4_COMPLETION_REPORT.md` - 各阶段报告
- `A2A_QUICK_START.md` - 快速开始

---

**文档版本**: 1.0  
**最后更新**: 2026-03-03  
**维护者**: cyberclaw Team
