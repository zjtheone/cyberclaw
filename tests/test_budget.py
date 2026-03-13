"""Tests for token budget tracking."""

import pytest
from cyberclaw.agent.team.budget import TokenBudgetTracker, DailyBudget


class TestDailyBudget:
    def test_unlimited_budget(self):
        budget = DailyBudget(limit=0)
        assert budget.can_use(1000) is True
        budget.use(1000)
        assert budget.used == 1000
    
    def test_limited_budget_allowed(self):
        budget = DailyBudget(limit=1000)
        assert budget.can_use(500) is True
        budget.use(500)
        assert budget.used == 500
    
    def test_limited_budget_exceeded(self):
        budget = DailyBudget(limit=1000)
        budget.use(800)
        assert budget.can_use(300) is False
    
    def test_daily_reset(self):
        from datetime import date, timedelta
        budget = DailyBudget(limit=1000)
        budget.used = 500
        budget.reset_date = date.today() - timedelta(days=1)
        budget.reset_if_needed()
        assert budget.used == 0


class TestTokenBudgetTracker:
    def test_record_usage(self):
        tracker = TokenBudgetTracker()
        tracker.record_usage("agent1", "task1", 100, 50)
        report = tracker.get_usage_report("agent1")
        assert report["total_tokens"] == 150
        assert report["total_requests"] == 1
    
    def test_daily_limit_check(self):
        tracker = TokenBudgetTracker(daily_limit=1000)
        tracker.record_usage("agent1", "task1", 400, 100)  # 500
        tracker.record_usage("agent1", "task2", 300, 100)  # 900 total
        allowed, msg = tracker.check_budget("agent1", 200)
        assert allowed is False
        assert "limit exceeded" in msg.lower()
    
    def test_per_task_limit_check(self):
        tracker = TokenBudgetTracker(per_task_limit=500)
        tracker.record_usage("agent1", "task1", 200, 100)  # 300
        allowed, msg = tracker.check_task_budget("task1", 300)
        assert allowed is False
    
    def test_usage_report_by_agent(self):
        tracker = TokenBudgetTracker()
        tracker.record_usage("agent1", "task1", 100, 50)
        tracker.record_usage("agent1", "task2", 200, 100)
        tracker.record_usage("agent2", "task3", 300, 150)
        
        report1 = tracker.get_usage_report("agent1")
        assert report1["total_tokens"] == 450
        assert report1["total_requests"] == 2
        
        report_all = tracker.get_usage_report()
        assert report_all["total_tokens"] == 900
        assert report_all["total_requests"] == 3
    
    def test_clear(self):
        tracker = TokenBudgetTracker()
        tracker.record_usage("agent1", "task1", 100, 50)
        tracker.clear()
        report = tracker.get_usage_report()
        assert report["total_tokens"] == 0
    
    def test_task_usage_tracking(self):
        tracker = TokenBudgetTracker()
        tracker.record_usage("agent1", "task1", 100, 50)
        tracker.record_usage("agent1", "task1", 200, 100)
        assert tracker.get_task_usage("task1") == 450
    
    def test_combined_limits(self):
        tracker = TokenBudgetTracker(daily_limit=1000, per_task_limit=300)
        tracker.record_usage("agent1", "task1", 150, 50)  # 200 for task1
        allowed, _ = tracker.check_task_budget("task1", 200)
        assert allowed is False  # Would be 400 > 300
        
        tracker.record_usage("agent1", "task2", 400, 350)  # 750 more, total 950
        allowed, msg = tracker.check_budget("agent1", 100)
        assert allowed is False  # Would be 1050 > 1000
        assert "limit exceeded" in msg.lower()
