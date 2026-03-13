"""Chat interface components for Web Console."""

import streamlit as st
from typing import Callable, Optional


def render_chat_message(role: str, content: str, **kwargs) -> None:
    """Render a single chat message."""
    avatar = "👤" if role == "user" else "🤖"

    with st.chat_message(role, avatar=avatar):
        if role == "assistant" and "thinking" in kwargs:
            with st.expander("🤔 Thinking Process", expanded=False):
                st.markdown(kwargs["thinking"])

        if role == "assistant" and "tool_calls" in kwargs and kwargs["tool_calls"]:
            with st.expander("🛠️ Tool Calls", expanded=False):
                for tool_call in kwargs["tool_calls"]:
                    st.code(
                        f"{tool_call.get('name', 'unknown')}({tool_call.get('arguments', {})})",
                        language="python",
                    )

        st.markdown(content)


def render_chat_input(
    key: str = "chat_input",
    placeholder: str = "Message cyberclaw...",
    on_submit: Optional[Callable] = None,
    disabled: bool = False,
) -> Optional[str]:
    """Render chat input field."""
    return st.chat_input(
        placeholder=placeholder,
        key=key,
        disabled=disabled,
    )


def render_message_actions(message_index: int) -> None:
    """Render action buttons for a message."""
    cols = st.columns([1, 1, 1, 4])

    with cols[0]:
        if st.button("📋 Copy", key=f"copy_{message_index}", use_container_width=True):
            st.toast("Message copied to clipboard")

    with cols[1]:
        if st.button("🔄 Regenerate", key=f"regen_{message_index}", use_container_width=True):
            st.toast("Regeneration not yet implemented")

    with cols[2]:
        if st.button("🗑️ Delete", key=f"delete_{message_index}", use_container_width=True):
            st.toast("Deletion not yet implemented")


def render_typing_indicator() -> None:
    """Render a typing indicator."""
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("cyberclaw is thinking..."):
            pass


def render_code_block(code: str, language: str = "python") -> None:
    """Render a code block with copy button."""
    st.code(code, language=language)


def render_file_attachment(file_path: str, file_type: str = "file") -> None:
    """Render a file attachment."""
    icon = "📄" if file_type == "file" else "🖼️" if file_type == "image" else "📊"

    with st.container():
        st.markdown(f"{icon} **Attached:** `{file_path}`")


def render_tool_result(tool_name: str, result: str, success: bool = True) -> None:
    """Render a tool execution result."""
    status = "✅" if success else "❌"

    with st.expander(f"{status} Tool: {tool_name}", expanded=False):
        if success:
            st.success("Tool executed successfully")
        else:
            st.error("Tool execution failed")

        st.code(result, language="json" if result.startswith("{") else None)


def render_subagent_spawn(task: str, agent_id: str) -> None:
    """Render a subagent spawn notification."""
    with st.container():
        st.info(f"🚀 **Subagent spawned** (`{agent_id[:8]}`): {task}")


def render_progress_tracker(current: int, total: int, label: str = "Progress") -> None:
    """Render a progress tracker."""
    progress = current / total if total > 0 else 0
    st.progress(progress, text=f"{label}: {current}/{total}")


def render_status_badge(status: str) -> str:
    """Render a status badge."""
    badges = {
        "running": "🟢",
        "completed": "✅",
        "failed": "❌",
        "pending": "⏳",
        "cancelled": "⚪",
    }
    return badges.get(status.lower(), "⚪")
