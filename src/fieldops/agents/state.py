from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    messages: list[dict[str, Any]]
    request_id: str
    customer_id: str
    user_query: str
    category: str
    rag_context: list[dict]
    draft_answer: str
    reflection_notes: str
    tool_results: list[dict]
    final_response: str
    metrics: dict
