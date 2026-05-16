"""
Google ADK variant — mirrors the same support workflow using Google's Agent Development Kit.

Enable after: pip install google-adk && gcloud auth application-default login

This module is optional at import time so the repo runs in mock mode without ADK credentials.
See README section "ADK deployment path".
"""

from __future__ import annotations


def build_adk_support_agent():
    """
    Skeleton for ADK-based agent with MCP tool wiring.

    Uncomment and extend once `google-adk` is configured for your GCP project.
    Referenced in interviews to show familiarity with Google's preferred agent stack.
    """
    try:
        from google.adk.agents import LlmAgent  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("Install google-adk to use the ADK code path") from exc

    return LlmAgent(
        name="fieldops_support",
        model="gemini-2.0-flash",
        instruction=(
            "You are an enterprise support copilot. Triage requests, cite policy, "
            "and propose ticket actions. Use tools for CRM lookup and incident creation."
        ),
    )
