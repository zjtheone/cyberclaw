# Agent Team 通信架构详解

## 📊 核心问题

**Teams 中多个 Agent 之间是如何通信的？**

**答案**: **目前 `teams exec` 命令中的 agents 并不直接通信！** 它们通过 **MessageBus + Announce Chain** 间接协调。

---

## 🏗️ 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                   cyberclaw teams exec                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  CLI: teams.py                                              │
│  ───────────────────────────────────────────────────────    │
│  for member_id in team.members:                             │
│      agent = gw.get_agent(member_id)                        │
│      worker = agent.process_direct(...)  # 独立执行         │
│      workers.append(worker)                                 │
│                                                             │
│  await asyncio.gather(*workers)  # 等待所有完成             │
│  results = aggregate(results)    # 聚合结果                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   MessageBus                                │
│  ───────────────────────────────────────────────────────    │
│  - publish_inbound(msg)   # 发布消息到总线                  │
│  - consume_inbound()      # 消费总线消息                   │
│  - publish_outbound(msg)  # 发布结果到总线                 │
│  - consume_outbound()     # 消费结果消息                   │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Agent: coding│   │Agent:reviewer │   │Agent:debugger │
│  ──────────── │   │────────────── │   │────────────── │
│  AgentLoop    │   │  AgentLoop    │   │  AgentLoop    │
│  process_msg()│   │  process_msg()│   │  process_msg()│
└───────────────┘   └───────────────┘   └───────────────┘
```

---

## 🔑 关键组件

### 1. MessageBus (消息总线)

**文件**: `cyberclaw/bus/queue.py`

```python
class MessageBus:
    """异步消息队列，用于 Agent 间通信"""
    
    def __init__(self):
        self.inbound = asyncio.Queue()   # 输入消息队列
        self.outbound = asyncio.Queue()  # 输出消息队列
    
    async def publish_inbound(self, msg: InboundMessage):
        """发布消息到输入队列"""
        await self.inbound.put(msg)
    
    async def consume_inbound(self) -> InboundMessage:
        """从输入队列消费消息"""
        return await self.inbound.get()
    
    async def publish_outbound(self, msg: OutboundMessage):
        """发布结果到输出队列"""
        await self.outbound.put(msg)
    
    async def consume_outbound(self) -> OutboundMessage:
        """从输出队列消费结果"""
        return await self.outbound.get()
```

**作用**: 所有 Agent 共享同一个 MessageBus，通过它传递消息。

---

### 2. SubagentManager (子 Agent 管理器)

**文件**: `cyberclaw/agent/subagent.py`

```python
class SubagentManager:
    """管理子 Agent 的生成和结果聚合"""
    
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        session_key: str | None = None,
        parent_session_key: str | None = None,  # ← 父 session
    ) -> str:
        """Spawn 子 Agent"""
        
        # 创建子 Agent 的 session key
        subagent_session_key = SessionKey.create_subagent(agent_id, task_id)
        
        # 启动后台任务
        bg_task = asyncio.create_task(
            self._run_subagent_with_retry(
                session_key=str(subagent_session_key),
                parent_session_key=session_key,  # ← 传递给子 Agent
                ...
            )
        )
```

**作用**: 管理父子 Agent 关系，追踪任务完成状态。

---

### 3. AnnounceChain (通知链)

**文件**: `cyberclaw/agent/announce_chain.py`

```python
class AnnounceChainManager:
    """管理分层结果聚合"""
    
    def register_announce(self, event: AnnounceEvent) -> None:
        """注册子 Agent 完成通知"""
        self._events[event.event_id] = event
        
        # 追踪父子关系
        if event.parent_session_key:
            if event.parent_session_key not in self._session_children:
                self._session_children[event.parent_session_key] = []
            self._session_children[event.parent_session_key].append(event.event_id)
            
            # 聚合结果
            if event.parent_session_key not in self._aggregations:
                self._aggregations[event.parent_session_key] = AggregatedResult(
                    parent_session_key=event.parent_session_key
                )
            self._aggregations[event.parent_session_key].add_child(event)
```

**作用**: 当子 Agent 完成时，通知父 Agent 并聚合结果。

---

## 📡 通信流程

### 场景 1: teams exec (当前实现)

```
用户: cyberclaw teams exec dev-team "实现库房系统"
        │
        ▼
┌─────────────────────────────────────────┐
│ 1. CLI 直接 spawn team members           │
│    for member_id in ['coding',          │
│                       'reviewer',        │
│                       'debugger']:       │
│        agent = gw.get_agent(member_id)  │
│        agent.process_direct(task)       │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 2. 所有 agents 独立执行                  │
│    - coding: 写代码                      │
│    - reviewer: 审查代码                 │
│    - debugger: 测试验证                 │
│                                         │
│    ⚠️ 注意：agents 之间不直接通信！       │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 3. CLI 等待所有完成                      │
│    await asyncio.gather(*workers)       │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 4. CLI 聚合结果                          │
│    for member_id, result in results:    │
│        print(f"{member_id}: {result}")  │
└─────────────────────────────────────────┘
```

**特点**:
- ✅ 简单直接
- ✅ 100% 并行执行
- ❌ agents 之间无直接通信
- ❌ 无法跨 agent 协作

---

### 场景 2: Orchestrator + Workers (理想模式)

```
用户：实现库房系统
        │
        ▼
┌─────────────────────────────────────────┐
│ 1. Orchestrator 接收任务                 │
│    🤖 [orchestrator] Processing          │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 2. Orchestrator 使用 spawn 工具          │
│    🔄 spawn(batch=[                      │
│      {"task": "调研", "label": "r1"},   │
│      {"task": "实现", "label": "c1"},   │
│      {"task": "测试", "label": "d1"}    │
│    ])                                    │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 3. SubagentManager 创建 workers          │
│    - 创建 session_key: worker-1         │
│    - 创建 session_key: worker-2         │
│    - 创建 session_key: worker-3         │
│    - parent_session_key: orchestrator   │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 4. Workers 并行执行                      │
│    🤖 [worker-1] Processing: 调研...     │
│    🤖 [worker-2] Processing: 实现...     │
│    🤖 [worker-3] Processing: 测试...     │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 5. Workers 完成，发布 Announce           │
│    AnnounceEvent(                        │
│      task_id="worker-1",                 │
│      result="调研结果...",               │
│      parent_session_key="orchestrator"  │
│    )                                     │
│                                          │
│    AnnounceChain 注册事件                │
│    聚合到 orchestrator 的结果中          │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 6. Orchestrator 聚合所有结果             │
│    results = announce_chain.get_summary()│
│    print(results)                        │
└─────────────────────────────────────────┘
```

**特点**:
- ✅ 真正的多 agent 协作
- ✅ 父子关系明确
- ✅ 结果自动聚合
- ❌ 依赖 orchestrator 决策

---

## 🔍 关键代码位置

### 1. teams exec 实现

**文件**: `cyberclaw/cli/teams.py`

```python
@app.command("exec")
def exec_team(team_name, task, timeout=600, parallel=True):
    # 直接 spawn team members
    for member_id in team.members:
        agent = gw.get_agent(member_id)
        worker_task = asyncio.create_task(
            agent.process_direct(
                content=member_prompt,
                session_key=f"{member_id}:team-exec",
                channel="cli",
                chat_id=f"team-exec-{member_id}"
            )
        )
        workers.append((member_id, worker_task))
    
    # 等待所有 workers
    for member_id, worker in workers:
        result = await asyncio.wait_for(worker, timeout=timeout)
        results[member_id] = result
```

**行号**: 约 140-200 行

---

### 2. MessageBus 实现

**文件**: `cyberclaw/bus/queue.py`

```python
class MessageBus:
    def __init__(self):
        self.inbound = asyncio.Queue()
        self.outbound = asyncio.Queue()
    
    async def publish_inbound(self, msg: InboundMessage):
        await self.inbound.put(msg)
    
    async def consume_inbound(self) -> InboundMessage:
        return await self.inbound.get()
```

**行号**: 约 8-35 行

---

### 3. SubagentManager 实现

**文件**: `cyberclaw/agent/subagent.py`

```python
async def spawn(
    self,
    task: str,
    session_key: str | None = None,
    parent_session_key: str | None = None,
) -> str:
    # 创建子 Agent session
    subagent_session_key = SessionKey.create_subagent(agent_id, task_id)
    
    # 启动后台任务
    bg_task = asyncio.create_task(
        self._run_subagent_with_retry(
            session_key=str(subagent_session_key),
            parent_session_key=session_key,
            ...
        )
    )
```

**行号**: 约 50-120 行

---

### 4. AnnounceChain 实现

**文件**: `cyberclaw/agent/announce_chain.py`

```python
class AnnounceChainManager:
    def register_announce(self, event: AnnounceEvent):
        self._events[event.event_id] = event
        
        # 追踪父子关系
        if event.parent_session_key:
            self._session_children[event.parent_session_key].append(event.event_id)
            self._aggregations[event.parent_session_key].add_child(event)
```

**行号**: 约 100-150 行

---

## 📊 通信方式对比

| 方式 | 直接通信 | 间接通信 | 适用场景 |
|------|---------|---------|---------|
| **teams exec** | ❌ | ✅ MessageBus | 简单并行任务 |
| **spawn workers** | ❌ | ✅ AnnounceChain | 父子任务分解 |
| **broadcast** | ❌ | ✅ MessageBus | 团队广播 |
| **A2A (未来)** | ✅ | ✅ | 复杂协作 |

---

## 🎯 未来改进：Agent 间直接通信

```python
# 理想的 Agent 间通信
class AgentLoop:
    async def process_message(self, msg):
        # Agent 可以发送消息给其他 Agent
        await self.send_to_agent(
            target_agent_id="reviewer",
            message="请审查这段代码：..."
        )
        
        # 等待回复
        response = await self.receive_from_agent("reviewer")
```

**需要实现**:
1. Agent 间的直接消息路由
2. 请求 - 响应模式支持
3. 消息队列和优先级
4. 超时和重试机制

---

## 📚 相关文档

- `cyberclaw/bus/queue.py` - MessageBus 实现
- `cyberclaw/agent/subagent.py` - SubagentManager
- `cyberclaw/agent/announce_chain.py` - AnnounceChain
- `cyberclaw/agent/tools/spawn.py` - Spawn 工具
- `cyberclaw/cli/teams.py` - Teams exec 命令

---

**最后更新**: 2026-03-05
**版本**: 1.0

