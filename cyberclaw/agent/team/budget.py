"""Token budget tracking and limiting for agents.

Provides token usage tracking with daily and per-task limits.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, Tuple
from collections import defaultdict


@dataclass
class TokenUsage:
    """Token usage record."""

    agent_id: str
    task_id: str
    input_tokens: int
    output_tokens: int
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class DailyBudget:
    """Daily token budget configuration."""

    limit: int = 0  # 0 = unlimited
    used: int = 0
    reset_date: date = field(default_factory=date.today)

    def is_new_day(self) -> bool:
        """Check if budget should be reset."""
        return date.today() > self.reset_date

    def reset_if_needed(self) -> None:
        """Reset budget if it's a new day."""
        if self.is_new_day():
            self.used = 0
            self.reset_date = date.today()

    def can_use(self, tokens: int) -> bool:
        """Check if tokens can be used within budget."""
        self.reset_if_needed()
        if self.limit == 0:
            return True
        return self.used + tokens <= self.limit

    def use(self, tokens: int) -> bool:
        """Use tokens from budget. Returns False if exceeded."""
        self.reset_if_needed()
        if self.limit > 0 and self.used + tokens > self.limit:
            return False
        self.used += tokens
        return True


class TokenBudgetTracker:
    """跟踪和限制 agent/subagent 的 token 使用量。

    功能：
    - 每日 token 限额追踪
    - 每任务 token 限额
    - 用量统计和报告
    """

    def __init__(
        self,
        daily_limit: int = 0,
        per_task_limit: int = 0,
    ):
        """初始化 token 预算追踪器。

        Args:
            daily_limit: 每日 token 限额 (0 = 无限)
            per_task_limit: 每任务 token 限额 (0 = 无限)
        """
        self.daily_limit = daily_limit
        self.per_task_limit = per_task_limit

        # 按 agent 追踪每日用量
        self._daily_budgets: Dict[str, DailyBudget] = defaultdict(DailyBudget)

        # 按任务追踪用量
        self._task_usage: Dict[str, int] = defaultdict(int)

        # 历史用量记录
        self._history: list[TokenUsage] = []

    def record_usage(
        self,
        agent_id: str,
        task_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """记录 token 使用量。

        Args:
            agent_id: Agent 标识
            task_id: 任务标识
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
        """
        total = input_tokens + output_tokens

        # 记录到历史
        usage = TokenUsage(
            agent_id=agent_id,
            task_id=task_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self._history.append(usage)

        # 更新每日用量
        self._daily_budgets[agent_id].use(total)

        # 更新任务用量
        self._task_usage[task_id] += total

    def check_budget(self, agent_id: str, estimated_tokens: int = 0) -> Tuple[bool, str]:
        """检查是否超出预算。
        
        Args:
            agent_id: Agent 标识
            estimated_tokens: 预估需要的 token 数
        
        Returns:
            (是否允许，消息)
        """
        budget = self._daily_budgets[agent_id]
        budget.reset_if_needed()
        
        # 检查每日限额
        if self.daily_limit > 0:
            if budget.used + estimated_tokens > self.daily_limit:
                return (
                    False,
                    f"Daily token limit exceeded ({budget.used}/{self.daily_limit} tokens used today)"
                )
        
        return True, "OK"

    def check_task_budget(self, task_id: str, estimated_tokens: int = 0) -> Tuple[bool, str]:
        """检查任务预算。

        Args:
            task_id: 任务标识
            estimated_tokens: 预估需要的 token 数

        Returns:
            (是否允许，消息)
        """
        if self.per_task_limit == 0:
            return True, "OK"

        current_usage = self._task_usage.get(task_id, 0)
        if current_usage + estimated_tokens > self.per_task_limit:
            return (
                False,
                f"Task token limit exceeded ({current_usage}/{self.per_task_limit} tokens used)",
            )

        return True, "OK"

    def get_usage_report(self, agent_id: str | None = None) -> dict:
        """获取用量报告。

        Args:
            agent_id: 可选的 agent 过滤

        Returns:
            用量报告字典
        """
        if agent_id:
            budget = self._daily_budgets[agent_id]
            agent_usage = [u for u in self._history if u.agent_id == agent_id]
            total_tokens = sum(u.total_tokens for u in agent_usage)
            total_requests = len(agent_usage)
        else:
            budget = None
            total_tokens = sum(u.total_tokens for u in self._history)
            total_requests = len(self._history)
        
        report = {
            "total_tokens": total_tokens,
            "total_requests": total_requests,
        }

        if budget:
            report["daily_limit"] = self.daily_limit
            report["daily_used"] = budget.used
            report["daily_remaining"] = (
                max(0, self.daily_limit - budget.used) if self.daily_limit > 0 else "unlimited"
            )

        # 按 agent 分组统计
        agent_stats = defaultdict(lambda: {"tokens": 0, "requests": 0})
        for usage in self._history:
            agent_stats[usage.agent_id]["tokens"] += usage.total_tokens
            agent_stats[usage.agent_id]["requests"] += 1

        report["by_agent"] = dict(agent_stats)

        return report

    def get_task_usage(self, task_id: str) -> int:
        """获取指定任务的 token 用量。"""
        return self._task_usage.get(task_id, 0)

    def reset_daily(self, agent_id: str | None = None) -> None:
        """重置每日用量。

        Args:
            agent_id: 可选的 agent 过滤，None 表示重置所有
        """
        if agent_id:
            if agent_id in self._daily_budgets:
                self._daily_budgets[agent_id].reset_if_needed()
                self._daily_budgets[agent_id].used = 0
        else:
            for budget in self._daily_budgets.values():
                budget.used = 0
                budget.reset_date = date.today()

    def clear(self) -> None:
        """清空所有追踪数据。"""
        self._daily_budgets.clear()
        self._task_usage.clear()
        self._history.clear()
