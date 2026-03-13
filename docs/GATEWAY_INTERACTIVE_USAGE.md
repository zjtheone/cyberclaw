# Cyberclaw Gateway 交互模式使用指南

> 方案 A + C 完整实现：HTTP API + 交互式 CLI

---

## 🚀 快速开始

### 方式 1: 交互式 CLI（最简单）⭐

```bash
# 启动 Gateway 并进入交互模式
cyberclaw gateway --multi --interactive

# 或简写
cyberclaw gateway -m -i
```

**输出**:
```
🐈 Starting cyberclaw gateway in MULTI-AGENT mode on port 18790...
Configured agents: ['orchestrator', 'main', 'coding', 'research', 'reviewer', 'debugger']
Default agent: orchestrator
Routing rules: 6

2026-03-04 19:30:00 | INFO | MultiAgentGateway started with 6 agents
HTTP Server started at http://127.0.0.1:18791
  POST /chat - Send message to gateway
  GET  /status - Get gateway status
  GET  /health - Health check

======================================================================
Gateway 已启动，可以直接输入消息测试路由
输入 'quit' 或 'exit' 退出
======================================================================

📤 输入消息：帮我写个快速排序算法
```

---

### 方式 2: Gateway + CLI 客户端（推荐用于生产）

**终端 1: 启动 Gateway**
```bash
cyberclaw gateway --multi
```

**终端 2: 使用 CLI 连接 Gateway**
```bash
cyberclaw agent --gateway http://localhost:18791 -s test0304v6
```

**或简写**:
```bash
cyberclaw agent -g http://localhost:18791 -s test0304v6
```

---

## 📋 使用场景

### 场景 1: 单终端测试（交互式 CLI）

适合快速测试和调试：

```bash
# 启动交互模式
cyberclaw gateway --multi -i

# 直接输入消息
📤 输入消息：帮我写个代码
🔄 发送消息到 Gateway...
2026-03-04 19:30:00 | DEBUG | Routing message from cli:interactive to agent coding

# 查看实时日志和回复
```

**优点**:
- ✅ 一个终端完成所有操作
- ✅ 实时看到路由日志
- ✅ 适合调试

**缺点**:
- ❌ 不支持多用户
- ❌ 无法后台运行

---

### 场景 2: 多终端客户端（生产模式）

适合实际使用：

```bash
# 终端 1: Gateway 后台运行
cyberclaw gateway --multi &

# 终端 2: 用户 A
cyberclaw agent -g http://localhost:18791 -s user-a

# 终端 3: 用户 B
cyberclaw agent -g http://localhost:18791 -s user-b
```

**优点**:
- ✅ 支持多用户
- ✅ Gateway 可后台运行
- ✅ Session 隔离

**缺点**:
- ❌ 需要多个终端
- ❌ 日志分散在不同窗口

---

### 场景 3: HTTP API 集成（开发集成）

适合集成到其他系统：

```bash
# 启动 Gateway
cyberclaw gateway --multi
```

**Python 调用**:
```python
import aiohttp
import asyncio

async def send_message(content):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'http://localhost:18791/chat',
            json={
                'content': content,
                'chat_id': 'my-session',
                'channel': 'api',
                'sender_id': 'user'
            }
        ) as resp:
            data = await resp.json()
            return data['content']

# 使用
response = asyncio.run(send_message("帮我写个代码"))
print(response)
```

**curl 调用**:
```bash
curl -X POST http://localhost:18791/chat \
  -H "Content-Type: application/json" \
  -d '{
    "content": "帮我写个快速排序",
    "chat_id": "test-session",
    "channel": "curl"
  }'
```

---

## 🎯 路由测试

### 测试不同 Agent

```bash
cyberclaw gateway --multi -i

# 测试 coding agent
📤 输入消息：帮我写个快速排序算法
# → 路由到 coding

# 测试 research agent
📤 输入消息：搜索一下 React 最佳实践
# → 路由到 research

# 测试 reviewer agent
📤 输入消息：审查这段代码的性能问题
# → 路由到 reviewer

# 测试 debugger agent
📤 输入消息：调试这个报错：TypeError
# → 路由到 debugger

# 测试 orchestrator agent
📤 输入消息：帮我做个完整的博客系统
# → 路由到 orchestrator
```

### 查看路由日志

```
2026-03-04 19:30:00 | DEBUG | Routing message from cli:interactive to agent coding
2026-03-04 19:30:05 | INFO  | Agent coding completed task in 5.2s

2026-03-04 19:31:00 | DEBUG | Routing message from cli:interactive to agent research
2026-03-04 19:31:08 | INFO  | Agent research completed task in 8.1s
```

---

## 🌐 HTTP API 文档

### Endpoints

| Endpoint | Method | 说明 |
|----------|--------|------|
| `/chat` | POST | 发送消息到 Gateway |
| `/status` | GET | 获取 Gateway 状态 |
| `/health` | GET | 健康检查 |

### POST /chat

**Request**:
```json
{
  "content": "消息内容",
  "chat_id": "会话 ID（可选，默认：default）",
  "channel": "渠道（可选，默认：http）",
  "sender_id": "发送者 ID（可选，默认：user）",
  "timeout": "超时秒数（可选，默认：300）"
}
```

**Response**:
```json
{
  "content": "Agent 响应内容",
  "session_key": "会话标识",
  "response_id": "响应 ID"
}
```

**错误响应**:
```json
{
  "error": "错误描述"
}
```

### GET /status

**Response**:
```json
{
  "status": "running",
  "uptime": 3600.5,
  "uptime_human": "1.0 小时",
  "agent_count": 6,
  "agents": ["orchestrator", "main", "coding", ...],
  "default_agent": "orchestrator",
  "routing_rules": 6,
  "teams": 4,
  "team_names": ["dev-team", "research-team", ...]
}
```

### GET /health

**Response**:
```json
{
  "status": "healthy",
  "gateway_running": true
}
```

---

## 🔧 配置说明

### 默认端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Gateway MessageBus | 18790 | 内部消息总线（不直接访问） |
| HTTP Server | 18791 | REST API 端点 |

### 环境变量

无需特殊环境变量。

### 依赖

HTTP Server 需要 `aiohttp`：

```bash
# 已自动安装，如果缺失请手动安装
pip install aiohttp
```

---

## 💡 最佳实践

### 1. 开发环境

```bash
# 使用交互模式，快速测试
cyberclaw gateway --multi -i
```

### 2. 测试环境

```bash
# 后台运行 Gateway
nohup cyberclaw gateway --multi > gateway.log 2>&1 &

# 多个测试终端连接
cyberclaw agent -g http://localhost:18791 -s test-1
cyberclaw agent -g http://localhost:18791 -s test-2
```

### 3. 生产环境

```bash
# 使用进程管理器（systemd/supervisor）
# 配置 HTTP 反向代理（nginx）

# nginx 配置示例
server {
    listen 80;
    server_name bot.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:18791;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# 客户端连接
cyberclaw agent -g https://bot.example.com -s user-session
```

---

## 🐛 故障排查

### 问题 1: HTTP Server 未启动

**症状**:
```
WARNING | aiohttp not installed, HTTP server disabled
```

**解决**:
```bash
pip install aiohttp
cyberclaw gateway --multi
```

### 问题 2: 连接被拒绝

**症状**:
```
Connection Error: Cannot connect to host localhost:18791
```

**解决**:
```bash
# 检查 Gateway 是否运行
ps aux | grep "cyberclaw gateway"

# 检查端口是否监听
lsof -i :18791

# 重启 Gateway
pkill -f "cyberclaw gateway"
cyberclaw gateway --multi
```

### 问题 3: 路由不工作

**症状**: 消息没有路由到正确的 agent

**解决**:
```bash
# 检查配置
cat ~/.cyberclaw/config.json | jq '.agents.bindings'

# 查看详细日志
cyberclaw gateway --multi -v
```

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| `AGENT_TEAM_CONFIG.md` | Agent Team 配置指南 |
| `AGENT_TEAM_USAGE_GUIDE.md` | 完整使用指南 |
| `GATEWAY_STATUS_USAGE.md` | 状态监控指南 |
| `check_gateway_status.py` | Python 状态检查脚本 |

---

## 🎯 快速参考

```bash
# 方式 1: 交互模式（单终端）
cyberclaw gateway --multi -i

# 方式 2: Gateway + CLI 客户端（多终端）
cyberclaw gateway --multi                  # 终端 1
cyberclaw agent -g http://localhost:18791  # 终端 2

# 方式 3: HTTP API（程序调用）
curl -X POST http://localhost:18791/chat \
  -H "Content-Type: application/json" \
  -d '{"content": "hello"}'

# 查看状态
cyberclaw status

# 检查 Gateway 进程
python check_gateway_status.py
```

---

**最后更新**: 2026-03-04
**版本**: 1.0 (方案 A + C 完整实现)
