# cyberclaw A2A 实施 - 快速参考

## 🎯 核心目标

实现 OpenClaw 风格的 Agent-to-Agent 协议，让 cyberclaw 支持：
- ✅ 多 Agent 协作
- ✅ 嵌套 Subagent (Orchestrator Pattern)
- ✅ 跨 Agent 通信
- ✅ 团队管理命令

---

## 📋 实施步骤 (5-7 天)

### Phase 1: 基础架构 (Day 1-2)

#### 1. 会话键格式改造
```python
# 从
session_key = "cli:direct"

# 改为
session_key = "agent:main:subagent:abc123"
```

**文件**: `cyberclaw/session/keys.py` (新建), `cyberclaw/session/manager.py` (修改)

#### 2. 多 Agent 配置
```json
{
  "agents": {
    "list": [
      {"id": "main", "workspace": "~/.cyberclaw/workspace-main"},
      {"id": "coding", "workspace": "~/.cyberclaw/workspace-coding"},
      {"id": "research", "workspace": "~/.cyberclaw/workspace-research"}
    ]
  }
}
```

**文件**: `cyberclaw/config/schema.py`

---

### Phase 2: A2A 控制 (Day 2-3)

#### 3. Agent-to-Agent 策略
```python
{
  "tools": {
    "agent_to_agent": {
      "enabled": true,
      "allow": ["main", "coding", "research"],
      "max_ping_pong_turns": 5
    }
  }
}
```

**文件**: `cyberclaw/agent/policy.py` (新建)

#### 4. 嵌套 Subagent
```python
# 配置
{
  "agents": {
    "defaults": {
      "subagents": {
        "max_spawn_depth": 2,  # 允许 3 层：main → orchestrator → worker
        "max_children_per_agent": 5
      }
    }
  }
}
```

**文件**: `cyberclaw/agent/subagent.py`

---

### Phase 3: Announce Chain (Day 3-4)

#### 5. 层级结果聚合
```
Depth-2 Worker 完成
  ↓ announce
Depth-1 Orchestrator 聚合
  ↓ announce  
Depth-0 Main Agent
  ↓ 回复用户
```

**文件**: `cyberclaw/agent/subagent.py`, `cyberclaw/bus/events.py`

#### 6. PingPong 对话
```python
# 自动多轮对话
{
  "session": {
    "agent_to_agent": {
      "max_ping_pong_turns": 5  # 最多 5 轮自动对话
    }
  }
}
```

**文件**: `cyberclaw/agent/tools/sessions_send.py` (新建)

---

### Phase 4: CLI 命令 (Day 4-5)

#### 7. 团队管理命令
```bash
# 查看 subagent
/subagents list

# 停止 subagent
/subagents kill <id|all>

# 发送消息
/subagents send <id> <message>

# 查看日志
/subagents log <id> [limit]
```

**文件**: `cyberclaw/cli/subagents.py` (新建)

#### 8. 会话生命周期
```bash
# 聚焦到子代理会话
/focus <target>

# 取消聚焦
/unfocus

# 设置空闲超时
/session idle <duration>
```

**文件**: `cyberclaw/cli/sessions.py` (新建)

---

## 🔧 关键代码片段

### 会话键解析
```python
# cyberclaw/session/keys.py
@dataclass
class SessionKey:
    agent_id: str
    session_type: Literal["main", "subagent", "acp", "cron"]
    session_id: str
    
    def __str__(self) -> str:
        return f"agent:{self.agent_id}:{self.session_type}:{self.session_id}"
    
    @classmethod
    def parse(cls, key: str) -> "SessionKey":
        parts = key.split(":")
        if len(parts) >= 4 and parts[0] == "agent":
            return cls(agent_id=parts[1], session_type=parts[2], session_id=parts[3])
        return cls(agent_id="default", session_type="main", session_id=key)
```

### A2A 策略检查
```python
# cyberclaw/agent/policy.py
class AgentToAgentPolicy(BaseModel):
    enabled: bool = False
    allow: list[str] = Field(default_factory=list)
    
    def is_allowed(self, requester_id: str, target_id: str) -> bool:
        if not self.enabled:
            return False
        if "*" in self.allow:
            return True
        return target_id in self.allow
```

### 嵌套深度检查
```python
# cyberclaw/agent/subagent.py
async def spawn(self, task: str, ..., parent_depth: int = 0):
    max_depth = self.config.tools.agent_to_agent.max_spawn_depth or 1
    if parent_depth >= max_depth:
        return f"Error: Maximum spawn depth ({max_depth}) reached"
    
    # Create child session with depth+1
    session = self.session_manager.create(
        key=f"agent:{agent_id}:subagent:{task_id}",
        spawn_depth=parent_depth + 1,
        parent_session_key=current_session,
    )
```

---

## 📊 优先级矩阵

| 功能 | 优先级 | 工作量 | 价值 |
|------|--------|--------|------|
| 会话键格式 | 🔴 高 | 4h | ⭐⭐⭐⭐⭐ |
| 多 Agent 配置 | 🔴 高 | 6h | ⭐⭐⭐⭐⭐ |
| A2A 策略 | 🔴 高 | 6h | ⭐⭐⭐⭐⭐ |
| 嵌套 Subagent | 🟡 中 | 8h | ⭐⭐⭐⭐ |
| Announce Chain | 🟡 中 | 8h | ⭐⭐⭐⭐ |
| PingPong 对话 | 🟡 中 | 6h | ⭐⭐⭐ |
| CLI 命令 | 🟢 低 | 6h | ⭐⭐⭐ |
| 生命周期管理 | 🟢 低 | 4h | ⭐⭐ |

---

## 🚀 MVP 范围 (3 天快速版)

如果时间紧张，只实现以下核心功能：

### Day 1: 基础
- [ ] 会话键格式改造
- [ ] 多 Agent 配置

### Day 2: 控制
- [ ] A2A 策略引擎
- [ ] 嵌套 Subagent (maxSpawnDepth=2)

### Day 3: 管理
- [ ] CLI: subagents list/kill
- [ ] 基础测试

**MVP 不包含**:
- ❌ Announce Chain 层级聚合
- ❌ PingPong 自动对话
- ❌ 细粒度会话可见性

---

## 📚 完整文档

详细实施规划：`A2A_IMPLEMENTATION_PLAN.md`

---

**更新日期**: 2026-03-03
**状态**: 待实施
