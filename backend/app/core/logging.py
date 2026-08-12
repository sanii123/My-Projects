"""Structured JSON logging. docs/architecture.md section 4.8.

Every layer (gateway/runtime/llm/tool/db) gets its own logger via
get_logger(layer) and writes its own log lines - no central "logging module"
that tries to log on other layers' behalf. The shared `trace_id`, bound per
request via contextvars in the gateway middleware (app/main.py), is what lets
you pull every line for one request across all layers.
"""

import logging
import sys

import structlog

from app.core.config import settings


def _level() -> int:
    return getattr(logging, settings.log_level.upper(), logging.INFO)


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=_level())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_level()),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(layer: str):
    """layer: one of gateway/runtime/llm/tool/db, per section 4.8."""
    return structlog.get_logger().bind(layer=layer)


def bind_request_context(*, trace_id: str, session_id: str | None = None) -> None:
    structlog.contextvars.clear_contextvars()
    bound = {"trace_id": trace_id}
    if session_id:
        bound["session_id"] = session_id
    structlog.contextvars.bind_contextvars(**bound)
