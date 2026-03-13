"""Agent-to-Agent policy engine for controlling inter-agent communication."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cyberclaw.config.schema import AgentToAgentPolicy, SessionVisibilityPolicy, RateLimitPolicy
    IN_DENYLIST = "in_denylist"


class PolicyCheckResult(Enum):
    """Result of a policy check."""

    ALLOWED = "allowed"
    DENIED = "denied"
    DISABLED = "disabled"
    DEPTH_EXCEEDED = "depth_exceeded"
    NOT_IN_ALLOWLIST = "not_in_allowlist"
    IN_DENYLIST = "in_denylist"


@dataclass
class PolicyDecision:
    """Decision from policy check."""

    result: PolicyCheckResult
    message: str
    details: dict | None = None

    @property
    def is_allowed(self) -> bool:
        """Check if the action is allowed."""
        return self.result == PolicyCheckResult.ALLOWED

    @property
    def is_denied(self) -> bool:
        """Check if the action is denied."""
        return self.result in (
            PolicyCheckResult.DENIED,
            PolicyCheckResult.DISABLED,
            PolicyCheckResult.DEPTH_EXCEEDED,
            PolicyCheckResult.NOT_IN_ALLOWLIST,
            PolicyCheckResult.IN_DENYLIST,
        )


class AgentToAgentPolicyEngine:
    """Engine for checking Agent-to-Agent communication policies.

    This engine enforces:
    - A2A enabled/disabled status
    - Allowlist/denylist checks
    - Spawn depth limits
    - Ping-pong turn limits
    """

    def __init__(self, policy: "AgentToAgentPolicy"):
        """
        Initialize the policy engine.

        Args:
            policy: AgentToAgentPolicy configuration
        """
        self.policy = policy
        
        # Rate limiting tracking
        from collections import defaultdict
        self._spawn_timestamps: defaultdict[str, list[float]] = defaultdict(list)
        self._concurrent_spawns: defaultdict[str, int] = defaultdict(int)
    def check_spawn_allowed(
        self,
        requester_agent_id: str,
        target_agent_id: str,
        current_depth: int = 0,
        max_depth: int | None = None,
    ) -> PolicyDecision:
        """
        Check if spawning a subagent is allowed.

        Args:
            requester_agent_id: Agent requesting the spawn
            target_agent_id: Target agent to spawn
            current_depth: Current spawn depth
            max_depth: Maximum allowed depth (overrides policy if set)

        Returns:
            PolicyDecision with result and message
        """
        # Check if A2A is enabled
        if not self.policy.enabled:
            # Allow same-agent spawn even if A2A is disabled
            if requester_agent_id == target_agent_id:
                return PolicyDecision(
                    result=PolicyCheckResult.ALLOWED,
                    message="Same-agent spawn allowed",
                )
            return PolicyDecision(
                result=PolicyCheckResult.DISABLED,
                message="Agent-to-agent spawning is disabled. "
                f"Set tools.agent_to_agent.enabled=true to allow cross-agent spawns.",
                details={"requester": requester_agent_id, "target": target_agent_id},
            )

        # Check denylist
        if target_agent_id in self.policy.deny:
            return PolicyDecision(
                result=PolicyCheckResult.IN_DENYLIST,
                message=f"Agent '{target_agent_id}' is in the deny list",
                details={"target": target_agent_id},
            )

        if requester_agent_id in self.policy.deny:
            return PolicyDecision(
                result=PolicyCheckResult.IN_DENYLIST,
                message=f"Requester agent '{requester_agent_id}' is in the deny list",
                details={"requester": requester_agent_id},
            )

        # Check allowlist
        if "*" not in self.policy.allow:
            if target_agent_id not in self.policy.allow:
                return PolicyDecision(
                    result=PolicyCheckResult.NOT_IN_ALLOWLIST,
                    message=f"Agent '{target_agent_id}' is not in the allow list",
                    details={"target": target_agent_id, "allow": self.policy.allow},
                )
            if requester_agent_id not in self.policy.allow:
                return PolicyDecision(
                    result=PolicyCheckResult.NOT_IN_ALLOWLIST,
                    message=f"Requester agent '{requester_agent_id}' is not in the allow list",
                    details={"requester": requester_agent_id, "allow": self.policy.allow},
                )

        # Check spawn depth
        effective_max_depth = (
            max_depth if max_depth is not None else self.policy.max_ping_pong_turns
        )
        if current_depth >= effective_max_depth:
            return PolicyDecision(
                result=PolicyCheckResult.DEPTH_EXCEEDED,
                message=f"Maximum spawn depth ({effective_max_depth}) reached",
                details={"current_depth": current_depth, "max_depth": effective_max_depth},
            )

        return PolicyDecision(
            result=PolicyCheckResult.ALLOWED,
            message=f"Spawn allowed: {requester_agent_id} → {target_agent_id}",
            details={
                "requester": requester_agent_id,
                "target": target_agent_id,
                "depth": current_depth,
            },
        )
    
    def check_rate_limit(
        self,
        agent_id: str,
        max_spawns_per_minute: int = 10,
        max_concurrent: int = 8,
    ) -> PolicyDecision:
        """检查 rate limit 是否允许 spawn。
        
        Args:
            agent_id: Agent 标识
            max_spawns_per_minute: 每分钟最大 spawn 数
            max_concurrent: 最大并发 spawn 数
        
        Returns:
            PolicyDecision
        """
        import time
        
        current_time = time.time()
        one_minute_ago = current_time - 60
        
        # Clean old timestamps
        timestamps = self._spawn_timestamps[agent_id]
        self._spawn_timestamps[agent_id] = [t for t in timestamps if t > one_minute_ago]
        
        # Check spawns per minute
        if len(self._spawn_timestamps[agent_id]) >= max_spawns_per_minute:
            return PolicyDecision(
                result=PolicyCheckResult.DENIED,
                message=f"Rate limit exceeded: {len(self._spawn_timestamps[agent_id])} spawns in last minute (limit: {max_spawns_per_minute})",
                details={
                    "agent_id": agent_id,
                    "spawns_last_minute": len(self._spawn_timestamps[agent_id]),
                    "limit": max_spawns_per_minute,
                },
            )
        
        # Check concurrent spawns
        if self._concurrent_spawns[agent_id] >= max_concurrent:
            return PolicyDecision(
                result=PolicyCheckResult.DENIED,
                message=f"Concurrent spawn limit exceeded: {self._concurrent_spawns[agent_id]} active (limit: {max_concurrent})",
                details={
                    "agent_id": agent_id,
                    "concurrent_spawns": self._concurrent_spawns[agent_id],
                    "limit": max_concurrent,
                },
            )
        
        return PolicyDecision(
            result=PolicyCheckResult.ALLOWED,
            message="Rate limit check passed",
        )
    
    def record_spawn(self, agent_id: str) -> None:
        """记录一次 spawn 事件。"""
        import time
        self._spawn_timestamps[agent_id].append(time.time())
        self._concurrent_spawns[agent_id] += 1
    
    def record_spawn_complete(self, agent_id: str) -> None:
        """记录 spawn 完成。"""
        if self._concurrent_spawns[agent_id] > 0:
            self._concurrent_spawns[agent_id] -= 1

    def check_ping_pong_allowed(
        self,
        requester_agent_id: str,
        target_agent_id: str,
        current_turn: int,
    ) -> PolicyDecision:
        """
        Check if a ping-pong turn is allowed.

        Args:
            requester_agent_id: Agent that initiated the conversation
            target_agent_id: Current target agent
            current_turn: Current turn number (1-indexed)

        Returns:
            PolicyDecision with result and message
        """
        if not self.policy.enabled:
            return PolicyDecision(
                result=PolicyCheckResult.DISABLED,
                message="Agent-to-agent communication is disabled",
            )

        if current_turn > self.policy.max_ping_pong_turns:
            return PolicyDecision(
                result=PolicyCheckResult.DEPTH_EXCEEDED,
                message=f"Maximum ping-pong turns ({self.policy.max_ping_pong_turns}) reached",
                details={
                    "current_turn": current_turn,
                    "max_turns": self.policy.max_ping_pong_turns,
                },
            )

        # Reuse spawn allowed check for basic permissions
        spawn_result = self.check_spawn_allowed(
            requester_agent_id,
            target_agent_id,
            current_depth=current_turn,
        )

        if spawn_result.is_denied:
            return PolicyDecision(
                result=spawn_result.result,
                message=spawn_result.message,
            )

        return PolicyDecision(
            result=PolicyCheckResult.ALLOWED,
            message=f"Ping-pong turn {current_turn} allowed",
            details={"turn": current_turn, "max_turns": self.policy.max_ping_pong_turns},
        )

    def get_max_spawn_depth(self) -> int:
        """Get the maximum spawn depth from policy."""
        return self.policy.max_ping_pong_turns

    def is_enabled(self) -> bool:
        """Check if A2A communication is enabled."""
        return self.policy.enabled


class SessionVisibilityEngine:
    """Engine for checking session visibility policies.

    This engine enforces:
    - Session visibility levels (self, tree, agent, all)
    - Parent-child session relationships
    """

    def __init__(self, policy: "SessionVisibilityPolicy"):
        """
        Initialize the visibility engine.

        Args:
            policy: SessionVisibilityPolicy configuration
        """
        self.policy = policy

    def can_see_session(
        self,
        requester_agent_id: str,
        requester_session_key: str,
        target_session_key: str,
        target_agent_id: str,
        parent_session_key: str | None = None,
    ) -> PolicyDecision:
        """
        Check if a session is visible to the requester.

        Args:
            requester_agent_id: Agent requesting access
            requester_session_key: Requester's session key
            target_session_key: Target session to check
            target_agent_id: Target session's agent ID
            parent_session_key: Parent session key (for tree visibility)

        Returns:
            PolicyDecision with result and message
        """
        if self.policy.is_all:
            return PolicyDecision(
                result=PolicyCheckResult.ALLOWED,
                message="Session visibility: all (no restrictions)",
            )

        if self.policy.is_self:
            if requester_session_key == target_session_key:
                return PolicyDecision(
                    result=PolicyCheckResult.ALLOWED,
                    message="Session visibility: self (same session)",
                )
            return PolicyDecision(
                result=PolicyCheckResult.DENIED,
                message="Session visibility: self (different session)",
                details={"requester": requester_session_key, "target": target_session_key},
            )

        if self.policy.is_agent:
            if requester_agent_id == target_agent_id:
                return PolicyDecision(
                    result=PolicyCheckResult.ALLOWED,
                    message="Session visibility: agent (same agent)",
                )
            return PolicyDecision(
                result=PolicyCheckResult.DENIED,
                message="Session visibility: agent (different agent)",
                details={"requester_agent": requester_agent_id, "target_agent": target_agent_id},
            )

        if self.policy.is_tree:
            # Tree visibility: can see own session and spawned children
            if requester_session_key == target_session_key:
                return PolicyDecision(
                    result=PolicyCheckResult.ALLOWED,
                    message="Session visibility: tree (same session)",
                )

            # Check if target was spawned by requester
            if parent_session_key == requester_session_key:
                return PolicyDecision(
                    result=PolicyCheckResult.ALLOWED,
                    message="Session visibility: tree (child session)",
                    details={"parent": requester_session_key, "child": target_session_key},
                )

            return PolicyDecision(
                result=PolicyCheckResult.DENIED,
                message="Session visibility: tree (not in spawn tree)",
                details={
                    "requester": requester_session_key,
                    "target": target_session_key,
                    "parent": parent_session_key,
                },
            )

        # Default: deny
        return PolicyDecision(
            result=PolicyCheckResult.DENIED,
            message=f"Unknown visibility policy: {self.policy.visibility}",
        )

    def get_visibility_level(self) -> str:
        """Get the current visibility level."""
        return self.policy.visibility


def create_policy_engine(policy: "AgentToAgentPolicy") -> AgentToAgentPolicyEngine:
    """
    Factory function to create a policy engine.

    Args:
        policy: AgentToAgentPolicy configuration

    Returns:
        AgentToAgentPolicyEngine instance
    """
    return AgentToAgentPolicyEngine(policy)


def create_visibility_engine(policy: "SessionVisibilityPolicy") -> SessionVisibilityEngine:
    """
    Factory function to create a visibility engine.

    Args:
        policy: SessionVisibilityPolicy configuration

    Returns:
        SessionVisibilityEngine instance
    """
    return SessionVisibilityEngine(policy)
