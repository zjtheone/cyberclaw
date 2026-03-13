# Agent Team 日志增强

## 📊 日志改进

### 改进前
```
2026-03-04 22:07:15.270 | DEBUG | cyberclaw.gateway.manager:_handle_message - Routing message from cli:interactive to agent orchestrator
2026-03-04 22:07:15.270 | INFO | cyberclaw.agent.loop:_process_message - Processing message from cli:user: 设计一个完整的图书管理系统
```

**问题**: 看不出具体是哪个 agent 在处理

---

### 改进后
```
2026-03-04 22:07:15.270 | INFO | cyberclaw.gateway.manager - 
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 设计一个完整的图书管理系统...

2026-03-04 22:07:15.270 | INFO | cyberclaw.agent.loop - 
🤖 [orchestrator] Processing: 设计一个完整的图书管理系统...
```

**改进**:
- ✅ 使用 emoji 图标区分日志类型
- ✅ 大写显示 agent_id（路由日志）
- ✅ 显示消息内容预览
- ✅ 格式统一，易于扫描

---

## 🎯 日志类型说明

| 图标 | 说明 | 示例 |
|------|------|------|
| 📥 | 消息路由 | `[ORCHESTRATOR] Routing message` |
| 🤖 | 消息处理 | `[orchestrator] Processing` |
| 🔄 | 工具调用 | `Tool call: create_implementation_plan` |
| ✅ | 任务完成 | `Agent xxx completed task` |

---

## 📝 查看特定 Agent 日志

```bash
# 只看 orchestrator 的日志
cyberclaw gateway --multi -i 2>&1 | grep -i "\[orchestrator\]"

# 只看 coding agent 的日志
cyberclaw gateway --multi -i 2>&1 | grep -i "\[coding\]"

# 只看消息路由
cyberclaw gateway --multi -i 2>&1 | grep "📥"

# 只看工具调用
cyberclaw gateway --multi -i 2>&1 | grep "Tool call"
```

---

## 🎨 日志示例

### 完整工作流

```
📥 [ORCHESTRATOR] Routing message from cli:interactive
   Content: 帮我设计一个图书管理系统...

🤖 [orchestrator] Processing: 帮我设计一个图书管理系统...

🔄 Tool call: create_implementation_plan({...})
🔄 Tool call: read_file({...})
🔄 Tool call: shell({...})

✅ Agent orchestrator completed task in 15.2s
```

### 多 Agent 协作

```
📥 [CODING] Routing message from cli:interactive
   Content: 实现用户登录功能...

🤖 [coding] Processing: 实现用户登录功能...

📥 [REVIEWER] Routing message from cli:interactive
   Content: 审查刚才的代码...

🤖 [reviewer] Processing: 审查刚才的代码...
```

---

## 🔍 调试技巧

### 1. 实时日志过滤
```bash
cyberclaw gateway --multi -i 2>&1 | \
  grep -E "📥|🤖|Tool call" | \
  grep -v "DEBUG"
```

### 2. 只查看错误
```bash
cyberclaw gateway --multi -i 2>&1 | grep -i "error\|failed\|exception"
```

### 3. 查看特定会话
```bash
cyberclaw gateway --multi -i 2>&1 | grep "interactive"
```

---

## 📋 相关文档

- `GATEWAY_INTERACTIVE_USAGE.md` - Gateway 使用指南
- `AGENT_TEAM_CONFIG.md` - Agent Team 配置
- `AGENT_TEAM_USAGE_GUIDE.md` - 完整使用指南

---

**最后更新**: 2026-03-04
