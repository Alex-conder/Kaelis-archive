"""
OpenTelemetry setup for Kaelis.

Provides:
- TracerProvider with BatchSpanProcessor + ConsoleSpanExporter
- get_tracer(name) helper
- @trace_span(name) decorator (sync + async)
- Optional Flask auto-instrumentation
- In-memory metrics aggregation for real-time monitoring
- WebSocket trace event broadcasting
"""

import asyncio
import functools
import inspect
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

# ============================================================================
# In-memory metrics aggregation
# ============================================================================

class _MetricsAggregator:
    """Thread-safe in-memory aggregator for observability metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls = 0
        self._errors = 0
        self._latencies: List[float] = []
        self._max_latencies = 1000  # rolling window
        self._trace_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def record_call(self, latency_ms: float, error: bool = False):
        with self._lock:
            self._calls += 1
            if error:
                self._errors += 1
            self._latencies.append(latency_ms)
            if len(self._latencies) > self._max_latencies:
                self._latencies = self._latencies[-self._max_latencies:]

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            latencies = self._latencies.copy()
            calls = self._calls
            errors = self._errors
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        return {
            "call_count": calls,
            "error_count": errors,
            "avg_latency_ms": round(avg_latency, 2),
            "error_rate": round(errors / calls, 4) if calls > 0 else 0.0,
            "window_size": len(latencies),
        }

    def reset(self):
        with self._lock:
            self._calls = 0
            self._errors = 0
            self._latencies = []

    def register_trace_callback(self, callback: Callable[[Dict[str, Any]], None]):
        with self._lock:
            self._trace_callbacks.append(callback)

    def unregister_trace_callback(self, callback: Callable[[Dict[str, Any]], None]):
        with self._lock:
            if callback in self._trace_callbacks:
                self._trace_callbacks.remove(callback)

    def emit_trace_event(self, event: Dict[str, Any]):
        with self._lock:
            callbacks = self._trace_callbacks.copy()
        for cb in callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.debug("Trace callback error: %s", e)


_metrics_aggregator = _MetricsAggregator()


def get_metrics() -> Dict[str, Any]:
    """Return current aggregated metrics."""
    return _metrics_aggregator.get_metrics()


def reset_metrics():
    """Reset aggregated metrics."""
    _metrics_aggregator.reset()


def register_trace_callback(callback: Callable[[Dict[str, Any]], None]):
    """Register a callback to receive trace events."""
    _metrics_aggregator.register_trace_callback(callback)


def unregister_trace_callback(callback: Callable[[Dict[str, Any]], None]):
    """Unregister a trace event callback."""
    _metrics_aggregator.unregister_trace_callback(callback)


# ============================================================================
# Custom SpanProcessor that feeds the aggregator + WS broadcast
# ============================================================================

class _AggregatingSpanProcessor(SpanProcessor):
    """Custom span processor that updates in-memory metrics and broadcasts events."""

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        try:
            latency_ms = 0.0
            if span.start_time and span.end_time:
                latency_ms = (span.end_time - span.start_time) / 1_000_000.0
            is_error = span.status.status_code == StatusCode.ERROR
            _metrics_aggregator.record_call(latency_ms, error=is_error)

            event = {
                "type": "trace_span",
                "name": span.name,
                "kind": str(span.kind),
                "latency_ms": round(latency_ms, 2),
                "error": is_error,
                "timestamp": time.time(),
                "attributes": dict(span.attributes or {}),
            }
            _metrics_aggregator.emit_trace_event(event)
        except Exception as e:
            logger.debug("Span aggregation error: %s", e)

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        pass


# ============================================================================
# TracerProvider setup
# ============================================================================

_PROVIDER_SET = False


def setup_tracing(service_name: str = "kaelis") -> TracerProvider:
    """Set up OpenTelemetry Tracing for Kaelis."""
    global _PROVIDER_SET
    if _PROVIDER_SET:
        return trace.get_tracer_provider()

    provider = TracerProvider()

    # Console exporter (batch)
    console_exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Aggregating processor for metrics + WS events
    provider.add_span_processor(_AggregatingSpanProcessor())

    trace.set_tracer_provider(provider)
    _PROVIDER_SET = True
    logger.info("OpenTelemetry tracing initialized for service=%s", service_name)
    return provider


def get_tracer(name: str = "kaelis") -> trace.Tracer:
    """Get a named tracer. Auto-initializes provider if needed."""
    if not _PROVIDER_SET:
        setup_tracing()
    return trace.get_tracer(name)


# ============================================================================
# trace_span decorator
# ============================================================================

def trace_span(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator to trace a function execution.

    Works with both sync and async functions.
    Usage:
        @trace_span("my_operation")
        def my_func():
            ...

        @trace_span("my_async_operation")
        async def my_async_func():
            ...
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__qualname__
        tracer = get_tracer("kaelis.tracing")
        _attrs = attributes or {}

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with tracer.start_as_current_span(span_name) as span:
                    for k, v in _attrs.items():
                        span.set_attribute(k, v)
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as exc:
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        span.record_exception(exc)
                        raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with tracer.start_as_current_span(span_name) as span:
                    for k, v in _attrs.items():
                        span.set_attribute(k, v)
                    try:
                        result = func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as exc:
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        span.record_exception(exc)
                        raise
            return sync_wrapper
    return decorator


# ============================================================================
# Flask auto-instrumentation (optional)
# ============================================================================

def instrument_flask(app: Any) -> bool:
    """
    Auto-instrument Flask requests if opentelemetry-instrumentation-flask is available.
    Returns True if instrumentation was applied.
    """
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        FlaskInstrumentor().instrument_app(app)
        logger.info("Flask auto-instrumentation enabled")
        return True
    except ImportError:
        logger.debug("opentelemetry-instrumentation-flask not installed, skipping Flask instrumentation")
        return False
