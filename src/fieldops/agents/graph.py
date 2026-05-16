"""
Multi-agent LangGraph workflow: triage → research (RAG) → action (tools) → reflection.

Patterns demonstrated for FDE interviews:
- ReAct-style tool use in the action node
- Self-reflection gate before returning to the user
- Hierarchical delegation via specialized nodes
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from fieldops.agents.state import AgentState
from fieldops.llm import get_chat_model, parse_json_from_llm
from fieldops.observability import RequestMetrics, span
from fieldops.observability.tracing import init_tracing
from fieldops.rag.retriever import KnowledgeRetriever
from fieldops.tools.enterprise import create_ticket, lookup_customer


TRIAGE_SYSTEM = """You are a support triage agent. Classify the user request into one of:
billing, incident, account, general. Respond ONLY with JSON:
{"category": "<label>", "needs_escalation": true|false, "rationale": "<short>"}"""

RESEARCH_SYSTEM = """You are a research agent. Use the provided policy excerpts to draft a helpful answer.
Respond ONLY with JSON: {"answer": "<text>", "citations": ["<source ids>"]}"""

REFLECTION_SYSTEM = """You are a safety/quality reviewer. Check the draft for:
- unsupported claims vs citations
- missing escalation for Enterprise incidents
Respond ONLY with JSON: {"approved": true|false, "notes": "<short>", "revised_answer": "<optional>"}"""


def _triage_node(state: AgentState) -> dict[str, Any]:
    model = get_chat_model()
    with span("agent.triage", {"request_id": state["request_id"]}):
        resp = model.invoke(TRIAGE_SYSTEM, state["user_query"])
    parsed = parse_json_from_llm(resp.content)
    category = str(parsed.get("category", "general"))
    return {
        "category": category,
        "messages": [{"role": "assistant", "content": f"[triage] {category}"}],
        "metrics": _merge_metrics(state, resp.usage, step="triage"),
    }


def _research_node(state: AgentState) -> dict[str, Any]:
    retriever = KnowledgeRetriever()
    with span("agent.research", {"request_id": state["request_id"]}):
        chunks = retriever.search(state["user_query"], k=4)
        context_block = "\n---\n".join(
            f"[{c['id']}] {c['text']}" for c in chunks
        ) or "No policy documents indexed."
        model = get_chat_model()
        user = f"Query: {state['user_query']}\n\nPolicy excerpts:\n{context_block}"
        resp = model.invoke(RESEARCH_SYSTEM, user)
    parsed = parse_json_from_llm(resp.content)
    metrics = _merge_metrics(state, resp.usage, step="research")
    metrics["rag_chunks_retrieved"] = len(chunks)
    return {
        "rag_context": chunks,
        "draft_answer": str(parsed.get("answer", resp.content)),
        "messages": [{"role": "assistant", "content": "[research] draft ready"}],
        "metrics": metrics,
    }


def _action_node(state: AgentState) -> dict[str, Any]:
    """ReAct-style tool execution based on category and customer tier."""
    tool_results: list[dict] = []
    customer = lookup_customer(state["customer_id"])
    tool_results.append({"tool": customer.audit_note, "result": customer.data})

    ticket_payload: dict | None = None
    if state["category"] in {"billing", "incident"}:
        priority = "P1" if state["category"] == "incident" else "P3"
        ticket = create_ticket(
            customer_id=state["customer_id"],
            title=f"{state['category'].title()}: {state['user_query'][:80]}",
            priority=priority,
            category=state["category"],
            body=state.get("draft_answer", ""),
        )
        tool_results.append({"tool": ticket.audit_note, "result": ticket.data})
        ticket_payload = ticket.data

    with span("agent.action", {"request_id": state["request_id"]}):
        pass

    answer = state.get("draft_answer", "")
    if ticket_payload:
        answer = f"{answer}\n\nTicket created: {ticket_payload['ticket_id']}"

    metrics = dict(state.get("metrics", {}))
    metrics["tool_calls"] = int(metrics.get("tool_calls", 0)) + len(tool_results)

    return {
        "tool_results": tool_results,
        "draft_answer": answer,
        "messages": [{"role": "assistant", "content": "[action] tools executed"}],
        "metrics": metrics,
    }


def _reflection_node(state: AgentState) -> dict[str, Any]:
    model = get_chat_model()
    user = json.dumps(
        {
            "category": state["category"],
            "draft_answer": state.get("draft_answer"),
            "customer": state.get("tool_results", [{}])[0].get("result", {}),
            "rag_chunks": len(state.get("rag_context", [])),
        }
    )
    with span("agent.reflection", {"request_id": state["request_id"]}):
        resp = model.invoke(REFLECTION_SYSTEM, user)
    parsed = parse_json_from_llm(resp.content)
    approved = bool(parsed.get("approved", True))
    final = parsed.get("revised_answer") or state.get("draft_answer", "")
    if not approved and not parsed.get("revised_answer"):
        final = f"{final}\n\n[Reviewer note: {parsed.get('notes', 'needs human review')}]"

    metrics = _merge_metrics(state, resp.usage, step="reflection")
    return {
        "reflection_notes": str(parsed.get("notes", "")),
        "final_response": final,
        "messages": [{"role": "assistant", "content": "[reflection] complete"}],
        "metrics": metrics,
    }


def _merge_metrics(state: AgentState, usage: Any, step: str) -> dict:
    raw = dict(state.get("metrics", {}))
    usages = list(raw.get("usages", []))
    usages.append(
        {
            "step": step,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "latency_ms": usage.latency_ms,
            "model": usage.model,
        }
    )
    raw["usages"] = usages
    return raw


def build_graph() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("triage", _triage_node)
    graph.add_node("research", _research_node)
    graph.add_node("action", _action_node)
    graph.add_node("reflection", _reflection_node)

    graph.set_entry_point("triage")
    graph.add_edge("triage", "research")
    graph.add_edge("research", "action")
    graph.add_edge("action", "reflection")
    graph.add_edge("reflection", END)
    return graph.compile()


def run_support_workflow(
    user_query: str,
    customer_id: str = "cust-1001",
    request_id: str | None = None,
) -> dict[str, Any]:
    init_tracing()
    rid = request_id or str(uuid.uuid4())
    app = build_graph()
    initial: AgentState = {
        "messages": [{"role": "user", "content": user_query}],
        "request_id": rid,
        "customer_id": customer_id,
        "user_query": user_query,
        "category": "",
        "rag_context": [],
        "draft_answer": "",
        "reflection_notes": "",
        "tool_results": [],
        "final_response": "",
        "metrics": {},
    }
    with span("workflow.support", {"request_id": rid}):
        result = app.invoke(initial)

    metrics = RequestMetrics(request_id=rid)
    for entry in result.get("metrics", {}).get("usages", []):
        from fieldops.llm import LLMUsage

        metrics.add_usage(
            LLMUsage(
                input_tokens=entry["input_tokens"],
                output_tokens=entry["output_tokens"],
                latency_ms=entry["latency_ms"],
                model=entry.get("model", ""),
            )
        )
    metrics.tool_calls = int(result.get("metrics", {}).get("tool_calls", 0))
    metrics.rag_chunks_retrieved = int(result.get("metrics", {}).get("rag_chunks_retrieved", 0))

    return {
        "request_id": rid,
        "category": result.get("category"),
        "answer": result.get("final_response"),
        "reflection_notes": result.get("reflection_notes"),
        "tool_results": result.get("tool_results"),
        "rag_context": result.get("rag_context"),
        "metrics": metrics.to_dict(),
    }
