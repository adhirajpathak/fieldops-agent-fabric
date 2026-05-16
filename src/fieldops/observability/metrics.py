"""LLM-native metrics aggregation for eval runs and live requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from fieldops.llm import LLMUsage


@dataclass
class RequestMetrics:
    request_id: str
    usages: list[LLMUsage] = field(default_factory=list)
    tool_calls: int = 0
    rag_chunks_retrieved: int = 0

    def add_usage(self, usage: LLMUsage) -> None:
        self.usages.append(usage)

    @property
    def total_input_tokens(self) -> int:
        return sum(u.input_tokens for u in self.usages)

    @property
    def total_output_tokens(self) -> int:
        return sum(u.output_tokens for u in self.usages)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_latency_ms(self) -> float:
        return sum(u.latency_ms for u in self.usages)

    @property
    def tokens_per_second(self) -> float:
        if self.total_latency_ms <= 0:
            return 0.0
        return self.total_tokens / (self.total_latency_ms / 1000)

    def to_dict(self) -> dict:
        from fieldops.config import get_settings

        settings = get_settings()
        cost = sum(u.estimated_cost_usd(settings) for u in self.usages)
        return {
            "request_id": self.request_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "tokens_per_second": round(self.tokens_per_second, 2),
            "estimated_cost_usd": cost,
            "tool_calls": self.tool_calls,
            "rag_chunks_retrieved": self.rag_chunks_retrieved,
            "llm_calls": len(self.usages),
        }
