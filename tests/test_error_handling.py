"""Tests for error handling and recovery."""

import pytest
from cyberclaw.agent.team.errors import (
    SubagentErrorType,
    SubagentError,
    classify_error,
    is_retryable_error,
    create_subagent_error,
    RetryConfig,
    RecoveryPlan,
    ErrorRecoveryStrategy,
)


class TestErrorClassification:
    """Test error classification."""

    def test_network_error(self):
        error = ConnectionError("Connection refused")
        assert classify_error(error) == SubagentErrorType.NETWORK

    def test_timeout_error(self):
        error = asyncio.TimeoutError("Task timed out")
        assert classify_error(error) == SubagentErrorType.TIMEOUT

    def test_rate_limit_error(self):
        error = Exception("Rate limit exceeded: 429 Too Many Requests")
        assert classify_error(error) == SubagentErrorType.RATE_LIMIT

    def test_api_limit_error(self):
        error = Exception("Quota exceeded. Please try again later")
        assert classify_error(error) == SubagentErrorType.API_LIMIT

    def test_budget_error(self):
        error = Exception("Token budget exceeded")
        assert classify_error(error) == SubagentErrorType.BUDGET_EXCEEDED

    def test_cancelled_error(self):
        error = asyncio.CancelledError("Task cancelled")
        assert classify_error(error) == SubagentErrorType.CANCELLED

    def test_logic_error(self):
        error = ValueError("Invalid parameter")
        assert classify_error(error) == SubagentErrorType.LOGIC

    def test_unknown_error(self):
        # Unknown errors default to LOGIC type
        error = Exception("Unknown error occurred")
        assert classify_error(error) == SubagentErrorType.LOGIC


class TestRetryableError:
    """Test retryable error detection."""

    def test_network_is_retryable(self):
        error = ConnectionError("Network error")
        assert is_retryable_error(error) is True

    def test_timeout_is_retryable(self):
        error = asyncio.TimeoutError("Timeout")
        assert is_retryable_error(error) is True

    def test_rate_limit_is_retryable(self):
        error = Exception("Rate limit exceeded")
        assert is_retryable_error(error) is True

    def test_logic_is_not_retryable(self):
        error = ValueError("Invalid value")
        assert is_retryable_error(error) is False

    def test_budget_is_not_retryable(self):
        error = Exception("Budget exceeded")
        assert is_retryable_error(error) is False


class TestSubagentError:
    """Test SubagentError creation."""

    def test_create_from_exception(self):
        error = ConnectionError("Connection failed")
        sub_error = create_subagent_error(error, "agent1", "task1")

        assert sub_error.error_type == SubagentErrorType.NETWORK
        assert sub_error.agent_id == "agent1"
        assert sub_error.task_id == "task1"
        assert sub_error.retryable is True

    def test_subagent_error_str(self):
        error = SubagentError(
            error_type=SubagentErrorType.NETWORK,
            message="Connection failed",
            retryable=True,
        )
        error_str = str(error)
        assert "network" in error_str
        assert "retryable" in error_str
        assert "Connection failed" in error_str


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_delay(self):
        config = RetryConfig()
        assert config.get_delay(0) == config.retry_delay

    def test_exponential_backoff(self):
        config = RetryConfig(exponential_backoff=True, retry_delay=1.0)
        assert config.get_delay(0) == 1.0
        assert config.get_delay(1) == 2.0
        assert config.get_delay(2) == 4.0

    def test_max_delay_cap(self):
        config = RetryConfig(
            retry_delay=10.0,
            exponential_backoff=True,
            max_delay=30.0,
        )
        # 10 * 2^3 = 80, but should be capped at 30
        assert config.get_delay(3) == 30.0

    def test_no_exponential_backoff(self):
        config = RetryConfig(exponential_backoff=False, retry_delay=5.0)
        assert config.get_delay(0) == 5.0
        assert config.get_delay(1) == 5.0
        assert config.get_delay(2) == 5.0


class TestRecoveryPlan:
    """Test recovery plan selection."""

    def test_network_error_plan(self):
        plan = RecoveryPlan.for_error_type(SubagentErrorType.NETWORK)
        assert plan.strategy == ErrorRecoveryStrategy.RETRY
        assert plan.max_retries == 3
        assert plan.notify_parent is False

    def test_timeout_error_plan(self):
        plan = RecoveryPlan.for_error_type(SubagentErrorType.TIMEOUT)
        assert plan.strategy == ErrorRecoveryStrategy.RETRY
        assert plan.max_retries == 3

    def test_rate_limit_plan(self):
        plan = RecoveryPlan.for_error_type(SubagentErrorType.RATE_LIMIT)
        assert plan.strategy == ErrorRecoveryStrategy.RETRY
        assert plan.max_retries == 5
        assert plan.delay_seconds == 30.0

    def test_api_limit_plan(self):
        plan = RecoveryPlan.for_error_type(SubagentErrorType.API_LIMIT)
        assert plan.strategy == ErrorRecoveryStrategy.NOTIFY_PARENT
        assert plan.max_retries == 0
        assert plan.notify_parent is True

    def test_budget_exceeded_plan(self):
        plan = RecoveryPlan.for_error_type(SubagentErrorType.BUDGET_EXCEEDED)
        assert plan.strategy == ErrorRecoveryStrategy.ABORT
        assert plan.notify_parent is True

    def test_cancelled_plan(self):
        plan = RecoveryPlan.for_error_type(SubagentErrorType.CANCELLED)
        assert plan.strategy == ErrorRecoveryStrategy.ABORT
        assert plan.notify_parent is False

    def test_logic_error_plan(self):
        plan = RecoveryPlan.for_error_type(SubagentErrorType.LOGIC)
        assert plan.strategy == ErrorRecoveryStrategy.NOTIFY_PARENT
        assert plan.notify_parent is True


# Import asyncio for timeout tests
import asyncio
