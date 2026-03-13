# cyberclaw Agent Team 功能完善规划

## 📋 现状分析

### 已实现的核心功能 ✅

根据代码和文档分析，cyberclaw 已经实现了 Agent Team 的核心基础设施：

1. **多 Agent 配置支持**
   - `AgentsConfig` 和 `AgentConfig` schema
   - 支持配置多个独立 agent，每个 agent 有独立的 workspace、model、参数
   - 位置：`cyberclaw/config/schema.py`

2. **A2A (Agent-to-Agent) 通信协议**
   - `AgentToAgentPolicyEngine` - 策略引擎（白名单/黑名单/深度限制）
   - `SessionVisibilityEngine` - 会话可见性控制
   - 位置：`cyberclaw/agent/policy_engine.py`

3. **Subagent 系统**
   - `SubagentManager` - 管理后台 subagent 执行
   - 支持嵌套 subagent（orchestrator pattern）
   - 支持深度限制（max_spawn_depth）
   - 位置：`cyberclaw/agent/subagent.py`

4. **Spawn 工具**
   - `SpawnTool` - 创建 subagent 的工具
   - 集成策略检查
   - 位置：`cyberclaw/agent/tools/spawn.py`

5. **Announce Chain**
   - `AnnounceChainManager` - 层级结果聚合
   - `AnnounceEvent` 和 `AggregatedResult` 数据结构
   - 支持 cascade stop（级联停止）
   - 位置：`cyberclaw/agent/announce_chain.py`

6. **PingPong 对话**
   - `AgentToAgentFlow` - 管理多轮对话
   - 支持 turn limits 和 timeout
   - 位置：`cyberclaw/agent/a2a_flow.py`

7. **CLI 管理工具**
   - `cli/subagents.py` - Subagent 管理命令
   - `cli/sessions.py` - Session 管理命令
   - 位置：`cyberclaw/cli/`

8. **会话键系统**
   - `SessionKey` - 统一的会话键格式和解析
   - 支持 main agent 和 subagent 会话区分
   - 位置：`cyberclaw/session/keys.py`

9. **文档和测试**
   - 88 个测试用例，100% 通过率
   - 完整文档：`A2A_COMPLETE_GUIDE.md`, `A2A_QUICK_START.md`
   - 实现分析：`AGENT_TEAM_IMPLEMENTATION.md`
   - 测试报告：`AGENT_TEAM_TEST_REPORT.md`

---

## 🔍 识别的差距和改进机会

尽管核心架构已完整，但通过深入代码审查，发现以下可以完善的领域：

### 1. **Gateway 模式的多 Agent 路由** 🔴 缺失

**现状**：
- 当前的 `AgentLoop` (在 `cyberclaw/agent/loop.py`) 只支持单一 agent 实例
- Gateway 启动时，只有一个 agent 实例运行，无法根据 bindings 路由到不同 agent
- 配置文件中虽然支持 `agents.list`，但没有实际的多 agent 路由实现

**需要实现**：
```python
# 伪代码示例
class MultiAgentGateway:
    def __init__(self):
        self.agents: dict[str, AgentLoop] = {}
        self.bindings: list[Binding] = []
    
    async def route_message(self, msg: InboundMessage):
        # 根据 channel/chat_id/bindings 路由到正确的 agent
        target_agent = self._find_target_agent(msg)
        return await target_agent.process_message(msg)
```

**优先级**: 🔴 高

---

### 2. **Orchestrator Pattern 的自动化支持** 🟡 部分支持

**现状**：
- 支持手动 spawn subagent，但缺少自动化的 orchestrator 模式
- 没有预定义的"协调者"角色模板
- 结果聚合需要父 agent 手动处理 announce 消息

**需要实现**：
- Orchestrator 角色定义（系统 prompt 模板）
- 自动结果聚合并触发下一步行动
- Worker 任务分配模式（一次性 spawn 多个 worker）

**优先级**: 🟡 中

---

### 3. **Broadcast Groups (并行处理组)** 🔴 缺失

**现状**：
- 支持单个 spawn，但缺少"broadcast"模式
- 无法一键让多个 agent 同时处理同一消息
- 缺少 agent team 的显式分组概念

**需要实现**：
```python
# 示例：broadcast 到 team
await gateway.broadcast_to_team(
    team=["coding", "research", "design"],
    message="实现用户登录功能",
    aggregation_strategy="sequential"  # 或 "parallel"
)
```

**优先级**: 🟡 中

---

### 4. **增强的 CLI 命令** 🟢 可用但可增强

**现状**：
- 已有基础命令：`list`, `tree`, `spawn`, `steer`, `log`, `kill`
- 但缺少一些高级功能

**需要增强**：
- `cyberclaw teams list` - 列出预定义的 agent teams
- `cyberclaw teams broadcast <team> <message>` - broadcast 模式
- `cyberclaw agents status` - 查看所有 agent 的健康状态
- `cyberclaw agents switch <agent-id>` - 切换当前会话的 agent
- `cyberclaw subagents wait <id>` - 等待 subagent 完成并显示结果

**优先级**: 🟢 低

---

### 5. **可视化 Dashboard** 🔴 缺失

**现状**：
- 只有 CLI 输出
- 无法直观看到 spawn 树、agent 状态、任务进度

**需要实现**：
- Web 界面显示 agent team 状态
- 实时 spawn 树可视化
- Agent 间通信历史
- Token 使用统计

**优先级**: 🟢 低（可选）

---

### 6. **Session 持久化和跨会话上下文** 🟡 部分支持

**现状**：
- Session 保存在内存和文件中
- 但 agent 之间的会话上下文不共享
- 跨 agent 会话时，history 不连续

**需要增强**：
- 可选的跨 agent session 共享
- Vector memory 支持 agent team 级别
- 会话历史导出/导入

**优先级**: 🟡 中

---

### 7. **高级策略控制** 🟡 部分支持

**现状**：
- 已有基础的 allow/deny 列表
- 已有深度限制和 turn 限制
- 但缺少：
  - 基于时间的限制（rate limiting）
  - 基于 token 预算的限制
  - 基于任务类型的路由策略

**需要实现**：
```json
{
  "tools": {
    "agent_to_agent": {
      "enabled": true,
      "rate_limit": {
        "max_spawns_per_minute": 5,
        "max_concurrent_subagents": 10
      },
      "token_budget": {
        "max_daily_tokens": 1000000,
        "per_subagent_limit": 100000
      },
      "routing_rules": [
        {
          "if": {"contains_keywords": ["code", "implement"]},
          "route_to": "coding"
        },
        {
          "if": {"contains_keywords": ["research", "find"]},
          "route_to": "research"
        }
      ]
    }
  }
}
```

**优先级**: 🟡 中

---

### 8. **错误处理和恢复机制** 🟡 部分支持

**现状**：
- 有基础的 error announce
- cascade stop 支持
- 但缺少：
  - Subagent 失败重试机制
  - 超时自动 recovery
  - 错误分类和智能处理

**需要实现**：
- 失败 subagent 自动重试（可配置次数）
- 超时检测和自动 kill
- 错误类型识别（网络错误、API 限制、逻辑错误）

**优先级**: 🟡 中

---

## 🎯 实施阶段规划

### Phase 1: Gateway 多 Agent 路由（核心功能）

**目标**: 让 Gateway 支持多 agent 实例和消息路由

**任务**:
1. [ ] 创建 `MultiAgentGateway` 类
2. [ ] 实现 agent 实例管理（启动/停止/健康检查）
3. [ ] 实现消息路由逻辑
4. [ ] 实现 bindings 配置
5. [ ] 更新 CLI 的 `gateway` 命令
6. [ ] 添加集成测试

**预计工作量**: 3-4 天

---

### Phase 2: Orchestrator Pattern 增强

**目标**: 自动化的 orchestrator 工作流

**任务**:
1. [ ] 创建 orchestrator 角色模板（system prompt）
2. [ ] 实现自动任务分解和 worker spawn
3. [ ] 实现自动结果聚合和推进
4. [ ] 添加 orchestrator 专用 CLI 命令
5. [ ] 编写示例工作流

**预计工作量**: 2-3 天

---

### Phase 3: Broadcast Groups

**目标**: 支持多 agent 并行处理

**任务**:
1. [ ] 实现 team 配置（显式分组）
2. [ ] 创建 broadcast 工具
3. [ ] 实现结果聚合策略（sequential vs parallel）
4. [ ] 添加 CLI 命令
5. [ ] 编写使用示例

**预计工作量**: 2 天

---

### Phase 4: CLI 增强

**目标**: 提升用户体验

**任务**:
1. [ ] 添加 `teams` 命令组
2. [ ] 添加 `agents status` 命令
3. [ ] 增强 `subagents wait` 命令
4. [ ] 改进 Rich 输出格式
5. [ ] 添加交互式菜单（可选）

**预计工作量**: 1-2 天

---

### Phase 5: 高级策略控制（可选）

**目标**: 更精细的控制

**任务**:
1. [ ] 实现 rate limiting
2. [ ] 实现 token budget 追踪
3. [ ] 实现智能路由规则
4. [ ] 添加策略配置 UI（可选）

**预计工作量**: 2-3 天

---

### Phase 6: Web Dashboard（可选）

**目标**: 可视化监控

**任务**:
1. [ ] 创建简单的 Web 界面（基于现有 web_console）
2. [ ] 实现 agent 状态展示
3. [ ] 实现 spawn 树可视化
4. [ ] 实现实时日志流

**预计工作量**: 4-5 天

---

## 📁 推荐的文件结构变更

### 新增文件

```
cyberclaw/
├── gateway/                    # 新增：多 agent gateway
│   ├── __init__.py
│   ├── manager.py              # MultiAgentGateway 类
│   ├── router.py               # 消息路由逻辑
│   └── bindings.py             # Binding 配置和匹配
│
├── agent/
│   ├── team/                   # 新增：Agent Team 核心逻辑
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Orchestrator 模式实现
│   │   ├── broadcast.py        # Broadcast 功能
│   │   └── roles.py            # Agent 角色定义
│   │
│   └── tools/
│       ├── broadcast.py        # Broadcast 工具 (新增)
│       └── team.py             # Team 管理工具 (新增)
│
├── cli/
│   └── teams.py                # Team CLI 命令 (新增)
│
└── dashboard/                  # 新增：Web Dashboard (可选)
    ├── __init__.py
    ├── app.py                  # Streamlit 应用
    ├── components/             # UI 组件
    │   ├── agent_status.py
    │   ├── spawn_tree.py
    │   └── logs.py
    └── api.py                  # REST API
```

### 修改的文件

```
cyberclaw/
├── cli/commands.py             # 添加 teams 命令入口
├── config/schema.py            # 添加 team 配置和高级策略
├── agent/loop.py               # 可能需要在 process_direct 中添加 team 支持
└── gateway/                    # 如果已有 gateway 模块，需要扩展
```

---

## 🔧 具体实施步骤

### 步骤 1: Gateway 多 Agent 路由实现

#### 1.1 创建配置文件扩展

```python
# cyberclaw/config/schema.py

class AgentBinding(BaseModel):
    """Binding rule for routing messages to agents."""
    channel: str | None = None
    chat_pattern: str | None = None  # regex pattern
    keyword: str | None = None
    agent_id: str

class AgentTeamConfig(BaseModel):
    """Agent team definition."""
    name: str
    members: list[str]  # agent IDs
    leader: str | None = None  # leader agent ID
    strategy: str = "parallel"  # parallel | sequential

class TeamGatewayConfig(BaseModel):
    """Gateway configuration for multi-agent."""
    agents: list[AgentConfig]
    bindings: list[AgentBinding]
    teams: list[AgentTeamConfig]
    default_agent: str
```

#### 1.2 实现 MultiAgentGateway

```python
# cyberclaw/gateway/manager.py

class MultiAgentGateway:
    def __init__(self, config: TeamGatewayConfig, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.agents: dict[str, AgentLoop] = {}
        self.router = MessageRouter(config.bindings)
        
    async def start(self):
        # 启动所有配置的 agent
        for agent_config in self.config.agents:
            self.agents[agent_config.id] = await self._create_agent(agent_config)
    
    async def handle_message(self, msg: InboundMessage):
        # 路由消息到正确的 agent
        target_agent_id = self.router.route(msg)
        if target_agent_id not in self.agents:
            target_agent_id = self.config.default_agent
        
        agent = self.agents[target_agent_id]
        return await agent.process_message(msg)
```

#### 1.3 更新 CLI gateway 命令

```python
# cyberclaw/cli/commands.py

@app.command()
async def gateway(
    multi_agent: bool = typer.Option(False, "--multi", help="Enable multi-agent mode"),
):
    if multi_agent:
        from cyberclaw.gateway.manager import MultiAgentGateway
        gateway = MultiAgentGateway(config, bus)
        await gateway.start()
    else:
        # 现有单 agent gateway
        pass
```

---

### 步骤 2: Orchestrator Pattern 实现

#### 2.1 创建 Orchestrator 角色

```python
# cyberclaw/agent/team/orchestrator.py

ORCHESTRATOR_PROMPT = """
你是一个协调者 (Orchestrator)，负责任务分解和结果整合。

你的工作流程：
1. 分析用户请求，识别需要并行处理的子任务
2. 为每个子任务 spawn 专门的 subagent
3. 等待所有 subagent 完成
4. 聚合结果并生成综合报告
5. 如果有缺失，spawn 额外的 subagent 补充

可用工具：
- spawn: 创建 subagent（指定 task 和 label）
- 其他工具...

注意：
- 一次 spawn 所有可以并行的任务
- 等待所有任务完成后再综合
- 如果某个任务失败，决定重试或报告
"""

class OrchestratorMode:
    def __init__(self, agent_loop: AgentLoop):
        self.agent_loop = agent_loop
    
    async def execute(self, task: str):
        # 1. 分析任务并分解
        subtasks = await self._decompose_task(task)
        
        # 2. Spawn workers
        spawn_results = []
        for subtask in subtasks:
            result = await self.agent_loop.tools.execute(
                "spawn",
                task=subtask["description"],
                label=subtask["label"]
            )
            spawn_results.append(result)
        
        # 3. 等待所有完成（通过 announce chain）
        aggregated = await self._wait_for_completion()
        
        # 4. 合成最终结果
        final = await self._synthesize(aggregated)
        
        return final
```

---

### 步骤 3: Broadcast 功能实现

#### 3.1 创建 Broadcast 工具

```python
# cyberclaw/agent/tools/broadcast.py

class BroadcastTool(Tool):
    name = "broadcast"
    
    async def execute(
        self,
        team: list[str],
        message: str,
        aggregation_strategy: str = "parallel",
        timeout_seconds: int = 300,
    ):
        """
        Broadcast a message to multiple agents simultaneously.
        
        Args:
            team: List of agent IDs to broadcast to
            message: Message to send
            aggregation_strategy: "parallel" or "sequential"
            timeout_seconds: Maximum wait time
        """
        # 1. Spawn subagents for each team member
        tasks = []
        for agent_id in team:
            task = await self._manager.spawn(
                task=message,
                label=f"{agent_id}: broadcast",
                target_agent_id=agent_id,
            )
            tasks.append(task)
        
        # 2. Wait for all to complete
        results = await self._wait_for_all(tasks, timeout=timeout_seconds)
        
        # 3. Aggregate based on strategy
        if aggregation_strategy == "sequential":
            return self._aggregate_sequential(results)
        else:
            return self._aggregate_parallel(results)
```

#### 3.2 添加 Team 配置

```json
{
  "agents": {
    "teams": [
      {
        "name": "dev-team",
        "members": ["backend", "frontend", "qa"],
        "leader": "team-lead",
        "strategy": "parallel"
      },
      {
        "name": "research-team",
        "members": ["researcher1", "researcher2", "analyst"],
        "strategy": "sequential"
      }
    ]
  }
}
```

---

### 步骤 4: CLI 增强

#### 4.1 创建 teams CLI

```python
# cyberclaw/cli/teams.py

import typer

app = typer.Typer()

@app.command("list")
def list_teams():
    """List all configured agent teams."""
    config = load_config()
    teams = config.agents.teams
    
    # Rich table output
    table = Table(title="Agent Teams")
    table.add_column("Name")
    table.add_column("Members")
    table.add_column("Leader")
    table.add_column("Strategy")
    
    for team in teams:
        table.add_row(
            team.name,
            ", ".join(team.members),
            team.leader or "-",
            team.strategy,
        )
    
    console.print(table)

@app.command("broadcast")
def broadcast_to_team(
    team_name: str,
    message: str,
):
    """Broadcast a message to a team."""
    # Implementation
    pass

@app.command("status")
def team_status(team_name: str):
    """Show status of a specific team."""
    # Implementation
    pass
```

---

## ✅ 验证和测试计划

### 单元测试

- [ ] `test_gateway_router.py` - 路由逻辑测试
- [ ] `test_orchestrator.py` - Orchestrator 模式测试
- [ ] `test_broadcast.py` - Broadcast 功能测试
- [ ] `test_rate_limiting.py` - Rate limiting 测试

### 集成测试

- [ ] `test_multi_agent_gateway.py` - 完整 gateway 工作流
- [ ] `test_team_broadcast.py` - Team broadcast 工作流
- [ ] `test_cascade_failure.py` - 级联失败处理

### 端到端测试

- [ ] 实际运行多 agent gateway
- [ ] 测试 orchestrator pattern
- [ ] 测试 broadcast 到 team

---

## 📊 成功标准

### Phase 1 完成标准

- [ ] Gateway 可以启动多个 agent 实例
- [ ] 消息正确路由到目标 agent
- [ ] bindings 配置生效
- [ ] CLI 命令正常工作
- [ ] 所有测试通过

### Phase 2 完成标准

- [ ] Orchestrator 模式可以自动分解任务
- [ ] Worker subagents 正确执行
- [ ] 结果自动聚合
- [ ] 示例工作流演示成功

### Phase 3 完成标准

- [ ] Broadcast 工具可用
- [ ] Team 配置正确加载
- [ ] 并行/顺序聚合策略工作正常
- [ ] CLI 命令正常工作

---

## 🎯 推荐实施顺序

**推荐按以下顺序实施**：

1. **Phase 1 (Gateway 多 Agent 路由)** - 这是基础架构，必须先实现
2. **Phase 4 (CLI 增强)** - 提升开发体验，便于后续测试
3. **Phase 2 (Orchestrator Pattern)** - 核心价值功能
4. **Phase 3 (Broadcast Groups)** - 增强功能
5. **Phase 5 (高级策略)** - 可选，根据需求
6. **Phase 6 (Dashboard)** - 可选，锦上添花

---

## 🚀 快速启动建议

如果你想快速验证 Agent Team 的价值，建议：

### 最小可行产品 (MVP)

只做以下功能：
1. Phase 1 的核心路由（1-2 天）
2. 简单的 CLI 命令增强（0.5 天）
3. 编写示例工作流文档（0.5 天）

**总计**: 3 天即可看到 multi-agent gateway 工作

### 完整 MVP+

在 MVP 基础上增加：
4. Orchestrator pattern（2 天）
5. Broadcast 工具（1 天）

**总计**: 6 天即可拥有完整的 Agent Team 功能

---

## 📚 参考资源

- OpenClaw agent team 实现：https://github.com/openclaw/openclaw
- cyberclaw 现有 A2A 文档：`docs/A2A_COMPLETE_GUIDE.md`
- cyberclaw 实现分析：`docs/AGENT_TEAM_IMPLEMENTATION.md`

---

**文档创建时间**: 2026-03-04  
**状态**: Ready for Implementation  
**下一步**: 选择要实施的 Phase，开始编码
