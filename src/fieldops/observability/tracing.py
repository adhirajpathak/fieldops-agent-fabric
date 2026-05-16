"""OpenTelemetry tracing with optional export to Google Cloud Trace."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter
from opentelemetry.trace import Status, StatusCode

from fieldops.config import get_settings

_tracer: trace.Tracer | None = None
_initialized = False


def _build_exporter() -> SpanExporter:
    settings = get_settings()
    if settings.otel_export_gcp and settings.google_cloud_project:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            return CloudTraceSpanExporter(project_id=settings.google_cloud_project)
        except ImportError:
            pass
    return ConsoleSpanExporter()


def init_tracing() -> trace.Tracer:
    global _tracer, _initialized
    if _initialized and _tracer is not None:
        return _tracer

    settings = get_settings()
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_build_exporter()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(settings.otel_service_name)
    _initialized = True
    return _tracer


def get_tracer() -> trace.Tracer:
    return init_tracing()


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None) -> Generator[None, None, None]:
    tracer = get_tracer()
    start = time.perf_counter()
    with tracer.start_as_current_span(name) as current:
        if attributes:
            for key, value in attributes.items():
                current.set_attribute(key, value)
        try:
            yield
        except Exception as exc:
            current.set_status(Status(StatusCode.ERROR, str(exc)))
            current.record_exception(exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            current.set_attribute("duration_ms", elapsed_ms)
