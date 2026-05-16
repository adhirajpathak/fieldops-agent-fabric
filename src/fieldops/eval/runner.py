"""Evaluation pipeline with LLM-native metrics and simple accuracy checks."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fieldops.agents.graph import run_support_workflow
from fieldops.rag.ingest import ingest_directory


def _load_cases(path: Path) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def _score_case(case: dict, result: dict) -> dict:
    expected_category = case.get("expected_category", "").lower()
    actual_category = (result.get("category") or "").lower()
    category_ok = expected_category == actual_category

    must_contain = [s.lower() for s in case.get("answer_must_contain", [])]
    answer = (result.get("answer") or "").lower()
    content_ok = all(token in answer for token in must_contain)

    return {
        "id": case["id"],
        "category_ok": category_ok,
        "content_ok": content_ok,
        "passed": category_ok and content_ok,
        "metrics": result.get("metrics", {}),
    }


def main(argv: list[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    dataset = Path(argv[0] if argv else "data/eval/golden_cases.jsonl")
    ingest_directory()

    cases = _load_cases(dataset)
    started = time.perf_counter()
    results = []
    for case in cases:
        out = run_support_workflow(
            user_query=case["query"],
            customer_id=case.get("customer_id", "cust-1001"),
        )
        results.append(_score_case(case, out))

    elapsed = time.perf_counter() - started
    passed = sum(1 for r in results if r["passed"])
    total_tokens = sum(r["metrics"].get("total_tokens", 0) for r in results)
    total_cost = sum(r["metrics"].get("estimated_cost_usd", 0) for r in results)

    report = {
        "cases": len(cases),
        "passed": passed,
        "pass_rate": round(passed / len(cases), 3) if cases else 0.0,
        "wall_clock_s": round(elapsed, 2),
        "total_tokens": total_tokens,
        "total_estimated_cost_usd": round(total_cost, 4),
        "avg_tokens_per_case": round(total_tokens / len(cases), 1) if cases else 0,
        "results": results,
    }
    print(json.dumps(report, indent=2))
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
