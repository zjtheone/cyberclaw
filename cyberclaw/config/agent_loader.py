"""Agent configuration loader for multi-agent support."""

from pathlib import Path
from loguru import logger

from cyberclaw.config.schema import AgentConfig, AgentsConfig, Config


class AgentConfigLoader:
    """Loads and manages agent configurations.

    This class provides methods to:
    - Get agent configuration by ID
    - Resolve workspace and agent directory paths
    - Check if an agent exists
    - List available agents
    """

    def __init__(self, config: Config):
        """
        Initialize the agent config loader.

        Args:
            config: Root configuration object
        """
        self.config = config
        self._agents_config: AgentsConfig = getattr(config, "agents", AgentsConfig())
        self._cache: dict[str, AgentConfig] = {}

    def get_agent(self, agent_id: str) -> AgentConfig:
        """
        Get agent configuration by ID.

        Falls back to defaults if agent is not explicitly configured.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentConfig object

        Examples:
            >>> loader.get_agent("main")
            AgentConfig(id="main", workspace=Path(...), ...)

            >>> loader.get_agent("nonexistent")
            AgentConfig(id="nonexistent", ...)  # from defaults
        """
        if agent_id in self._cache:
            return self._cache[agent_id]

        agent = self._agents_config.get_agent(agent_id)
        self._cache[agent_id] = agent
        return agent

    def has_agent(self, agent_id: str) -> bool:
        """
        Check if an agent is explicitly configured.

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent exists in config list
        """
        return self._agents_config.has_agent(agent_id)

    def list_agents(self) -> list[AgentConfig]:
        """
        Get list of all configured agents.

        Returns:
            List of AgentConfig objects
        """
        return self._agents_config.list.copy()

    def list_agent_ids(self) -> list[str]:
        """
        Get list of all configured agent IDs.

        Returns:
            List of agent ID strings
        """
        return self._agents_config.list_agent_ids()

    def resolve_workspace(self, agent: AgentConfig | str) -> Path:
        """
        Resolve workspace path for an agent.

        Args:
            agent: AgentConfig object or agent ID string

        Returns:
            Resolved workspace Path
        """
        if isinstance(agent, str):
            agent = self.get_agent(agent)
        return agent.get_workspace_path()

    def resolve_agent_dir(self, agent: AgentConfig | str) -> Path:
        """
        Resolve agent directory path for an agent.

        The agent directory stores:
        - Auth profiles
        - Model registry
        - Per-agent configuration

        Args:
            agent: AgentConfig object or agent ID string

        Returns:
            Resolved agent directory Path
        """
        if isinstance(agent, str):
            agent = self.get_agent(agent)
        return agent.get_agent_dir_path()

    def get_default_agent_id(self) -> str:
        """
        Get the default agent ID.

        Returns:
            Default agent ID ("main" if configured, otherwise "default")
        """
        if self._agents_config.list:
            # Return first configured agent
            return self._agents_config.list[0].id
        return "default"

    def ensure_agent_dirs(self, agent_id: str) -> None:
        """
        Ensure agent directories exist.

        Creates workspace and agent directories if they don't exist.

        Args:
            agent_id: Agent identifier
        """
        agent = self.get_agent(agent_id)
        workspace = agent.get_workspace_path()
        agent_dir = agent.get_agent_dir_path()

        # Create directories
        workspace.mkdir(parents=True, exist_ok=True)
        agent_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "Ensured agent directories for {}: workspace={}, agent_dir={}",
            agent_id,
            workspace,
            agent_dir,
        )

    def get_subagent_config(self, agent_id: str) -> "SubagentConfig":
        """
        Get subagent configuration for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            SubagentConfig object
        """
        agent = self.get_agent(agent_id)
        return agent.subagents

    def get_a2a_policy(self) -> "AgentToAgentPolicy":
        """
        Get Agent-to-Agent communication policy.

        Returns:
            AgentToAgentPolicy object
        """
        return self.config.tools.agent_to_agent

    def get_session_visibility(self) -> "SessionVisibilityPolicy":
        """
        Get session visibility policy.

        Returns:
            SessionVisibilityPolicy object
        """
        return self.config.tools.sessions


def create_agent_config_loader(config: Config) -> AgentConfigLoader:
    """
    Factory function to create an AgentConfigLoader.

    Args:
        config: Root configuration object

    Returns:
        AgentConfigLoader instance
    """
    return AgentConfigLoader(config)


# Convenience functions for common operations
def get_default_agent_workspace(config: Config) -> Path:
    """Get default agent workspace path."""
    loader = create_agent_config_loader(config)
    return loader.resolve_workspace(loader.get_default_agent_id())


def get_agent_workspace(config: Config, agent_id: str) -> Path:
    """Get workspace path for a specific agent."""
    loader = create_agent_config_loader(config)
    return loader.resolve_workspace(agent_id)
