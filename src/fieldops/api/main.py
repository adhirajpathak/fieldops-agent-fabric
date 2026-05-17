"""FastAPI service — Cloud Run ready entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from fieldops.agents.graph import run_support_workflow
from fieldops.config import get_settings
from fieldops.observability.tracing import init_tracing
from fieldops.rag.retriever import KnowledgeRetriever

app = FastAPI(
    title="FieldOps Agent Fabric",
    description="Enterprise support copilot — multi-agent + RAG + tools + observability",
    version="0.1.0",
)


class SupportRequest(BaseModel):
    query: str = Field(..., examples=["Customer reports us-central1 outage affecting payments"])
    customer_id: str = Field(default="cust-1001", examples=["cust-1001"])


class SupportResponse(BaseModel):
    request_id: str
    category: str | None
    answer: str | None
    metrics: dict
    reflection_notes: str | None = None


_rag_ready = False


@app.on_event("startup")
def startup() -> None:
    """Keep startup fast — RAG index is baked into the Docker image for Cloud Run."""
    global _rag_ready
    try:
        init_tracing()
    except Exception as exc:
        logger.warning("Tracing init skipped: %s", exc)
    try:
        _rag_ready = KnowledgeRetriever().document_count > 0
    except Exception as exc:
        logger.warning("RAG check failed: %s", exc)


@app.get("/")
def root() -> dict:
    return {
        "service": get_settings().otel_service_name,
        "health": "/health",
        "docs": "/docs",
        "rag_ready": _rag_ready,
    }


@app.get("/health")
@app.get("/healthz")
def healthz() -> dict:
    # Note: Cloud Run reserves /healthz at the edge (returns Google 404). Use /health on Run.
    return {"status": "ok", "service": get_settings().otel_service_name, "rag_ready": _rag_ready}


@app.post("/v1/support", response_model=SupportResponse)
def support(req: SupportRequest) -> SupportResponse:
    result = run_support_workflow(user_query=req.query, customer_id=req.customer_id)
    return SupportResponse(
        request_id=result["request_id"],
        category=result.get("category"),
        answer=result.get("answer"),
        metrics=result.get("metrics", {}),
        reflection_notes=result.get("reflection_notes"),
    )


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "fieldops.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
