"""Message router for multi-agent gateway.

Routes InboundMessage to the appropriate agent based on binding rules.
"""

import re
from cyberclaw.config.schema import AgentBinding
from cyberclaw.bus.events import InboundMessage


class MessageRouter:
    """根据 binding 规则将 InboundMessage 路由到目标 agent。

    匹配顺序：
    1. 按 priority 降序检查所有 bindings
    2. 第一个匹配的规则决定目标 agent
    3. 无匹配时返回 default_agent
    """

    def __init__(self, bindings: list[AgentBinding], default_agent: str = "default"):
        # 按 priority 降序排列 bindings
        self.bindings = sorted(bindings, key=lambda b: b.priority, reverse=True)
        self.default_agent = default_agent

    def route(self, msg: InboundMessage) -> str:
        """返回目标 agent_id。按 priority 顺序匹配第一个命中的规则。"""
        for binding in self.bindings:
            if self._matches(binding, msg):
                return binding.agent_id
        return self.default_agent

    def _matches(self, binding: AgentBinding, msg: InboundMessage) -> bool:
        """检查消息是否匹配 binding 规则。

        匹配条件（AND 逻辑）：
        - channel: 如果指定了 channels 列表，必须匹配其中之一（空列表=不限制）
        - chat_id: 如果指定了 chat_ids 列表，必须精确匹配其中之一（空列表=不限制）
        - chat_pattern: 如果指定了正则表达式，chat_id 必须匹配（None=不限制）
        - keywords: 如果指定了 keywords 列表，消息内容必须包含其中之一（空列表=不限制）

        所有指定的条件都必须满足才返回 True。
        空列表或 None 表示不限制该条件。
        """
        # 1. channel 匹配（空列表视为"不限制"）
        if binding.channels and msg.channel not in binding.channels:
            return False

        # 2. chat_id 精确匹配（空列表视为"不限制"）
        if binding.chat_ids and msg.chat_id not in binding.chat_ids:
            return False

        # 3. chat_id 正则匹配（None 视为"不限制"）
        if binding.chat_pattern:
            try:
                if not re.search(binding.chat_pattern, msg.chat_id):
                    return False
            except re.error:
                # Invalid regex, treat as non-matching
                return False

        # 4. keywords 内容匹配（空列表视为"不限制"）
        if binding.keywords:
            content_lower = msg.content.lower()
            if not any(keyword.lower() in content_lower for keyword in binding.keywords):
                return False

        # 所有条件都满足（或未指定）
        return True

    def get_routing_info(self) -> dict:
        """返回路由规则信息（用于调试/日志）。"""
        return {
            "default_agent": self.default_agent,
            "rules": [
                {
                    "agent_id": b.agent_id,
                    "priority": b.priority,
                    "channels": b.channels or "*",
                    "chat_ids": b.chat_ids or "*",
                    "chat_pattern": b.chat_pattern or "*",
                    "keywords": b.keywords or "*",
                }
                for b in self.bindings
            ],
        }
