"""LLM and tool usage tracking via LangChain callbacks."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult


@dataclass
class UsageStats:
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int | None = None
    estimated_cost_usd: float | None = None
    provider_calls: int = 0
    provider_errors: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class UsageTracker(BaseCallbackHandler):
    """Callback handler that tracks LLM calls, tool calls, and token usage."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.tool_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.provider_calls = 0
        self.provider_errors = 0

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        with self._lock:
            self.llm_calls += 1

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        with self._lock:
            self.llm_calls += 1

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            generation = response.generations[0][0]
        except (IndexError, TypeError):
            return

        usage_metadata = None
        if hasattr(generation, "message"):
            message = generation.message
            if isinstance(message, AIMessage) and hasattr(message, "usage_metadata"):
                usage_metadata = message.usage_metadata

        if usage_metadata:
            with self._lock:
                self.tokens_in += int(usage_metadata.get("input_tokens", 0) or 0)
                self.tokens_out += int(usage_metadata.get("output_tokens", 0) or 0)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            self.tool_calls += 1

    def record_provider_call(self, *, error: bool = False) -> None:
        with self._lock:
            self.provider_calls += 1
            if error:
                self.provider_errors += 1

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "provider_calls": self.provider_calls,
                "provider_errors": self.provider_errors,
            }

    def to_usage_stats(
        self,
        *,
        duration_ms: int | None = None,
        estimated_cost_usd: float | None = None,
    ) -> UsageStats:
        raw = self.get_stats()
        return UsageStats(
            llm_calls=raw["llm_calls"],
            tool_calls=raw["tool_calls"],
            tokens_in=raw["tokens_in"],
            tokens_out=raw["tokens_out"],
            provider_calls=raw["provider_calls"],
            provider_errors=raw["provider_errors"],
            duration_ms=duration_ms,
            estimated_cost_usd=estimated_cost_usd,
        )


# Back-compat alias used by the CLI.
StatsCallbackHandler = UsageTracker
