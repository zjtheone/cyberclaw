# Gateway Status 功能使用说明

## ✅ 已完成的功能

### 1. MultiAgentGateway.get_status() 方法

**位置**: `cyberclaw/gateway/manager.py`

**功能**: 获取 Gateway 和所有 agent 的状态

**返回数据**:
```python
{
    "status": "running",              # 运行状态
    "uptime": 3600.5,                 # 运行时间（秒）
    "uptime_human": "1.0 小时",        # 人类可读的运行时间
    "agent_count": 6,                 # Agent 数量
    "agents": ["orchestrator", ...],  # Agent ID 列表
    "default_agent": "orchestrator",  # 默认 Agent
    "routing_rules": 6,               # 路由规则数量
    "teams": 4,                       # Team 数量
    "team_names": ["dev-team", ...]   # Team 名称列表
}
```

**使用示例**:
```python
from cyberclaw.config.loader import load_config
from cyberclaw.bus.queue import MessageBus
from cyberclaw.gateway.manager import MultiAgentGateway
import asyncio

async def test():
    config = load_config()
    bus = MessageBus()
    gw = MultiAgentGateway(config, bus)
    await gw.start()
    
    # 获取状态
    status = gw.get_status()
    print(status)
    
    await gw.stop()

asyncio.run(test())
```

---

### 2. CLI status 命令增强

**命令**: `cyberclaw status`

**功能**: 显示配置和 Gateway 状态

**输出示例**:
```
🐈 cyberclaw Status

Config: /Users/cengjian/.cyberclaw/config.json ✓
Workspace: /Users/cengjian/.cyberclaw/workspace ✓
Model: qwen3.5-plus
DashScope: ✓

Multi-Agent Gateway:
  Status: ● Running
  URL: http://127.0.0.1:18790
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
    • fullstack-team       [sequential] (leader: orchestrator)
      Members: research, coding, reviewer, debugger
    • code-review-team     [parallel] (leader: reviewer)
      Members: reviewer, debugger, coding
```

---

### 3. Python 状态检查脚本

**文件**: `check_gateway_status.py`

**运行**:
```bash
python check_gateway_status.py
```

**输出示例**:
```
======================================================================
Multi-Agent Gateway 状态
======================================================================

状态：🟢 运行中
URL: http://127.0.0.1:18790

默认 Agent: orchestrator
Agent 数量：6
路由规则：6 条
Teams: 4 个

配置的 Agents:
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

路由规则:
  • coding          (priority: 50) - 代码，编程，实现...
  • research        (priority: 50) - 搜索，查找，研究...
  • reviewer        (priority: 40) - 审查，review，检查...
  • debugger        (priority: 45) - 调试，debug，修复...
  • orchestrator    (priority: 60) - 复杂，完整，全栈...
  • main            (priority:  0) - 

======================================================================
💡 提示：查看 Gateway 终端窗口查看实时活动日志
======================================================================
```

---

## 📋 查看 Agent 工作状态的方法

### 方法 1: Gateway 终端日志（推荐）⭐

**最直接的方式**: 保持 Gateway 运行的终端窗口可见

```bash
cyberclaw gateway --multi
```

**实时日志输出**:
```
2026-03-04 18:10:37 | INFO | Agent orchestrator ready
2026-03-04 18:10:37 | INFO | Agent main ready
2026-03-04 18:10:37 | INFO | Agent coding ready
...
2026-03-04 18:15:00 | DEBUG | Routing message from cli:user123 to agent coding
2026-03-04 18:15:05 | INFO  | Agent coding completed task in 5.2s
```

### 方法 2: CLI status 命令

```bash
cyberclaw status
```

显示：
- ✅ Gateway 运行状态
- ✅ 配置的 Agents 列表
- ✅ Teams 配置
- ✅ 路由规则数量

### 方法 3: Python 脚本

```bash
python check_gateway_status.py
```

显示更详细的信息，包括所有路由规则。

### 方法 4: tmux 分屏监控

```bash
# 创建 tmux 会话
tmux new -s cyberclaw

# 左侧：Gateway
cyberclaw gateway --multi

# 分屏（Ctrl+b, %）

# 右侧：发送任务
cyberclaw agent
```

**优点**: 实时看到 Gateway 日志和任务发送

### 方法 5: 后台运行 + 日志重定向

```bash
# 创建日志目录
mkdir -p ~/.cyberclaw/logs

# 后台启动并重定向日志
nohup cyberclaw gateway --multi > ~/.cyberclaw/logs/gateway.log 2>&1 &

# 保存 PID
echo $! > ~/.cyberclaw/logs/gateway.pid

# 实时监控日志
tail -f ~/.cyberclaw/logs/gateway.log

# 停止 Gateway
kill $(cat ~/.cyberclaw/logs/gateway.pid)
```

---

## 🔍 当前状态指示

| 状态 | 显示 | 说明 |
|------|------|------|
| 运行中 | 🟢 Running / ● Running | Gateway 正常运行 |
| 未运行 | 🔴 Offline / ○ Offline | Gateway 未启动 |
| Agent Ready | `Agent xxx ready` | Agent 已就绪 |
| Processing | `Routing message to agent xxx` | 正在处理任务 |
| Completed | `Agent xxx completed task` | 任务完成 |

---

## 💡 最佳实践

### 开发/调试环境

```bash
# 使用 tmux 分屏
tmux new -s cyberclaw
# 左侧：cyberclaw gateway --multi
# 右侧：cyberclaw agent (发送任务)

# 优点：实时看到所有日志
```

### 生产/后台运行

```bash
# 后台运行 + 日志文件
mkdir -p ~/.cyberclaw/logs
nohup cyberclaw gateway --multi > ~/.cyberclaw/logs/gateway.log 2>&1 &

# 监控日志
tail -f ~/.cyberclaw/logs/gateway.log

# 定期检查状态
cyberclaw status
```

### 快速检查

```bash
# 添加到 ~/.zshrc 或 ~/.bashrc
alias gw-status='python check_gateway_status.py'

# 使用
gw-status
```

---

## ⚠️ 注意事项

1. **Gateway 不监听 HTTP 端口**
   - Gateway 通过 MessageBus 与 CLI 通信
   - 不是 HTTP server，不会监听 18790 端口
   - 状态检查通过进程和配置实现

2. **实时日志在终端窗口**
   - 最准确的 Agent 活动信息在 Gateway 运行的终端
   - 保持该窗口可见以监控实时状态

3. **后台运行需要日志重定向**
   - 后台运行时使用 `nohup` 或 `script` 记录日志
   - 使用 `tail -f` 实时查看

---

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `cyberclaw/gateway/manager.py` | `get_status()` 方法实现 |
| `cyberclaw/cli/commands.py` | CLI `status` 命令增强 |
| `check_gateway_status.py` | Python 状态检查脚本 |
| `AGENT_TEAM_CONFIG.md` | Agent Team 配置文档 |
| `GATEWAY_FIX_REPORT.md` | Gateway 修复报告 |

---

**最后更新**: 2026-03-04
