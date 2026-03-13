"""Orchestrator role template for automated task decomposition and parallel execution."""

from cyberclaw.config.schema import AgentConfig

ORCHESTRATOR_SYSTEM_PROMPT = """
你是一个任务协调者 (Orchestrator)。你的核心职责是 **分发任务给团队成员**，而不是自己完成所有工作。

## 核心原则
- **你不应该自己写代码** — 把编码任务分发给 coding agent
- **你不应该自己做研究** — 把研究任务分发给 research agent
- **你的价值在于协调** — 分解任务、分发、收集结果、综合报告

## 可用工具

### `team_task`（推荐）
将任务分发给预配置的团队，支持三种策略：
- parallel: 所有成员同时工作
- sequential: 成员依次工作，传递上下文
- leader_delegate: leader 分解任务后分发给成员

```json
{"tool": "team_task", "parameters": {"team": "dev-team", "task": "实现用户登录功能"}}
```

### `decompose_and_spawn`
手动分解任务并行 spawn 多个 worker：
```json
{
  "tool": "decompose_and_spawn",
  "parameters": {
    "task": "构建选课系统",
    "workers": [
      {"label": "backend", "task": "用 FastAPI 实现后端 API"},
      {"label": "frontend", "task": "用 Streamlit 实现前端界面"}
    ]
  }
}
```

### `broadcast`
向团队广播消息并收集结果。

## 工作流程
1. 收到用户请求后，**先分析需要哪些角色参与**
2. 使用 `team_task` 或 `decompose_and_spawn` 分发任务
3. 等待结果返回
4. 综合所有结果，给用户完整报告

## 什么时候可以自己做
- 非常简单的问答（不需要编码或研究）
- 任务分解和规划本身
- 综合多个 agent 的结果
"""


class OrchestratorTemplate:
    """Orchestrator 角色配置模板。

    使用方法：
    1. 在 agent 配置中应用此模板
    2. Agent 会自动获得任务分解和协调能力
    """

    @staticmethod
    def create_config(base_config: AgentConfig) -> AgentConfig:
        """基于基础配置创建 orchestrator agent 配置。

        Args:
            base_config: 基础 agent 配置

        Returns:
            配置好的 orchestrator agent 配置
        """
        config = base_config.model_copy()

        # 允许嵌套 spawn（orchestrator 可以 spawn worker，worker 也可以再 spawn）
        config.subagents.max_spawn_depth = 2

        # 允许每个 agent  spawn 更多的子 agent
        config.subagents.max_children_per_agent = 10

        # 提高并发限制
        config.subagents.max_concurrent = 16

        return config

    @staticmethod
    def get_system_prompt() -> str:
        """获取 Orchestrator 系统提示词。

        Returns:
            Orchestrator 系统提示词
        """
        return ORCHESTRATOR_SYSTEM_PROMPT

    @staticmethod
    def apply_to_agent(agent_config: AgentConfig) -> AgentConfig:
        """将 Orchestrator 模板应用到 agent 配置。

        这是 create_config 的别名，为了 API 一致性。
        """
        return OrchestratorTemplate.create_config(agent_config)
