"""Configuration management for Web Console."""

import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class WebConsoleConfig:
    """Web Console configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8501
    enable_cors: bool = True

    # cyberclaw integration
    workspace: Path = field(default_factory=lambda: Path.home() / ".cyberclaw" / "workspace")
    config_file: Optional[Path] = None

    # LLM settings (can override cyberclaw config)
    model: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7

    # Session settings
    session_dir: Optional[Path] = None
    max_sessions: int = 100
    session_timeout_hours: int = 24

    # UI settings
    default_theme: str = "dark"  # "dark" or "light"
    show_subagent_monitor: bool = True
    enable_file_upload: bool = True
    max_message_length: int = 10000

    # Performance
    enable_caching: bool = True
    auto_refresh_interval: int = 5  # seconds

    @classmethod
    def from_env(cls) -> "WebConsoleConfig":
        """Create config from environment variables."""
        config = cls()

        # Server settings
        if host := os.getenv("WEB_CONSOLE_HOST"):
            config.host = host
        if port := os.getenv("WEB_CONSOLE_PORT"):
            config.port = int(port)

        # cyberclaw settings
        if workspace := os.getenv("CYBERCLAW_WORKSPACE"):
            config.workspace = Path(workspace)
        if config_file := os.getenv("CYBERCLAW_CONFIG"):
            config.config_file = Path(config_file)

        # LLM settings
        if model := os.getenv("WEB_CONSOLE_MODEL"):
            config.model = model
        if max_tokens := os.getenv("WEB_CONSOLE_MAX_TOKENS"):
            config.max_tokens = int(max_tokens)
        if temperature := os.getenv("WEB_CONSOLE_TEMPERATURE"):
            config.temperature = float(temperature)

        # Session settings
        if session_dir := os.getenv("WEB_CONSOLE_SESSION_DIR"):
            config.session_dir = Path(session_dir)
        if max_sessions := os.getenv("WEB_CONSOLE_MAX_SESSIONS"):
            config.max_sessions = int(max_sessions)

        # UI settings
        if theme := os.getenv("WEB_CONSOLE_THEME"):
            config.default_theme = theme
        if show_monitor := os.getenv("WEB_CONSOLE_SHOW_MONITOR"):
            config.show_subagent_monitor = show_monitor.lower() == "true"

        return config

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "WebConsoleConfig":
        """Load config from file or environment."""
        config = cls.from_env()

        if config_path is None:
            config_path = Path.home() / ".cyberclaw" / "web_console.yaml"

        if config_path.exists():
            try:
                import yaml

                with open(config_path, "r") as f:
                    data = yaml.safe_load(f)
                    if data:
                        for key, value in data.items():
                            if hasattr(config, key) and value is not None:
                                setattr(config, key, value)
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")

        return config

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.workspace.exists():
            print(f"Warning: Workspace directory does not exist: {self.workspace}")
            self.workspace.mkdir(parents=True, exist_ok=True)

        if self.session_dir and not self.session_dir.exists():
            self.session_dir.mkdir(parents=True, exist_ok=True)

        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")

        if self.temperature < 0 or self.temperature > 2:
            raise ValueError(f"Temperature must be between 0 and 2, got: {self.temperature}")

        return True


# Global config instance
_config: Optional[WebConsoleConfig] = None


def get_config() -> WebConsoleConfig:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = WebConsoleConfig.load()
        _config.validate()
    return _config


def set_config(config: WebConsoleConfig) -> None:
    """Set global config instance."""
    global _config
    _config = config
