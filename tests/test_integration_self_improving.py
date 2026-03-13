"""
集成验证脚本：验证 4 项自改进系统改动是否生效。

运行方式：
    pytest tests/test_integration_self_improving.py -v -s

验证内容：
    1. Skill vs Tool 分离 - SkillsLoader 动态发现，skill_evolution 正确接入
    2. Reflection Await - _pending_reflection_tasks 存在且可跟踪
    3. 反馈闭环 - ConfidenceEvaluator 和 ToolOptimizer 的自适应权重
    4. 端到端数据流 - 从技能跟踪到反馈闭环的完整流程
"""

from pathlib import Path
from unittest.mock import MagicMock

from cyberclaw.agent.skills import SkillsLoader
from cyberclaw.agent.skill_evolution import SkillEvolutionAnalyzer
from cyberclaw.agent.confidence import ConfidenceEvaluator
from cyberclaw.agent.tool_optimizer import ToolOptimizer
from cyberclaw.agent.experience import ExperienceRepository
from cyberclaw.agent.metrics import MetricsTracker


# ─── 验证 1: Skill 动态发现 ─────────────────────────────────

class TestSkillDiscovery:
    """验证 SkillsLoader 能发现真实的内置技能。"""

    def test_builtin_skills_discovered(self):
        """SkillsLoader 应能发现 cyberclaw/skills/ 下的内置技能。"""
        workspace = Path("/tmp/test_workspace_discovery")
        workspace.mkdir(exist_ok=True)
        loader = SkillsLoader(workspace)
        skills = loader.list_skills(filter_unavailable=False)
        skill_names = {s["name"] for s in skills}

        print(f"\n发现 {len(skills)} 个技能: {skill_names}")

        # 至少应发现这些内置技能
        expected = {"weather", "github", "cron", "memory", "summarize"}
        found = expected & skill_names
        assert len(found) >= 3, f"内置技能发现不足，仅找到: {found}"
        print(f"✅ 技能发现正常: {found}")

    def test_skill_evolution_uses_loader(self, tmp_path):
        """SkillEvolutionAnalyzer 应通过 SkillsLoader 发现技能。"""
        workspace = tmp_path
        (workspace / ".cyberclaw").mkdir()

        loader = SkillsLoader(workspace)
        metrics = MetricsTracker(workspace)
        exp_repo = ExperienceRepository(workspace)
        optimizer = ToolOptimizer(workspace, metrics_tracker=metrics)

        analyzer = SkillEvolutionAnalyzer(
            workspace=workspace,
            experience_repo=exp_repo,
            metrics_tracker=metrics,
            tool_optimizer=optimizer,
            skills_loader=loader,
        )

        known = analyzer.get_known_skill_names()
        print(f"\nSkillEvolutionAnalyzer 已知技能: {known}")
        assert len(known) >= 3, f"通过 loader 发现的技能不足: {known}"
        print("✅ SkillEvolutionAnalyzer 正确接入 SkillsLoader")

    def test_skill_tracking_with_source(self, tmp_path):
        """技能跟踪应记录 source 信息。"""
        workspace = tmp_path
        (workspace / ".cyberclaw").mkdir()

        metrics = MetricsTracker(workspace)
        exp_repo = ExperienceRepository(workspace)
        optimizer = ToolOptimizer(workspace, metrics_tracker=metrics)

        analyzer = SkillEvolutionAnalyzer(
            workspace=workspace,
            experience_repo=exp_repo,
            metrics_tracker=metrics,
            tool_optimizer=optimizer,
        )

        analyzer.track_skill_usage(
            skill_name="weather",
            success=True,
            duration=1.5,
            task_description="查询天气",
            skill_source="builtin",
        )

        stats = analyzer._stats["weather"]
        assert stats.source == "builtin"
        assert stats.total_uses == 1
        print(f"\n✅ 技能跟踪记录 source: {stats.source}, uses: {stats.total_uses}")


# ─── 验证 2: Reflection Await ───────────────────────────────

class TestReflectionAwait:
    """验证 AgentLoop 中 _pending_reflection_tasks 的存在。"""

    def test_agent_loop_has_pending_tasks_set(self):
        """AgentLoop 应有 _pending_reflection_tasks 属性。"""
        # 检查代码中是否存在该属性定义
        import inspect
        from cyberclaw.agent.loop import AgentLoop
        source = inspect.getsource(AgentLoop.__init__)

        assert "_pending_reflection_tasks" in source, \
            "AgentLoop.__init__ 中缺少 _pending_reflection_tasks"
        print("\n✅ AgentLoop 已添加 _pending_reflection_tasks 跟踪集合")

    def test_shutdown_awaits_reflections(self):
        """shutdown 代码中应等待未完成的反思任务。"""
        import inspect
        from cyberclaw.agent.loop import AgentLoop
        source = inspect.getsource(AgentLoop.run)

        assert "asyncio.wait" in source and "_pending_reflection_tasks" in source, \
            "AgentLoop.run finally 块中缺少 asyncio.wait(_pending_reflection_tasks)"
        print("\n✅ shutdown 时正确等待反思任务完成")


# ─── 验证 3: 反馈闭环 ──────────────────────────────────────

class TestFeedbackLoop:
    """验证置信度和工具推荐的反馈闭环。"""

    def test_confidence_domain_weights_adaptive(self, tmp_path):
        """域权重应随 record_outcome 调整。"""
        evaluator = ConfidenceEvaluator(tmp_path)

        # 确认是实例级别属性（不是类级别）
        assert hasattr(evaluator, 'domain_confidence')
        assert evaluator.domain_confidence is not ConfidenceEvaluator.DOMAIN_CONFIDENCE

        original = evaluator.domain_confidence["code"]

        # 预测偏低但实际成功 → 权重应提高
        evaluator.record_outcome("test", predicted_score=0.3, actual_success=True, domain="code")
        after = evaluator.domain_confidence["code"]

        print(f"\n权重变化: {original:.3f} → {after:.3f}")
        assert after > original, f"权重未提高: {original} → {after}"
        print("✅ 置信度反馈闭环生效")

    def test_tool_optimizer_adaptive_weights(self, tmp_path):
        """工具推荐权重应随反馈自适应。"""
        metrics = MetricsTracker(tmp_path)
        optimizer = ToolOptimizer(tmp_path, metrics_tracker=metrics)

        assert hasattr(optimizer, '_adaptive_weights')
        assert hasattr(optimizer, '_recommendation_outcomes')

        original = dict(optimizer._adaptive_weights)

        # 模拟推荐被采纳但失败、未采纳但成功的场景
        for i in range(20):
            optimizer.record_recommendation_outcome(
                recommended_tool="tool_a",
                actual_tool_used="tool_a" if i % 2 == 0 else "tool_b",
                task_description="test task",
                success=(i % 2 != 0),  # 未采纳（tool_b）时成功
            )

        print(f"\n原始权重: {original}")
        print(f"调整后:   {optimizer._adaptive_weights}")
        assert optimizer._adaptive_weights != original, "权重未发生变化"
        print("✅ 工具推荐自适应权重生效")

    def test_confidence_feedback_in_loop_source(self):
        """loop.py 中应有 record_outcome 调用。"""
        import inspect
        from cyberclaw.agent.loop import AgentLoop
        source = inspect.getsource(AgentLoop._generate_task_reflection)

        assert "record_outcome" in source, \
            "_generate_task_reflection 中缺少 record_outcome 调用"
        print("\n✅ loop.py 中已接入置信度反馈闭环")


# ─── 验证 4: 端到端数据流 ──────────────────────────────────

class TestEndToEnd:
    """验证从技能发现到反馈闭环的完整数据流。"""

    def test_full_flow(self, tmp_path):
        """模拟完整流程: 发现技能 → 跟踪使用 → 评估置信度 → 反馈。"""
        workspace = tmp_path
        (workspace / ".cyberclaw").mkdir()

        # 1. 技能发现
        mock_loader = MagicMock()
        mock_loader.list_skills.return_value = [
            {"name": "weather", "source": "builtin", "path": "/skills/weather/SKILL.md"},
            {"name": "github", "source": "builtin", "path": "/skills/github/SKILL.md"},
        ]

        # 2. 初始化组件
        metrics = MetricsTracker(workspace)
        exp_repo = ExperienceRepository(workspace)
        optimizer = ToolOptimizer(workspace, metrics_tracker=metrics)
        evaluator = ConfidenceEvaluator(workspace)
        analyzer = SkillEvolutionAnalyzer(
            workspace=workspace,
            experience_repo=exp_repo,
            metrics_tracker=metrics,
            tool_optimizer=optimizer,
            skills_loader=mock_loader,
        )

        # 3. 验证技能被发现
        known = analyzer.get_known_skill_names()
        assert "weather" in known
        print(f"\n[Step 1] 发现技能: {known}")

        # 4. 模拟技能使用
        analyzer.track_skill_usage("weather", success=True, duration=2.0,
                                   task_description="查询北京天气", skill_source="builtin")
        assert analyzer._stats["weather"].total_uses == 1
        print(f"[Step 2] 跟踪技能使用: weather (uses={analyzer._stats['weather'].total_uses})")

        # 5. 置信度评估
        result = evaluator.evaluate(
            question="北京今天天气怎么样？",
            answer="北京今天晴天，温度25度，适合出行。",
            context={"domain": "factual"},
            tool_results=[{"success": True}],
        )
        print(f"[Step 3] 置信度评估: score={result.score:.3f}, level={result.level}")

        # 6. 反馈闭环
        original_weight = evaluator.domain_confidence.get("factual", 0.7)
        evaluator.record_outcome(
            question="天气查询",
            predicted_score=result.score,
            actual_success=True,
            domain="factual",
        )
        new_weight = evaluator.domain_confidence.get("factual", 0.7)
        print(f"[Step 4] 反馈闭环: factual 权重 {original_weight:.3f} → {new_weight:.3f}")

        # 7. 工具推荐反馈
        optimizer.record_recommendation_outcome(
            recommended_tool="weather",
            actual_tool_used="weather",
            task_description="查询天气",
            success=True,
        )
        print(f"[Step 5] 工具推荐反馈: 已记录 {len(optimizer._recommendation_outcomes)} 条")

        print("\n✅ 端到端数据流验证通过!")
