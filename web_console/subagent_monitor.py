"""Subagent monitoring panel for Web Console."""

import streamlit as st
from typing import Any, Optional
from datetime import datetime


def render_subagent_card(agent_id: str, agent_info: dict[str, Any]) -> None:
    """Render a single subagent card."""
    status = agent_info.get("status", "unknown")
    task = agent_info.get("task", "Unknown task")
    label = agent_info.get("label", "")
    created_at = agent_info.get("created_at", "")
    progress = agent_info.get("progress", 0)

    # Status badge
    status_colors = {
        "running": "🟢",
        "completed": "✅",
        "failed": "❌",
        "pending": "⏳",
        "cancelled": "⚪",
    }
    status_icon = status_colors.get(status.lower(), "⚪")

    with st.container():
        st.markdown(f"#### {status_icon} Subagent `{agent_id[:8]}`")

        col1, col2 = st.columns([3, 1])

        with col1:
            if label:
                st.markdown(f"**Task:** {label}")
            else:
                st.markdown(f"**Task:** {task[:100]}{'...' if len(task) > 100 else ''}")

            if created_at:
                try:
                    created_time = datetime.fromisoformat(created_at)
                    st.markdown(f"**Started:** {created_time.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception:
                    pass

        with col2:
            st.metric("Status", status.capitalize())

        # Progress bar
        if progress > 0:
            st.progress(min(progress / 100, 1.0))

        # Expandable details
        with st.expander("📋 Details", expanded=False):
            st.json(agent_info)


def render_subagent_monitor(agent_bridge: Optional[Any] = None) -> None:
    """Render the subagent monitor panel."""
    st.markdown("### 🚀 Subagent Monitor")

    # Get subagent status
    subagents = {}

    if agent_bridge and agent_bridge._initialized:
        try:
            status = agent_bridge.get_status()
            if "active_subagents" in status:
                # Try to get detailed subagent info
                if hasattr(agent_bridge.agent_loop, "subagents"):
                    subagents = agent_bridge.agent_loop.subagents
        except Exception as e:
            st.error(f"Failed to get subagent status: {e}")

    if not subagents:
        st.info("No active subagents. Subagents will appear here when spawned during task execution.")
        return

    # Display subagent count
    st.metric("Active Subagents", len(subagents))

    # Render each subagent
    for agent_id, agent_info in subagents.items():
        if isinstance(agent_info, dict):
            render_subagent_card(agent_id, agent_info)
        else:
            # Handle different formats
            render_subagent_card(
                agent_id,
                {
                    "status": getattr(agent_info, "status", "unknown"),
                    "task": getattr(agent_info, "task", ""),
                    "label": getattr(agent_info, "label", ""),
                },
            )

        st.divider()


def render_subagent_history(history: list[dict[str, Any]]) -> None:
    """Render subagent execution history."""
    st.markdown("### 📜 Subagent History")

    if not history:
        st.info("No subagent history available.")
        return

    # Display as a table
    df_data = []
    for entry in history:
        df_data.append(
            {
                "Agent ID": entry.get("agent_id", "")[:8],
                "Task": entry.get("task", "")[:50],
                "Status": entry.get("status", "unknown"),
                "Duration": entry.get("duration", "N/A"),
            }
        )

    st.table(df_data)


def render_subagent_metrics(metrics: dict[str, Any]) -> None:
    """Render subagent performance metrics."""
    st.markdown("### 📊 Subagent Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Spawned", metrics.get("total_spawned", 0))

    with col2:
        st.metric("Completed", metrics.get("completed", 0))

    with col3:
        st.metric("Failed", metrics.get("failed", 0))

    with col4:
        success_rate = (
            metrics.get("completed", 0) / metrics.get("total_spawned", 1) * 100
            if metrics.get("total_spawned", 0) > 0
            else 0
        )
        st.metric("Success Rate", f"{success_rate:.1f}%")


def render_realtime_updates() -> None:
    """Render realtime update placeholder."""
    # This would be used with st.empty() for realtime updates
    return st.empty()
