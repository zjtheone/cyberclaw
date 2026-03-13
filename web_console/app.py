"""Web Console - Streamlit interface for cyberclaw."""

import streamlit as st
import asyncio
from pathlib import Path
from typing import Optional

from config import get_config, WebConsoleConfig
from styles import get_custom_css, get_theme_config
from session_manager import SessionManager
from agent_bridge import AgentBridge, AgentResponse
from chat_interface import render_chat_message, render_chat_input
from subagent_monitor import render_subagent_monitor

# Page configuration
st.set_page_config(
    page_title="cyberclaw Web Console",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom CSS
st.markdown(get_custom_css(), unsafe_allow_html=True)


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "session_manager" not in st.session_state:
        config = get_config()
        st.session_state.session_manager = SessionManager(
            session_dir=config.session_dir,
            max_sessions=config.max_sessions,
            session_timeout_hours=config.session_timeout_hours,
        )

    if "agent_bridge" not in st.session_state:
        st.session_state.agent_bridge = AgentBridge()
        # Initialize agent bridge
        config = get_config()
        st.session_state.agent_bridge.initialize()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False


def render_sidebar() -> None:
    """Render the sidebar."""
    with st.sidebar:
        st.title("🤖 cyberclaw")
        st.markdown("Web Console")

        st.divider()

        # Session management
        st.markdown("### 💬 Sessions")

        session_manager = st.session_state.session_manager
        sessions = session_manager.list_sessions()

        # New session button
        if st.button("➕ New Session", use_container_width=True):
            session_manager.create_session()
            st.session_state.messages = []
            st.rerun()

        # Session list
        if sessions:
            st.divider()
            for session in sessions:
                session_name = session.metadata.get("name", f"Session {session.session_id}")
                message_count = len(session.messages)

                # Create a clickable session item
                if st.button(
                    f"💬 {session_name} ({message_count})",
                    key=f"session_{session.session_id}",
                    use_container_width=True,
                ):
                    session_manager.set_current_session(session.session_id)
                    st.session_state.messages = session.messages.copy()
                    st.rerun()

        st.divider()

        # Agent status
        st.markdown("### 📊 Agent Status")
        agent_bridge = st.session_state.agent_bridge
        status = agent_bridge.get_status()

        if status.get("initialized"):
            st.success("✅ Agent Ready")
            st.info(f"Workspace: {status.get('workspace', 'N/A')}")
        else:
            st.warning("⚠️ Agent not initialized")
            if status.get('error'):
                st.error(f"Error: {status['error']}")

        st.divider()

        # Settings
        st.markdown("### ⚙️ Settings")

        config = get_config()

        # Theme selector
        theme = st.selectbox(
            "Theme",
            ["dark", "light"],
            index=0 if config.default_theme == "dark" else 1,
        )

        # Clear all sessions
        if st.button("🗑️ Clear All Sessions", use_container_width=True):
            for session in sessions:
                session_manager.delete_session(session.session_id)
            st.session_state.messages = []
            st.success("All sessions cleared!")
            st.rerun()

        # Footer
        st.divider()
        st.markdown(
            """
            <div style="text-align: center; color: gray; font-size: 0.8em;">
                cyberclaw Web Console v0.1.0
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_main_chat() -> None:
    """Render the main chat interface."""
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    # Display chat messages
    for i, message in enumerate(st.session_state.messages):
        render_chat_message(
            message["role"],
            message["content"],
            **message.get("metadata", {}),
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Chat input
    if prompt := render_chat_input(
        disabled=st.session_state.is_processing,
    ):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.is_processing = True

        # Save to session
        session_manager = st.session_state.session_manager
        current_session = session_manager.get_current_session()
        if current_session:
            current_session.add_message("user", prompt)
        else:
            current_session = session_manager.create_session()
            current_session.add_message("user", prompt)
            st.session_state.messages = current_session.messages.copy()

        st.rerun()


def process_agent_response() -> None:
    """Process the agent response for the last user message."""
    if not st.session_state.messages:
        return

    last_message = st.session_state.messages[-1]
    if last_message["role"] != "user":
        return

    user_message = last_message["content"]
    agent_bridge = st.session_state.agent_bridge

    # Get response from agent
    with st.spinner("cyberclaw is thinking..."):
        response = asyncio.run(agent_bridge.send_message(user_message))

    # Add assistant response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response.content,
            "metadata": {
                "thinking": response.thinking,
                "tool_calls": response.tool_calls,
                "tool_results": response.tool_results,
            },
        }
    )

    # Save to session
    session_manager = st.session_state.session_manager
    current_session = session_manager.get_current_session()
    if current_session:
        current_session.add_message(
            "assistant",
            response.content,
            thinking=response.thinking,
            tool_calls=response.tool_calls,
        )
        session_manager.save_all_sessions()

    st.session_state.is_processing = False
    st.rerun()


def render_subagent_panel() -> None:
    """Render the subagent monitor panel."""
    config = get_config()

    if config.show_subagent_monitor:
        with st.expander("🚀 Subagent Monitor", expanded=False):
            agent_bridge = st.session_state.agent_bridge
            render_subagent_monitor(agent_bridge)


def main() -> None:
    """Main application entry point."""
    # Initialize session state
    init_session_state()

    # Render sidebar
    render_sidebar()

    # Main chat area
    st.title("💬 Chat")

    # Process agent response if needed
    if st.session_state.is_processing and st.session_state.messages:
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "user":
            process_agent_response()
            return

    # Render chat interface
    render_main_chat()

    # Subagent monitor
    render_subagent_panel()

    # Auto-save sessions periodically
    session_manager = st.session_state.session_manager
    session_manager.save_all_sessions()


if __name__ == "__main__":
    main()
