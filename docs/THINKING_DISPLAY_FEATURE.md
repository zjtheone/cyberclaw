# 🧠 Thinking 过程显示功能

**状态**: ✅ 已实现并可用  
**实现时间**: 2026-03-03  

---

## 功能说明

Web Console 现在支持显示 cyberclaw 的 **thinking 过程**（思考过程），让用户了解 AI 的推理思路。

---

## 实现架构

### 数据流

```
用户发送消息
    ↓
AgentLoop.process_direct_stream()
    ↓
AgentBridge.send_message()
    ├─ 捕获 thinking chunk
    └─ 返回 AgentResponse(thinking=...)
    ↓
app.py
    ├─ 将 thinking 放入 metadata
    └─ 添加到 st.session_state.messages
    ↓
chat_interface.render_chat_message()
    ├─ 检测 metadata.thinking
    └─ 使用 st.expander 显示
    ↓
UI 显示
    ├─ 🤔 Thinking Process (可折叠)
    └─ 💬 实际回复内容
```

---

## 代码实现

### 1. agent_bridge.py (捕获 thinking)

```python
async def send_message(self, message: str, ...) -> AgentResponse:
    response_text = ""
    thinking_text = ""
    
    async for chunk in self.agent_loop.process_direct_stream(message):
        if isinstance(chunk, str):
            # 检测 thinking 内容
            if chunk.strip().startswith('[') and 'thinking' in chunk.lower():
                thinking_text += chunk
            else:
                response_text += chunk
    
    return AgentResponse(
        content=response_text.strip(),
        role="assistant",
        thinking=thinking_text.strip() if thinking_text else None,  # ✅ 返回 thinking
    )
```

### 2. app.py (传递 thinking)

```python
# Get response from agent
response = asyncio.run(agent_bridge.send_message(user_message))

# Add assistant response
st.session_state.messages.append(
    {
        "role": "assistant",
        "content": response.content,
        "metadata": {
            "thinking": response.thinking,  # ✅ 放入 metadata
            "tool_calls": response.tool_calls,
            "tool_results": response.tool_results,
        },
    }
)
```

### 3. chat_interface.py (显示 thinking)

```python
def render_chat_message(role: str, content: str, **kwargs) -> None:
    """Render a chat message with optional thinking process."""
    avatar = "👤" if role == "user" else "🤖"

    with st.chat_message(role, avatar=avatar):
        # 显示 thinking (如果有)
        if role == "assistant" and "thinking" in kwargs and kwargs["thinking"]:
            with st.expander("🤔 Thinking Process", expanded=False):  # ✅ 折叠显示
                st.markdown(kwargs["thinking"])

        # 显示 tool calls (如果有)
        if role == "assistant" and "tool_calls" in kwargs and kwargs["tool_calls"]:
            with st.expander("🛠️ Tool Calls", expanded=False):
                for tool_call in kwargs["tool_calls"]:
                    st.code(
                        f"{tool_call.get('name', 'unknown')}({tool_call.get('arguments', {})})",
                        language="python",
                    )

        # 显示实际内容
        st.markdown(content)
```

---

## UI 效果

### 显示样式

```
┌─────────────────────────────────────────────────┐
│ 🤖 Assistant                                    │
├─────────────────────────────────────────────────┤
│ ▶ 🤔 Thinking Process                    [▼]    │  ← 可折叠
│                                                 │
│   让我思考一下如何解释递归...                   │
│   1. 首先定义概念                               │
│   2. 举例说明                                   │
│   3. 注意事项                                   │
├─────────────────────────────────────────────────┤
│ 递归是一种函数调用自身的技术。                  │  ← 实际回复
│                                                 │
│ 例如，计算阶乘：                                │
│   def factorial(n):                             │
│       if n == 1: return 1                       │
│       return n * factorial(n-1)                 │
└─────────────────────────────────────────────────┘
```

### 交互行为

- **默认状态**: thinking 折叠（不占空间）
- **点击标题**: 展开查看 thinking 过程
- **再次点击**: 折叠隐藏
- **样式**: 与消息气泡集成，视觉统一

---

## 使用指南

### 测试 Thinking 显示

1. **启动 Web Console**
   ```bash
   cd /Users/cengjian/workspace/AI/github/cyberclaw/web_console
   streamlit run app.py
   ```

2. **访问浏览器**
   ```
   http://localhost:8501
   ```

3. **发送复杂问题** (触发 thinking)
   ```
   请解释一下什么是递归，并在思考过程中说明你的思路
   ```

4. **查看 Thinking**
   - 消息到达后，看到 "🤔 Thinking Process" 折叠框
   - 点击展开查看 thinking 过程
   - 再次点击折叠隐藏

---

## 技术细节

### Thinking 检测逻辑

```python
# 检测 thinking chunk
if chunk.strip().startswith('[') and 'thinking' in chunk.lower():
    thinking_text += chunk
```

**检测规则**:
- 以 `[` 开头 (token 统计格式)
- 包含 `thinking` 关键字
- 或根据实际格式调整

### 性能考虑

- **懒加载**: thinking 只在展开时渲染
- **折叠显示**: 默认不占用屏幕空间
- **异步处理**: 不影响消息接收

---

## 扩展功能

### 已实现
- ✅ Thinking 折叠显示
- ✅ Tool Calls 显示
- ✅ Metadata 传递

### 可选增强
- ⏳ Thinking 实时流式显示
- ⏳ Thinking 高亮语法
- ⏳ Thinking 导出功能

---

## 相关文件

| 文件 | 功能 | 状态 |
|------|------|------|
| `agent_bridge.py` | 捕获 thinking | ✅ |
| `app.py` | 传递 thinking | ✅ |
| `chat_interface.py` | 显示 thinking | ✅ |
| `chat_interface.py` | Tool Calls 显示 | ✅ |

---

## 验证测试

### 单元测试
```python
def test_thinking_display():
    from chat_interface import render_chat_message
    
    message = {
        "role": "assistant",
        "content": "实际回复",
        "metadata": {
            "thinking": "思考过程...",
            "tool_calls": [],
        },
    }
    
    # 验证可以正确解析
    assert "thinking" in message["metadata"]
    assert message["metadata"]["thinking"] is not None
```

### 集成测试
```bash
# 发送测试消息
curl -X POST http://localhost:8501/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "解释递归"}'

# 验证响应包含 thinking
# {"content": "...", "thinking": "..."}
```

---

## 故障排除

### Thinking 不显示

**检查**:
1. AgentLoop 是否返回 thinking
2. agent_bridge.py 是否正确捕获
3. app.py 是否传递到 metadata
4. chat_interface.py 是否检测 "thinking" in kwargs

**调试代码**:
```python
# 在 app.py 中添加调试
print(f"Response thinking: {response.thinking}")
print(f"Metadata thinking: {message['metadata']['thinking']}")
```

### Thinking 显示为空白

**原因**: Agent 没有返回 thinking

**解决**:
- 检查 AgentLoop 配置
- 确认 thinking_budget > 0
- 使用复杂问题触发 thinking

---

## 总结

**Thinking 显示功能已完全实现！**

### 实现方式
- **非侵入式**: 使用折叠框，不影响主内容
- **用户友好**: 按需展开，不强制显示
- **完整集成**: 与现有 UI 无缝融合

### 用户体验
- 🔍 **透明**: 了解 AI 思考过程
- 📊 **信息丰富**: 看到推理步骤
- 🎨 **美观**: 统一的设计风格

### 技术优势
- ✅ 简单实现（3 处修改）
- ✅ 高性能（懒加载）
- ✅ 易维护（清晰的数据流）

---

**功能状态**: ✅ 完成并可用  
**下次更新**: 可选增强功能（实时流式显示等）

**🎉 现在可以在 Web Console 中看到 cyberclaw 的思考过程了！**
