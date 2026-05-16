"""Unified LLM access with token/cost accounting for LLM-native metrics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from fieldops.config import Settings, get_settings


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def estimated_cost_usd(self, settings: Settings | None = None) -> float:
        s = settings or get_settings()
        in_cost = (self.input_tokens / 1_000_000) * s.cost_per_1m_input_tokens
        out_cost = (self.output_tokens / 1_000_000) * s.cost_per_1m_output_tokens
        return round(in_cost + out_cost, 6)


@dataclass
class LLMResponse:
    content: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    raw: dict[str, Any] | None = None


class ChatModel(Protocol):
    def invoke(self, system: str, user: str) -> LLMResponse: ...


class MockChatModel:
    """Deterministic responses for CI, demos without cloud credentials."""

    def invoke(self, system: str, user: str) -> LLMResponse:
        text = user.lower()
        if "refund" in text or "billing" in text:
            category = "billing"
            answer = (
                "Per policy REF-2024-03, refunds over $500 require manager approval. "
                "I can draft a ticket for the billing queue."
            )
        elif "outage" in text or "down" in text:
            category = "incident"
            answer = (
                "Status page shows partial degradation in us-central1. "
                "Escalate to SRE if customer tier is Enterprise."
            )
        else:
            category = "general"
            answer = "I retrieved relevant knowledge and can open a support ticket if needed."

        payload = json.dumps({"category": category, "answer": answer})
        return LLMResponse(
            content=payload,
            usage=LLMUsage(input_tokens=120, output_tokens=80, latency_ms=45.0, model="mock"),
            raw={"category": category},
        )


class VertexChatModel:
    def __init__(self, settings: Settings) -> None:
        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError as exc:
            raise RuntimeError("Install GCP extras: pip install -e '.[gcp]'") from exc

        self._model = ChatVertexAI(
            model_name=settings.vertex_model,
            project=settings.google_cloud_project,
            location=settings.google_cloud_region,
            temperature=0.2,
        )
        self._model_name = settings.vertex_model

    def invoke(self, system: str, user: str) -> LLMResponse:
        import time

        from langchain_core.messages import HumanMessage, SystemMessage

        start = time.perf_counter()
        msg = self._model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        latency_ms = (time.perf_counter() - start) * 1000
        meta = getattr(msg, "usage_metadata", None) or {}
        return LLMResponse(
            content=str(msg.content),
            usage=LLMUsage(
                input_tokens=int(meta.get("input_tokens", 0)),
                output_tokens=int(meta.get("output_tokens", 0)),
                latency_ms=latency_ms,
                model=self._model_name,
            ),
        )


class OpenAIChatModel:
    def __init__(self, settings: Settings) -> None:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install OpenAI extras: pip install -e '.[openai]'") from exc

        self._model = ChatOpenAI(model=settings.openai_model, temperature=0.2)
        self._model_name = settings.openai_model

    def invoke(self, system: str, user: str) -> LLMResponse:
        import time

        from langchain_core.messages import HumanMessage, SystemMessage

        start = time.perf_counter()
        msg = self._model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        latency_ms = (time.perf_counter() - start) * 1000
        meta = getattr(msg, "response_metadata", {}) or {}
        usage = meta.get("token_usage", {})
        return LLMResponse(
            content=str(msg.content),
            usage=LLMUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                latency_ms=latency_ms,
                model=self._model_name,
            ),
        )


def get_chat_model(settings: Settings | None = None) -> ChatModel:
    s = settings or get_settings()
    if s.llm_provider == "vertex":
        if not s.google_cloud_project:
            raise ValueError("GOOGLE_CLOUD_PROJECT required for vertex provider")
        return VertexChatModel(s)
    if s.llm_provider == "openai":
        if not s.openai_api_key:
            raise ValueError("OPENAI_API_KEY required for openai provider")
        return OpenAIChatModel(s)
    return MockChatModel()


def parse_json_from_llm(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from model output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"answer": text, "category": "general"}
