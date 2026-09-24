"""A scripted tool-calling chat model so the agent loop can be tested without an API key."""
import json
from typing import Any, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedToolLLM(BaseChatModel):
    """Emits the queued tool calls one per turn, then a final answer; JSON when asked to summarise."""
    script: List[Any] = []
    step: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, **kwargs) -> ChatResult:
        text = " ".join(str(m.content) for m in messages)
        if "format_instructions" in text or "required JSON" in text or "ONLY valid JSON" in text:
            msg = AIMessage(content=json.dumps({
                "recommendation": "Scripted summary", "key_figures": ["EMI Rs 8,611/month"],
                "tools_used": ["search_inventory", "calculate_purchase_plan"], "data_gaps": "",
                "confidence": "high"}))
            return ChatResult(generations=[ChatGeneration(message=msg)])
        if self.step < len(self.script):
            item = self.script[self.step]
            self.step += 1
            if isinstance(item, tuple):
                name, args = item
                msg = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{self.step}"}])
            else:
                msg = AIMessage(content=item)
            return ChatResult(generations=[ChatGeneration(message=msg)])
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Final scripted answer."))])
