"""FastAPI gateway entrypoint. docs/architecture.md section 4.2.

Thin and boring on purpose: auth, request validation, session lookup,
streaming the runtime's output back out. No business logic here - that
lives in app.runtime and app.tools.
"""

import time
import uuid

from fastapi import FastAPI, Request
from prometheus_client import make_asgi_app

from app.api import actions, auth, health, sessions
from app.core.logging import bind_request_context, configure_logging, get_logger
from app.core.metrics import REQUEST_LATENCY

configure_logging()
logger = get_logger("gateway")

app = FastAPI(title="IPAM Support Agent", version="0.1.0")


@app.middleware("http")
async def trace_and_log(request: Request, call_next):
    """Every request gets a trace_id (client-supplied or generated), bound
    into logging context for the duration of the request - section 4.8.
    """
    trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
    bind_request_context(trace_id=trace_id)
    start = time.monotonic()
    logger.info("request.start", method=request.method, path=request.url.path)

    response = await call_next(request)

    duration_ms = (time.monotonic() - start) * 1000
    REQUEST_LATENCY.labels(layer="gateway").observe(duration_ms / 1000)
    logger.info(
        "request.end",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    response.headers["x-trace-id"] = trace_id
    return response


app.include_router(auth.router, prefix="/v1", tags=["auth"])
app.include_router(sessions.router, prefix="/v1", tags=["sessions"])
app.include_router(actions.router, prefix="/v1", tags=["actions"])
app.include_router(health.router, tags=["health"])
app.mount("/metrics", make_asgi_app())
