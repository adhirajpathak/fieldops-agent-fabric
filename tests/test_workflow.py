import os

os.environ.setdefault("LLM_PROVIDER", "mock")

from fieldops.agents.graph import run_support_workflow
from fieldops.rag.ingest import ingest_directory


def test_support_workflow_mock():
    ingest_directory()
    result = run_support_workflow(
        user_query="Customer wants a $2000 refund for duplicate charge",
        customer_id="cust-1001",
    )
    assert result["category"] == "billing"
    assert result["answer"]
    assert result["metrics"]["total_tokens"] > 0
    assert "ticket" in result["answer"].lower() or "TKT" in result["answer"]
