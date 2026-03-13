"""Team manager for agent team operations.

Provides CRUD operations and queries for agent teams.
"""

from cyberclaw.config.schema import AgentsConfig, TeamConfig, AgentConfig


class TeamManager:
    """Team 管理：查询、验证、操作 team。

    功能：
    - 查询 team 配置
    - 获取 team 成员列表
    - 验证 team 配置有效性
    """

    def __init__(self, config: AgentsConfig):
        self.config = config

    def get_team(self, name: str) -> TeamConfig | None:
        """Get team config by name.

        Args:
            name: Team name

        Returns:
            TeamConfig if found, None otherwise
        """
        return self.config.get_team(name)

    def list_teams(self) -> list[TeamConfig]:
        """Get list of configured teams.

        Returns:
            List of TeamConfig objects
        """
        return self.config.list_teams()

    def get_team_members(self, name: str) -> list[AgentConfig]:
        """Get agent configs for all team members.

        Args:
            name: Team name

        Returns:
            List of AgentConfig for team members
        """
        team = self.get_team(name)
        if not team:
            return []

        members = []
        for member_id in team.members:
            agent_config = self.config.get_agent(member_id)
            members.append(agent_config)

        return members

    def validate_team(self, name: str) -> list[str]:
        """Validate team configuration.

        Args:
            name: Team name

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        team = self.get_team(name)
        if not team:
            return [f"Team '{name}' not found"]

        # Check if team has members
        if not team.members:
            errors.append(f"Team '{name}' has no members")

        # Check if all members exist
        for member_id in team.members:
            if not self.config.has_agent(member_id):
                errors.append(f"Team member '{member_id}' is not configured")

        # Check if leader is a member
        if team.leader and team.leader not in team.members:
            errors.append(f"Team leader '{team.leader}' is not a team member")

        # Validate strategy
        valid_strategies = ["parallel", "sequential", "leader_delegate"]
        if team.strategy not in valid_strategies:
            errors.append(
                f"Invalid strategy '{team.strategy}'. Must be one of: {', '.join(valid_strategies)}"
            )

        return errors

    def get_team_summary(self, name: str) -> dict:
        """Get team summary information.

        Args:
            name: Team name

        Returns:
            Dict with team summary
        """
        team = self.get_team(name)
        if not team:
            return {"error": f"Team '{name}' not found"}

        members = self.get_team_members(name)
        validation_errors = self.validate_team(name)

        return {
            "name": team.name,
            "members": team.members,
            "member_count": len(team.members),
            "leader": team.leader,
            "strategy": team.strategy,
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "member_configs": [
                {
                    "id": m.id,
                    "model": m.model,
                    "workspace": str(m.workspace) if m.workspace else None,
                }
                for m in members
            ],
        }

    def get_all_teams_summary(self) -> list[dict]:
        """Get summary of all teams.

        Returns:
            List of team summaries
        """
        return [self.get_team_summary(team.name) for team in self.list_teams()]
