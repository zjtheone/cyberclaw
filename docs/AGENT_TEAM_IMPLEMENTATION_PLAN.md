# Agent Team 功能实施计划

> 基于 AGENT_TEAM_ROADMAP.md 的分析，本文档是可直接执行的详细实施方案。
> 创建时间: 2026-03-04 | 分支: feat_change_to_coder_v2

---

## 当前状态总结

### 已完成 ✅
| 模块 | 文件 | 状态 |
|------|------|------|
| A2A 策略引擎 | `cyberclaw/agent/policy_engine.py` | 完整 |
| Subagent 管理器 | `cyberclaw/agent/subagent.py` | 完整 |
| Spawn 工具 | `cyberclaw/agent/tools/spawn.py` | 完整 |
| Announce Chain | `cyberclaw/agent/announce_chain.py` | 完整 |
| PingPong 对话 | `cyberclaw/agent/a2a_flow.py` | 完整 |
| Session Key 系统 | `cyberclaw/session/keys.py` | 完整 |
| CLI (subagents/sessions) | `cyberclaw/cli/subagents.py`, `sessions.py` | 完整 |
| 测试（88 用例） | `tests/test_a2a_*.py` | 100% 通过 |
| 配置 Schema | `cyberclaw/config/schema.py` | 基础完成 |

### 未完成 🔴
| 功能 | 优先级 | 预估工时 |
|------|--------|----------|
| Gateway 多 Agent 路由 | P0 | 3-4 天 |
| Orchestrator 自动化 | P1 | 2-3 天 |
| Broadcast/Team 功能 | P1 | 2 天 |
| 高级策略控制 | P2 | 2-3 天 |
| CLI 增强 | P2 | 1-2 天 |
| Web Dashboard | P3 | 4-5 天 |

---

## Phase 1: Gateway 多 Agent 路由 [P0]

**目标**: gateway 命令启动时，能根据配置启动多个 AgentLoop 实例，并将消息路由到正确的 agent。

**当前问题**: `cyberclaw/cli/commands.py:376` 的 `gateway()` 函数只创建了一个 `AgentLoop` 实例，`config.agents.agent_list` 虽然在 schema 中定义但从未被使用。

### 1.1 扩展配置 Schema

**文件**: `cyberclaw/config/schema.py`

新增以下模型：

```python
class AgentBinding(BaseModel):
    """消息路由规则：将特定 channel/chat 绑定到特定 agent。"""
    agent_id: str                          # 目标 agent ID
    channels: list[str] = Field(default_factory=list)  # 匹配的 channel 名称列表，如 ["telegram", "slack"]
    chat_ids: list[str] = Field(default_factory=list)   # 匹配的 chat_id 列表
    chat_pattern: str | None = None        # chat_id 正则匹配
    keywords: list[str] = Field(default_factory=list)   # 消息内容关键词匹配
    priority: int = 0                      # 优先级，越大越优先

class TeamConfig(BaseModel):
    """Agent Team 分组定义。"""
    name: str                              # team 名称
    members: list[str]                     # agent IDs
    leader: str | None = None              # leader agent（可选）
    strategy: str = "parallel"             # parallel | sequential | leader_delegate
```

修改 `AgentsConfig`:

```python
class AgentsConfig(BaseModel):
    defaults: AgentConfig = Field(default_factory=lambda: AgentConfig(id="default"))
    agent_list: list[AgentConfig] = Field(default_factory=list)
    bindings: list[AgentBinding] = Field(default_factory=list)    # 新增
    teams: list[TeamConfig] = Field(default_factory=list)          # 新增
    default_agent: str = "default"                                  # 新增
```

### 1.2 创建消息路由器

**新文件**: `cyberclaw/gateway/__init__.py`（空）
**新文件**: `cyberclaw/gateway/router.py`

```python
class MessageRouter:
    """根据 binding 规则将 InboundMessage 路由到目标 agent。"""

    def __init__(self, bindings: list[AgentBinding], default_agent: str):
        # 按 priority 降序排列 bindings
        self.bindings = sorted(bindings, key=lambda b: b.priority, reverse=True)
        self.default_agent = default_agent

    def route(self, msg: InboundMessage) -> str:
        """返回目标 agent_id。按 priority 顺序匹配第一个命中的规则。"""
        for binding in self.bindings:
            if self._matches(binding, msg):
                return binding.agent_id
        return self.default_agent

    def _matches(self, binding: AgentBinding, msg: InboundMessage) -> bool:
        # 1. channel 匹配
        # 2. chat_id 精确/正则匹配
        # 3. keywords 内容匹配
        # 全部条件为 AND 关系（空列表视为"不限制"）
        ...
```

### 1.3 创建多 Agent Gateway 管理器

**新文件**: `cyberclaw/gateway/manager.py`

```python
class MultiAgentGateway:
    """管理多个 AgentLoop 实例的生命周期和消息路由。"""

    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.agents: dict[str, AgentLoop] = {}     # agent_id -> AgentLoop
        self.router = MessageRouter(config.agents.bindings, config.agents.default_agent)
        self._health_tasks: dict[str, asyncio.Task] = {}

    async def start(self):
        """启动所有配置的 agent 实例。"""
        # 1. 始终创建 default agent
        # 2. 为 agent_list 中每个 agent 创建实例
        # 3. 订阅 bus 消息并路由
        ...

    async def stop(self):
        """优雅关闭所有 agent。"""
        ...

    async def _handle_message(self, msg: InboundMessage):
        """路由消息到目标 agent。"""
        agent_id = self.router.route(msg)
        agent = self.agents.get(agent_id) or self.agents[self.config.agents.default_agent]
        await agent.process_message(msg)

    def _create_agent_loop(self, agent_config: AgentConfig) -> AgentLoop:
        """根据 AgentConfig 创建 AgentLoop 实例。"""
        # 从 agent_config 提取参数，覆盖 defaults
        ...

    async def health_check(self) -> dict[str, str]:
        """返回各 agent 健康状态。"""
        ...
```

### 1.4 更新 CLI gateway 命令

**文件**: `cyberclaw/cli/commands.py`（修改 `gateway()` 函数, ~L345）

```python
@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p"),
    multi: bool = typer.Option(False, "--multi", "-m", help="Enable multi-agent routing"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    if multi and config.agents.agent_list:
        from cyberclaw.gateway.manager import MultiAgentGateway
        gw = MultiAgentGateway(config, bus)
        # ... 启动 multi-agent gateway
    else:
        # 现有单 agent 逻辑不变
        ...
```

### 1.5 测试

**新文件**: `tests/test_gateway_router.py`

测试用例：
- [ ] `test_route_by_channel` — 按 channel 路由
- [ ] `test_route_by_chat_id` — 按 chat_id 路由
- [ ] `test_route_by_pattern` — 按正则路由
- [ ] `test_route_by_keyword` — 按关键词路由
- [ ] `test_route_priority` — 优先级测试
- [ ] `test_route_fallback_default` — 无匹配时 fallback

**新文件**: `tests/test_multi_agent_gateway.py`

测试用例：
- [ ] `test_start_multiple_agents` — 启动多个 agent
- [ ] `test_message_routed_to_correct_agent` — 消息路由到正确 agent
- [ ] `test_health_check` — 健康检查
- [ ] `test_graceful_shutdown` — 优雅关闭

### 1.6 配置示例

```json
{
  "agents": {
    "defaults": { "id": "default", "model": "anthropic/claude-sonnet-4-5" },
    "default_agent": "coder",
    "agent_list": [
      { "id": "coder", "model": "anthropic/claude-opus-4-5", "workspace": "~/.cyberclaw/workspace" },
      { "id": "researcher", "model": "anthropic/claude-sonnet-4-5" },
      { "id": "reviewer", "model": "deepseek/deepseek-chat" }
    ],
    "bindings": [
      { "agent_id": "coder", "channels": ["telegram"], "chat_ids": ["123456"], "priority": 10 },
      { "agent_id": "researcher", "keywords": ["搜索", "查找", "research"], "priority": 5 }
    ]
  }
}
```

### 1.7 完成标准
- [ ] `cyberclaw gateway --multi` 可以启动多个 agent 实例
- [ ] 消息根据 bindings 规则正确路由
- [ ] 未匹配的消息 fallback 到 default_agent
- [ ] 所有新增测试通过
- [ ] 不影响现有的 `cyberclaw gateway`（无 `--multi` 时行为不变）

---

## Phase 2: Orchestrator 自动化 [P1]

**目标**: 提供 Orchestrator 角色模板和自动化工作流，让一个 agent 能自动分解任务、spawn workers、聚合结果。

**前置依赖**: Phase 1（可部分并行，但完整测试需要 Phase 1）

### 2.1 创建 Orchestrator 角色模板

**新文件**: `cyberclaw/agent/team/__init__.py`（空）
**新文件**: `cyberclaw/agent/team/orchestrator.py`

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
你是一个任务协调者 (Orchestrator)。你的职责是：
1. 分析用户需求，将复杂任务分解为可并行执行的子任务
2. 使用 spawn 工具为每个子任务创建专门的 worker
3. 监控 worker 完成情况
4. 聚合所有 worker 的结果，生成综合报告
5. 如果某个 worker 失败，决定是否重试或调整策略

规则：
- 尽可能让子任务并行执行
- 每个子任务的 label 应该清晰描述任务内容
- 等待所有 worker 完成后再做最终总结
"""

class OrchestratorTemplate:
    """Orchestrator 角色配置模板。"""

    @staticmethod
    def create_config(base_config: AgentConfig) -> AgentConfig:
        """基于基础配置创建 orchestrator agent 配置。"""
        config = base_config.model_copy()
        config.subagents.max_spawn_depth = 2  # 允许嵌套
        config.subagents.max_children_per_agent = 10
        return config

    @staticmethod
    def get_system_prompt() -> str:
        return ORCHESTRATOR_SYSTEM_PROMPT
```

### 2.2 增强 Spawn 工具（批量 spawn）

**文件**: `cyberclaw/agent/tools/spawn.py`（修改）

新增 `spawn_batch` 方法或在现有 `execute` 中支持批量参数：

```python
# 在 SpawnTool 中新增
async def execute(self, task: str, label: str = None,
                  batch: list[dict] = None,  # 新增：批量 spawn
                  wait: bool = False,        # 新增：同步等待结果
                  timeout: int = 300):       # 新增：等待超时
    if batch:
        results = []
        for item in batch:
            r = await self._spawn_single(item["task"], item.get("label"))
            results.append(r)
        if wait:
            return await self._wait_all(results, timeout)
        return results
    else:
        return await self._spawn_single(task, label)
```

### 2.3 自动结果聚合增强

**文件**: `cyberclaw/agent/announce_chain.py`（修改）

新增等待所有子任务完成的便捷方法：

```python
class AnnounceChainManager:
    # 新增
    async def wait_for_children(
        self, parent_session_key: str, timeout: float = 300
    ) -> AggregatedResult:
        """等待指定 parent session 的所有子任务完成。"""
        ...
```

### 2.4 Skill 文件（可选）

**新文件**: `cyberclaw/skills/orchestrator.md`

```yaml
---
name: orchestrator
trigger: auto
description: 自动任务分解和并行执行
---
当需要处理复杂多步骤任务时，自动使用 orchestrator 模式...
```

### 2.5 测试

**新文件**: `tests/test_orchestrator.py`

- [ ] `test_orchestrator_template_config` — 配置模板正确
- [ ] `test_spawn_batch` — 批量 spawn 执行
- [ ] `test_wait_for_children` — 等待子任务完成
- [ ] `test_orchestrator_prompt` — system prompt 正确注入

### 2.6 完成标准
- [ ] Orchestrator 模板可被应用到任意 agent
- [ ] 批量 spawn 功能正常
- [ ] wait_for_children 超时机制正常
- [ ] 编写了至少一个完整示例工作流

---

## Phase 3: Broadcast / Team 功能 [P1]

**目标**: 支持将消息广播到一组 agent，并聚合结果。

**前置依赖**: Phase 1 + Phase 2（部分）

### 3.1 扩展配置（已在 Phase 1 的 TeamConfig 中完成）

### 3.2 创建 Broadcast 工具

**新文件**: `cyberclaw/agent/tools/broadcast.py`

```python
class BroadcastTool(Tool):
    """将消息广播到 team 中的所有 agent。"""

    name = "broadcast"
    description = "Broadcast a message to a team of agents and collect results."

    parameters = {
        "team": {"type": "string", "description": "Team name"},
        "message": {"type": "string", "description": "Message to broadcast"},
        "strategy": {"type": "string", "enum": ["parallel", "sequential"], "default": "parallel"},
        "timeout": {"type": "integer", "default": 300},
    }

    async def execute(self, team: str, message: str,
                      strategy: str = "parallel", timeout: int = 300) -> str:
        # 1. 从 config 查找 team 定义
        # 2. 为每个 member spawn subagent
        # 3. 根据 strategy 等待并聚合结果
        ...
```

### 3.3 注册 Broadcast 工具

**文件**: `cyberclaw/agent/tools/registry.py`（修改）

在 `ToolRegistry.__init__` 中注册 `BroadcastTool`。

### 3.4 Team 查询工具

**新文件**: `cyberclaw/agent/team/manager.py`

```python
class TeamManager:
    """Team 管理：查询、验证、操作 team。"""

    def __init__(self, config: AgentsConfig):
        self.config = config

    def get_team(self, name: str) -> TeamConfig | None: ...
    def list_teams(self) -> list[TeamConfig]: ...
    def get_team_members(self, name: str) -> list[AgentConfig]: ...
    def validate_team(self, name: str) -> list[str]:  # 返回错误列表
        ...
```

### 3.5 测试

**新文件**: `tests/test_broadcast.py`

- [ ] `test_broadcast_parallel` — 并行广播
- [ ] `test_broadcast_sequential` — 顺序广播
- [ ] `test_broadcast_timeout` — 超时处理
- [ ] `test_broadcast_partial_failure` — 部分失败处理
- [ ] `test_team_manager_crud` — TeamManager 查询功能

### 3.6 完成标准
- [ ] agent 可以在对话中使用 `broadcast` 工具
- [ ] parallel/sequential 策略正确执行
- [ ] 超时和部分失败有合理处理
- [ ] 结果聚合为结构化输出

---

## Phase 4: CLI 增强 [P2]

**目标**: 提供 team 相关的 CLI 命令，提升运维体验。

**前置依赖**: Phase 1 + Phase 3

### 4.1 创建 teams CLI 命令组

**新文件**: `cyberclaw/cli/teams.py`

```
cyberclaw teams list                    # 列出所有 team
cyberclaw teams info <team-name>        # 查看 team 详情
cyberclaw teams broadcast <team> <msg>  # 向 team 广播消息
cyberclaw teams status <team>           # 查看 team 成员状态
```

### 4.2 增强 agents 命令

**文件**: `cyberclaw/cli/commands.py`（修改）

新增或增强：
```
cyberclaw agents list                   # 列出所有 agent（含状态）
cyberclaw agents status                 # 查看所有 agent 运行状态
cyberclaw agents switch <agent-id>      # 切换当前 CLI 使用的 agent
```

### 4.3 注册到主 CLI

**文件**: `cyberclaw/cli/commands.py`

```python
from cyberclaw.cli.teams import app as teams_app
app.add_typer(teams_app, name="teams", help="Manage agent teams")
```

### 4.4 完成标准
- [ ] `cyberclaw teams list` 正确显示
- [ ] `cyberclaw agents list` 显示所有 agent 及其状态
- [ ] Rich table 格式输出
- [ ] 帮助文档（`--help`）完整

---

## Phase 5: 高级策略控制 [P2]

**目标**: 增加 rate limiting、token budget、智能路由规则。

**前置依赖**: Phase 1

### 5.1 Rate Limiting

**文件**: `cyberclaw/agent/policy_engine.py`（修改）

新增配置：

```python
class RateLimitPolicy(BaseModel):
    max_spawns_per_minute: int = 10
    max_concurrent_subagents: int = 8
    cooldown_seconds: float = 0
```

在 `AgentToAgentPolicyEngine.check_spawn()` 中增加 rate limit 检查。

### 5.2 Token Budget

**新文件**: `cyberclaw/agent/team/budget.py`

```python
class TokenBudgetTracker:
    """跟踪和限制 agent/subagent 的 token 使用量。"""

    def __init__(self, daily_limit: int = 0, per_task_limit: int = 0):
        ...

    def record_usage(self, agent_id: str, task_id: str, tokens: int): ...
    def check_budget(self, agent_id: str) -> tuple[bool, str]: ...
    def get_usage_report(self) -> dict: ...
```

### 5.3 智能路由规则

**文件**: `cyberclaw/gateway/router.py`（修改）

扩展 `MessageRouter` 支持基于规则的路由：

```python
class RoutingRule(BaseModel):
    condition: dict  # {"contains_keywords": [...], "channel": "...", "sender": "..."}
    route_to: str    # agent_id
    priority: int = 0
```

### 5.4 完成标准
- [ ] 每分钟 spawn 数量限制生效
- [ ] 并发 subagent 数量限制生效
- [ ] Token 用量可被追踪和限制
- [ ] 智能路由规则可配置

---

## Phase 6: 错误处理和恢复 [P2]

**目标**: 增加自动重试、超时处理、错误分类。

### 6.1 自动重试

**文件**: `cyberclaw/agent/subagent.py`（修改）

```python
class SubagentManager:
    async def spawn(self, ..., max_retries: int = 0, retry_delay: float = 5.0):
        """支持失败自动重试。"""
        for attempt in range(max_retries + 1):
            try:
                result = await self._run_subagent(...)
                return result
            except SubagentError as e:
                if attempt < max_retries and self._is_retryable(e):
                    await asyncio.sleep(retry_delay)
                    continue
                raise
```

### 6.2 超时自动处理

**文件**: `cyberclaw/agent/subagent.py`（修改）

增强现有超时检测，加入自动 kill 和通知父 agent。

### 6.3 错误分类

**新文件**: `cyberclaw/agent/team/errors.py`

```python
class SubagentErrorType(Enum):
    NETWORK = "network"       # 网络错误，可重试
    API_LIMIT = "api_limit"   # API 限额，需等待
    LOGIC = "logic"           # 逻辑错误，不可重试
    TIMEOUT = "timeout"       # 超时
    UNKNOWN = "unknown"
```

### 6.4 完成标准
- [ ] 网络类错误自动重试（可配置次数）
- [ ] 超时后自动 kill 并通知
- [ ] 错误类型正确分类
- [ ] 父 agent 收到清晰的错误报告

---

## Phase 7: Web Dashboard [P3]（可选）

**目标**: 基于现有 `web_console/` 扩展，增加 agent team 可视化。

### 7.1 新增页面

在 `web_console/` 中新增 Streamlit 页面：

- **Agent Status** — 显示所有 agent 的运行状态（在线/离线/忙碌）
- **Spawn Tree** — 树形可视化当前 spawn 关系
- **Team Overview** — 显示 team 配置和成员状态
- **Logs** — 实时日志流（按 agent 过滤）
- **Token Usage** — 各 agent 的 token 使用统计

### 7.2 数据 API

**新文件**: `cyberclaw/gateway/api.py`

提供 REST API 供 Dashboard 查询：
```
GET /api/agents          — 所有 agent 状态
GET /api/agents/{id}     — 单个 agent 详情
GET /api/teams           — 所有 team
GET /api/spawn-tree      — 当前 spawn 树
GET /api/usage           — token 使用统计
```

---

## 实施文件清单

### 新增文件（按 Phase 排序）

| Phase | 文件路径 | 说明 |
|-------|----------|------|
| 1 | `cyberclaw/gateway/__init__.py` | 空 |
| 1 | `cyberclaw/gateway/router.py` | 消息路由器 |
| 1 | `cyberclaw/gateway/manager.py` | 多 Agent Gateway 管理器 |
| 1 | `tests/test_gateway_router.py` | 路由器测试 |
| 1 | `tests/test_multi_agent_gateway.py` | Gateway 集成测试 |
| 2 | `cyberclaw/agent/team/__init__.py` | 空 |
| 2 | `cyberclaw/agent/team/orchestrator.py` | Orchestrator 模板 |
| 2 | `tests/test_orchestrator.py` | Orchestrator 测试 |
| 2 | `cyberclaw/skills/orchestrator.md` | Orchestrator skill |
| 3 | `cyberclaw/agent/tools/broadcast.py` | Broadcast 工具 |
| 3 | `cyberclaw/agent/team/manager.py` | Team 管理器 |
| 3 | `tests/test_broadcast.py` | Broadcast 测试 |
| 4 | `cyberclaw/cli/teams.py` | Teams CLI 命令 |
| 5 | `cyberclaw/agent/team/budget.py` | Token 预算追踪 |
| 6 | `cyberclaw/agent/team/errors.py` | 错误分类 |
| 7 | `cyberclaw/gateway/api.py` | REST API |

### 需修改的文件

| Phase | 文件路径 | 修改内容 |
|-------|----------|----------|
| 1 | `cyberclaw/config/schema.py` | 新增 AgentBinding, TeamConfig; 修改 AgentsConfig |
| 1 | `cyberclaw/cli/commands.py` | 修改 gateway() 支持 --multi |
| 2 | `cyberclaw/agent/tools/spawn.py` | 新增 batch spawn 和 wait 参数 |
| 2 | `cyberclaw/agent/announce_chain.py` | 新增 wait_for_children() |
| 3 | `cyberclaw/agent/tools/registry.py` | 注册 BroadcastTool |
| 4 | `cyberclaw/cli/commands.py` | 注册 teams 子命令 |
| 5 | `cyberclaw/agent/policy_engine.py` | 新增 rate limit 检查 |
| 5 | `cyberclaw/gateway/router.py` | 新增智能路由规则 |
| 6 | `cyberclaw/agent/subagent.py` | 新增自动重试和超时增强 |

---

## 推荐实施顺序

```
Week 1:
  ├── Phase 1: Gateway 多 Agent 路由（核心基础）
  │   ├── Day 1: schema 扩展 + router.py
  │   ├── Day 2: manager.py + CLI 集成
  │   └── Day 3: 测试 + 调试
  │
  └── Phase 4: CLI 增强（可并行开发）
      └── Day 2-3: teams.py + agents 增强

Week 2:
  ├── Phase 2: Orchestrator 自动化
  │   ├── Day 1: orchestrator 模板 + batch spawn
  │   └── Day 2: 测试 + 示例工作流
  │
  └── Phase 3: Broadcast / Team
      ├── Day 1: broadcast 工具 + team manager
      └── Day 2: 测试

Week 3 (可选):
  ├── Phase 5: 高级策略控制
  └── Phase 6: 错误处理和恢复

Week 4 (可选):
  └── Phase 7: Web Dashboard
```

---

## 快速验证路径 (MVP)

如果只想尽快验证 Agent Team 的核心价值，可以只做：

1. **Phase 1.1-1.3**（2 天）— schema + router + manager
2. **Phase 1.4**（0.5 天）— CLI 集成
3. **Phase 1.5**（0.5 天）— 测试

**3 天即可获得**: 多 agent 运行 + 消息路由的完整能力。

---

## 下一步

选择要开始的 Phase，执行：
```bash
# 创建功能分支（如果需要新分支）
git checkout -b feat/agent-team-gateway

# 开始编码
# 参照上述各 Phase 的具体步骤
```
