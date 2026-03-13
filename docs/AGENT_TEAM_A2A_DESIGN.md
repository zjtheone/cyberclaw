# Agent-to-Agent (A2A) 直接通信架构设计

## 🎯 目标

实现真正的 Agent 间直接通信机制，支持：
1. ✅ Agent 间直接发送消息
2. ✅ 请求 - 响应模式
3. ✅ 消息队列和优先级
4. ✅ 超时和重试机制

---

## 🏗️ 架构设计

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    A2A Communication Layer                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ AgentMessage    │  │ A2ARouter       │  │ MessageQueue│ │
│  │ - from_agent    │  │ - route(msg)    │  │ - priority  │ │
│  │ - to_agent      │  │ - deliver()     │  │ - timeout   │ │
│  │ - type          │  │ - lookup()      │  │ - retry     │ │
│  │ - content       │  │                 │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              A2ARequest (请求 - 响应模式)             │   │
│  │  - request_id                                        │   │
│  │  - from_agent → to_agent: "请审查代码..."           │   │
│  │  - ← response: "审查完成，发现 3 个问题..."          │   │
│  │  - timeout: 300s                                     │   │
│  │  - retries: 3                                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 消息格式

### AgentMessage

```python
@dataclass
class AgentMessage:
    """Agent 间直接通信的消息"""
    
    message_id: str                    # 消息 ID
    from_agent: str                    # 发送者
    to_agent: str                      # 接收者
    type: MessageType                  # 消息类型
    content: str                       # 消息内容
    priority: MessagePriority          # 优先级
    timeout: int                       # 超时时间（秒）
    max_retries: int                   # 最大重试次数
    created_at: datetime               # 创建时间
    request_id: str | None = None      # 关联的请求 ID（响应模式）
    metadata: dict = field(default_factory=dict)
```

### MessageType

```python
class MessageType(Enum):
    REQUEST = "request"           # 请求（需要响应）
    RESPONSE = "response"         # 响应
    NOTIFICATION = "notification" # 通知（无需响应）
    BROADCAST = "broadcast"       # 广播
```

### MessagePriority

```python
class MessagePriority(Enum):
    LOW = 0       # 低优先级
    NORMAL = 1    # 普通优先级
    HIGH = 2      # 高优先级
    URGENT = 3    # 紧急
```

---

## 🔄 通信模式

### 模式 1: 请求 - 响应

```python
# Agent A 发送请求
response = await agent.send_request(
    to_agent="reviewer",
    content="请审查这段代码：...",
    timeout=300,
    priority=MessagePriority.HIGH
)

# Agent B 接收并处理
request = await agent.receive_request()
result = process_request(request)
await agent.send_response(
    request_id=request.message_id,
    content=result
)

# Agent A 接收响应
print(f"审查结果：{response.content}")
```

**流程**:
```
Agent A                         Agent B
   │                              │
   │─ ─ ─ REQUEST ─ ─ ─ ─ ─ ─ ─> │
   │   (请审查代码)                │
   │                              │ 处理请求
   │                              │
   │<─ ─ ─ RESPONSE ─ ─ ─ ─ ─ ─ ─│
   │   (审查完成，3 个问题)         │
   │                              │
```

---

### 模式 2: 通知（无需响应）

```python
# 发送通知
await agent.send_notification(
    to_agent="debugger",
    content="代码已更新，请测试",
    priority=MessagePriority.NORMAL
)
```

**流程**:
```
Agent A                         Agent B
   │                              │
   │─ ─ ─ NOTIFICATION ─ ─ ─ ─ > │
   │   (代码已更新)                │
   │                              │ 处理通知
   │                              │ (无需响应)
```

---

### 模式 3: 广播

```python
# 广播给所有 agents
await agent.broadcast(
    content="系统即将重启",
    priority=MessagePriority.URGENT
)
```

**流程**:
```
Agent A              MessageBus              Other Agents
   │                    │                       │
   │─ ─ ─ BROADCAST ─ ─>│                       │
   │                    │─ ─ ─> Agent B         │
   │                    │─ ─ ─> Agent C         │
   │                    │─ ─ ─> Agent D         │
```

---

## 📬 消息队列

### Priority Queue

```python
class AgentMessageQueue:
    """优先级消息队列"""
    
    def __init__(self):
        self.queues = {
            MessagePriority.URGENT: asyncio.PriorityQueue(),
            MessagePriority.HIGH: asyncio.PriorityQueue(),
            MessagePriority.NORMAL: asyncio.PriorityQueue(),
            MessagePriority.LOW: asyncio.PriorityQueue(),
        }
    
    async def put(self, msg: AgentMessage):
        """放入消息（按优先级）"""
        await self.queues[msg.priority].put(msg)
    
    async def get(self) -> AgentMessage:
        """获取消息（优先级高的先出）"""
        # 按优先级顺序检查队列
        for priority in [MessagePriority.URGENT, MessagePriority.HIGH, 
                        MessagePriority.NORMAL, MessagePriority.LOW]:
            if not self.queues[priority].empty():
                return await self.queues[priority].get()
        
        # 所有队列为空时阻塞等待
        return await self.queues[MessagePriority.NORMAL].get()
```

---

## 🎯 API 设计

### AgentLoop 扩展

```python
class AgentLoop:
    """Agent 主循环（扩展 A2A 功能）"""
    
    # ========== 发送消息 ==========
    
    async def send_request(
        self,
        to_agent: str,
        content: str,
        timeout: int = 300,
        priority: MessagePriority = MessagePriority.NORMAL,
        max_retries: int = 3,
    ) -> AgentMessage:
        """发送请求并等待响应"""
        pass
    
    async def send_response(
        self,
        request_id: str,
        content: str,
    ) -> None:
        """发送响应"""
        pass
    
    async def send_notification(
        self,
        to_agent: str,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        """发送通知"""
        pass
    
    async def broadcast(
        self,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        """广播消息"""
        pass
    
    # ========== 接收消息 ==========
    
    async def receive_request(
        self,
        timeout: int | None = None,
    ) -> AgentMessage:
        """接收请求"""
        pass
    
    async def receive_response(
        self,
        request_id: str,
        timeout: int | None = None,
    ) -> AgentMessage:
        """接收特定请求的响应"""
        pass
    
    async def receive_notification(
        self,
        timeout: int | None = None,
    ) -> AgentMessage:
        """接收通知"""
        pass
```

---

## 🔧 实现要点

### 1. 消息路由

```python
class A2ARouter:
    """A2A 消息路由器"""
    
    def __init__(self, agents: dict[str, AgentLoop]):
        self.agents = agents  # agent_id -> AgentLoop
    
    async def route(self, msg: AgentMessage):
        """路由消息到目标 Agent"""
        target = self.agents.get(msg.to_agent)
        if not target:
            raise AgentNotFoundError(f"Agent {msg.to_agent} not found")
        
        # 放入目标 Agent 的消息队列
        await target.message_queue.put(msg)
```

### 2. 超时处理

```python
async def send_request_with_timeout(
    self,
    to_agent: str,
    content: str,
    timeout: int = 300,
):
    """发送带超时的请求"""
    msg = AgentMessage(
        from_agent=self.agent_id,
        to_agent=to_agent,
        type=MessageType.REQUEST,
        content=content,
        timeout=timeout,
    )
    
    try:
        # 等待响应
        response = await asyncio.wait_for(
            self.response_queue.get(msg.message_id),
            timeout=timeout
        )
        return response
    except asyncio.TimeoutError:
        # 超时重试
        if msg.retry_count < msg.max_retries:
            msg.retry_count += 1
            return await self.send_request_with_timeout(
                to_agent, content, timeout
            )
        else:
            raise TimeoutError(f"Request to {to_agent} timed out after {msg.max_retries} retries")
```

### 3. 优先级队列

```python
class PriorityMessageQueue:
    """优先级消息队列"""
    
    def __init__(self):
        self._queues = {
            priority: []
            for priority in MessagePriority
        }
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition()
    
    async def put(self, msg: AgentMessage):
        async with self._not_empty:
            self._queues[msg.priority].append(msg)
            # 按优先级排序
            self._queues[msg.priority].sort(
                key=lambda m: m.created_at
            )
            self._not_empty.notify()
    
    async def get(self) -> AgentMessage:
        async with self._not_empty:
            # 等待有消息
            while not any(self._queues.values()):
                await self._not_empty.wait()
            
            # 按优先级获取
            for priority in MessagePriority:
                if self._queues[priority]:
                    return self._queues[priority].pop(0)
```

---

## 📊 与现有架构对比

| 特性 | 当前架构 | A2A 架构（新） |
|------|---------|--------------|
| **通信方式** | 间接（CLI 聚合） | 直接 |
| **请求 - 响应** | ❌ 不支持 | ✅ 支持 |
| **消息队列** | ❌ 无 | ✅ 优先级队列 |
| **超时重试** | ❌ 无 | ✅ 支持 |
| **广播** | ✅ (teams exec) | ✅ (原生支持) |
| **异步处理** | ✅ | ✅ 增强 |

---

## 🚀 实施计划

### Phase 1: 基础架构 (2 天)
- [ ] 定义 AgentMessage 数据类
- [ ] 实现 MessageType 和 MessagePriority
- [ ] 创建 A2ARouter

### Phase 2: 消息队列 (1 天)
- [ ] 实现 PriorityMessageQueue
- [ ] 集成到 AgentLoop
- [ ] 添加消息处理循环

### Phase 3: 请求 - 响应 (2 天)
- [ ] 实现 send_request/send_response
- [ ] 实现超时机制
- [ ] 实现重试逻辑

### Phase 4: 测试和文档 (1 天)
- [ ] 编写单元测试
- [ ] 集成测试
- [ ] 更新文档

---

## 💡 使用示例

### 示例 1: 代码审查流程

```python
# Orchestrator 协调代码审查
async def code_review_workflow():
    # 1. 请求 coding agent 实现功能
    code_result = await orchestrator.send_request(
        to_agent="coding",
        content="实现用户登录功能",
        timeout=600
    )
    
    # 2. 请求 reviewer 审查代码
    review_result = await orchestrator.send_request(
        to_agent="reviewer",
        content=f"请审查这段代码：{code_result.content}",
        timeout=300
    )
    
    # 3. 如果有问题，请求 debugger 修复
    if review_result.has_issues:
        await orchestrator.send_request(
            to_agent="debugger",
            content=f"修复这些问题：{review_result.issues}",
            timeout=300
        )
    
    # 4. 聚合结果
    return aggregate_results([code_result, review_result])
```

### 示例 2: 团队协作

```python
# Team 成员间直接通信
async def team_collaboration():
    # coding 请求 research 提供最佳实践
    best_practices = await coding.send_request(
        to_agent="research",
        content="提供电商系统的最佳实践",
        timeout=300
    )
    
    # 实现后通知 reviewer
    await coding.send_notification(
        to_agent="reviewer",
        content="代码已实现，请审查"
    )
    
    # reviewer 审查后发送响应
    review_result = await reviewer.send_response(
        request_id=request_id,
        content="审查通过，发现 2 个优化点..."
    )
```

---

**设计完成时间**: 2026-03-05
**版本**: 1.0 (设计稿)
**下一步**: 开始实现 Phase 1

