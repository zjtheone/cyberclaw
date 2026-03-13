# cyberclaw Web Console 🤖

A modern, Streamlit-based web interface for interacting with cyberclaw.

## Features

- 💬 **Chat Interface**: Clean, modern chat UI for interacting with cyberclaw
- 🔄 **Session Management**: Persistent chat sessions with automatic save/load
- 🚀 **Subagent Monitor**: Real-time monitoring of spawned subagents
- 🎨 **Customizable Themes**: Dark and light theme support
- 📊 **Agent Status**: View agent health and configuration
- 🛠️ **Tool Visualization**: See tool calls and results inline

## Quick Start

### 1. Install Dependencies

```bash
cd web_console
pip install -r requirements.txt
```

### 2. Configure (Optional)

Create a configuration file at `~/.cyberclaw/web_console.yaml`:

```yaml
# Server settings
host: 0.0.0.0
port: 8501

# cyberclaw workspace
workspace: /path/to/your/workspace

# UI settings
default_theme: dark
show_subagent_monitor: true
enable_file_upload: true

# Session settings
session_timeout_hours: 24
max_sessions: 100
```

Or use environment variables:

```bash
export WEB_CONSOLE_PORT=8501
export CYBERCLAW_WORKSPACE=/path/to/workspace
export WEB_CONSOLE_THEME=dark
```

### 3. Run the Console

```bash
streamlit run app.py
```

The console will open at `http://localhost:8501`

## Project Structure

```
web_console/
├── app.py                 # Main Streamlit application
├── config.py              # Configuration management
├── styles.py              # Custom CSS styles
├── session_manager.py     # Session persistence
├── agent_bridge.py        # cyberclaw integration
├── chat_interface.py      # Chat components
├── subagent_monitor.py    # Subagent monitoring
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Components

### `app.py` - Main Application

The entry point that orchestrates all components:
- Initializes session state
- Renders sidebar and main chat area
- Handles message processing
- Manages agent communication

### `config.py` - Configuration

Manages application settings with support for:
- File-based configuration (YAML)
- Environment variable overrides
- Default values and validation

### `session_manager.py` - Session Management

Handles chat session persistence:
- Create, load, and delete sessions
- Automatic cleanup of expired sessions
- JSON-based storage

### `agent_bridge.py` - Agent Integration

Bridges the web console with cyberclaw's AgentLoop:
- Send messages and receive responses
- Stream processing support
- Subagent spawning and monitoring

### `chat_interface.py` - Chat Components

Reusable UI components:
- Message rendering with avatars
- Tool call visualization
- File attachments
- Status indicators

### `subagent_monitor.py` - Subagent Monitor

Real-time subagent tracking:
- Active subagent cards
- Status badges and progress
- Execution history

## Usage

### Starting a New Session

1. Click "➕ New Session" in the sidebar
2. Start chatting!

### Switching Sessions

1. Click on any session in the sidebar
2. The chat history will load automatically

### Viewing Tool Calls

When cyberclaw uses tools:
1. Look for the "🛠️ Tool Calls" expander in assistant messages
2. Click to see tool names and arguments

### Monitoring Subagents

When subagents are spawned:
1. Expand the "🚀 Subagent Monitor" panel
2. View active subagents and their status

## Configuration Options

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| `host` | `WEB_CONSOLE_HOST` | `0.0.0.0` | Server bind address |
| `port` | `WEB_CONSOLE_PORT` | `8501` | Server port |
| `workspace` | `CYBERCLAW_WORKSPACE` | `~/.cyberclaw/workspace` | cyberclaw workspace path |
| `default_theme` | `WEB_CONSOLE_THEME` | `dark` | UI theme |
| `show_subagent_monitor` | `WEB_CONSOLE_SHOW_MONITOR` | `true` | Show subagent panel |
| `session_timeout_hours` | - | `24` | Session expiration |
| `max_sessions` | `WEB_CONSOLE_MAX_SESSIONS` | `100` | Max stored sessions |

## Development

### Running in Development Mode

```bash
streamlit run app.py --server.headless true --server.enableCORS false
```

### Custom Styling

Edit `styles.py` to customize the appearance. The CSS is injected at runtime.

### Adding New Components

1. Create a new module (e.g., `metrics.py`)
2. Import in `app.py`
3. Add to the layout

## Troubleshooting

### Agent Not Initializing

Ensure cyberclaw is properly configured:
```bash
cyberclaw config show
```

### Session Data Not Persisting

Check that the session directory is writable:
```bash
ls -la ~/.cyberclaw/sessions
```

### Port Already in Use

Change the port in config or via environment:
```bash
export WEB_CONSOLE_PORT=8502
```

## License

MIT License - See cyberclaw main repository for details.

## Contributing

Contributions welcome! Please follow the cyberclaw contribution guidelines.
