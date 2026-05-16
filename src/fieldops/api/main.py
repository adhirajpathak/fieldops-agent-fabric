"""FastAPI service — Cloud Run ready entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from fieldops.agents.graph import run_support_workflow
from fieldops.config import get_settings
from fieldops.observability.tracing import init_tracing
from fieldops.rag.ingest import ingest_directory

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


@app.on_event("startup")
def startup() -> None:
    init_tracing()
    ingest_directory()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": get_settings().otel_service_name}


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
