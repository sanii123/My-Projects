"""Prometheus metrics. docs/architecture.md section 4.9.

Exposed at /metrics (mounted in main.py) and scraped by
docker/prometheus/prometheus.yml. Naming follows the "day one" list from the
architecture doc: latency by layer, tool success/failure by tool name, LLM
token throughput and time-to-first-token, active sessions, pending_actions
queue size.
"""

from prometheus_client import Counter, Gauge, Histogram

REQUEST_LATENCY = Histogram(
    "ipam_agent_request_latency_seconds",
    "Request latency by layer",
    ["layer"],
)

TOOL_CALL_TOTAL = Counter(
    "ipam_agent_tool_call_total",
    "Tool call outcomes by tool name and status",
    ["tool_name", "status"],
)

LLM_TOKENS_TOTAL = Counter(
    "ipam_agent_llm_tokens_total",
    "LLM token throughput",
    ["direction"],  # prompt | completion
)

LLM_TIME_TO_FIRST_TOKEN = Histogram(
    "ipam_agent_llm_time_to_first_token_seconds",
    "Time to first token from Ollama",
)

ACTIVE_SESSIONS = Gauge("ipam_agent_active_sessions", "Number of active conversation sessions")

PENDING_ACTIONS_QUEUE_SIZE = Gauge(
    "ipam_agent_pending_actions_queue_size",
    "Unapproved write actions awaiting confirmation - a growing queue is a UX problem first (section 4.9)",
)
