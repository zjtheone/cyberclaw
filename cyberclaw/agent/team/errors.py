"""Error types and classification for agent team operations."""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional


class SubagentErrorType(Enum):
    """子 agent 错误类型。"""

    NETWORK = "network"  # 网络错误，可重试
    API_LIMIT = "api_limit"  # API 限额，需等待
    LOGIC = "logic"  # 逻辑错误，不可重试
    TIMEOUT = "timeout"  # 超时
    RATE_LIMIT = "rate_limit"  # 速率限制
    BUDGET_EXCEEDED = "budget"  # 预算超限
    CANCELLED = "cancelled"  # 被取消
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class SubagentError(Exception):
    """子 agent 执行错误。

    Attributes:
        error_type: 错误类型
        message: 错误消息
        agent_id: 出错的 agent ID
        task_id: 任务 ID
        retryable: 是否可重试
        details: 额外详情
    """

    error_type: SubagentErrorType
    message: str
    agent_id: str = ""
    task_id: str = ""
    retryable: bool = False
    details: Optional[dict] = None

    def __str__(self) -> str:
        retry_info = " (retryable)" if self.retryable else ""
        return f"[{self.error_type.value}{retry_info}] {self.message}"


@dataclass
class RetryConfig:
    """重试配置。

    Attributes:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
        exponential_backoff: 是否指数退避
        max_delay: 最大延迟（秒）
    """

    max_retries: int = 3
    retry_delay: float = 5.0
    exponential_backoff: bool = True
    max_delay: float = 60.0

    def get_delay(self, attempt: int) -> float:
        """计算第 attempt 次重试的延迟。

        Args:
            attempt: 重试次数（从 0 开始）

        Returns:
            延迟秒数
        """
        if self.exponential_backoff:
            delay = self.retry_delay * (2**attempt)
            return min(delay, self.max_delay)
        return self.retry_delay


def classify_error(error: Exception) -> SubagentErrorType:
    """根据异常类型分类错误。

    Args:
        error: 异常对象

    Returns:
        SubagentErrorType
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    # 网络相关错误
    network_keywords = [
        "connection",
        "network",
        "timeout",
        "socket",
        "dns",
        "unreachable",
        "refused",
        "reset",
    ]
    if any(kw in error_str or kw in error_type for kw in network_keywords):
        # 但 timeout 单独分类
        if "timeout" in error_str or "timeout" in error_type:
            return SubagentErrorType.TIMEOUT
        return SubagentErrorType.NETWORK

    # API 限额错误
    api_limit_keywords = [
        "rate limit",
        "quota",
        "limit exceeded",
        "too many requests",
        "429",
        "403",
        "forbidden",
    ]
    if any(kw in error_str for kw in api_limit_keywords):
        if "rate" in error_str:
            return SubagentErrorType.RATE_LIMIT
        return SubagentErrorType.API_LIMIT

    # 预算超限
    budget_keywords = ["budget", "token limit", "cost"]
    if any(kw in error_str for kw in budget_keywords):
        return SubagentErrorType.BUDGET_EXCEEDED

    # 取消
    cancel_keywords = ["cancel", "abort", "terminated"]
    if any(kw in error_str or kw in error_type for kw in cancel_keywords):
        return SubagentErrorType.CANCELLED

    # 默认为逻辑错误（不可重试）
    return SubagentErrorType.LOGIC


def is_retryable_error(error: Exception) -> bool:
    """判断错误是否可重试。

    Args:
        error: 异常对象

    Returns:
        是否可重试
    """
    error_type = classify_error(error)

    # 可重试的错误类型
    retryable_types = {
        SubagentErrorType.NETWORK,
        SubagentErrorType.TIMEOUT,
        SubagentErrorType.RATE_LIMIT,
    }

    return error_type in retryable_types


def create_subagent_error(
    error: Exception,
    agent_id: str = "",
    task_id: str = "",
) -> SubagentError:
    """从异常创建 SubagentError。

    Args:
        error: 原始异常
        agent_id: Agent ID
        task_id: 任务 ID

    Returns:
        SubagentError
    """
    error_type = classify_error(error)
    retryable = is_retryable_error(error)

    return SubagentError(
        error_type=error_type,
        message=str(error),
        agent_id=agent_id,
        task_id=task_id,
        retryable=retryable,
        details={
            "original_error_type": type(error).__name__,
        },
    )


class ErrorRecoveryStrategy(Enum):
    """错误恢复策略。"""

    RETRY = "retry"  # 重试
    SKIP = "skip"  # 跳过
    FALLBACK = "fallback"  # 使用 fallback
    ABORT = "abort"  # 中止
    NOTIFY_PARENT = "notify_parent"  # 通知父 agent


@dataclass
class RecoveryPlan:
    """恢复计划。

    Attributes:
        strategy: 恢复策略
        max_retries: 最大重试次数
        delay_seconds: 延迟秒数
        fallback_task: fallback 任务描述
        notify_parent: 是否通知父 agent
    """

    strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.RETRY
    max_retries: int = 3
    delay_seconds: float = 5.0
    fallback_task: str = ""
    notify_parent: bool = False

    @classmethod
    def for_error_type(cls, error_type: SubagentErrorType) -> "RecoveryPlan":
        """根据错误类型创建恢复计划。

        Args:
            error_type: 错误类型

        Returns:
            RecoveryPlan
        """
        if error_type in (SubagentErrorType.NETWORK, SubagentErrorType.TIMEOUT):
            # 网络/超时错误：重试
            return cls(
                strategy=ErrorRecoveryStrategy.RETRY,
                max_retries=3,
                delay_seconds=5.0,
                notify_parent=False,
            )

        elif error_type == SubagentErrorType.RATE_LIMIT:
            # 速率限制：带退避的重试
            return cls(
                strategy=ErrorRecoveryStrategy.RETRY,
                max_retries=5,
                delay_seconds=30.0,  # 更长延迟
                notify_parent=False,
            )

        elif error_type == SubagentErrorType.API_LIMIT:
            # API 限额：通知父 agent
            return cls(
                strategy=ErrorRecoveryStrategy.NOTIFY_PARENT,
                max_retries=0,
                notify_parent=True,
            )

        elif error_type == SubagentErrorType.BUDGET_EXCEEDED:
            # 预算超限：中止
            return cls(
                strategy=ErrorRecoveryStrategy.ABORT,
                max_retries=0,
                notify_parent=True,
            )

        elif error_type == SubagentErrorType.CANCELLED:
            # 被取消：不恢复
            return cls(
                strategy=ErrorRecoveryStrategy.ABORT,
                max_retries=0,
                notify_parent=False,
            )

        else:
            # 逻辑错误/未知：跳过或通知
            return cls(
                strategy=ErrorRecoveryStrategy.NOTIFY_PARENT,
                max_retries=0,
                notify_parent=True,
            )
