# IPAM Support Agent

An internal AI agent for IP address management. Answers questions about subnets, IPs, and VLANs, and can perform write actions (reserve/release an IP, create a subnet) against your IPAM system — with a human confirmation gate in front of anything that mutates network state, because nobody wants to explain a hallucinated subnet delete to their team lead.

Runs entirely on infrastructure you control: local LLM via Ollama, no data leaving the building.

## Stack

```
Frontend -> FastAPI -> Agent Runtime -> Ollama (LLM) -> Tool Layer -> NetBox (IPAM API) -> Postgres -> Logging -> Monitoring
```

| Layer | Choice |
|---|---|
| LLM | Ollama, local (Llama 3.1 / Qwen2.5 — tool-calling capable) |
| IPAM backend | NetBox (self-hosted, REST + GraphQL) |
| Database | Postgres — agent state, tool call log, audit trail |
| Backup | Barman, continuous WAL archiving, PITR, scheduled restore drills |
| Logging | Structured JSON, correlated by `trace_id` |
| Monitoring | Prometheus + Grafana |

Full design rationale and trade-offs: see [`docs/architecture.md`](docs/architecture.md).

## Why the confirmation gate

Any tool call that mutates IPAM state is proposed by the model, then held in `pending_actions` until a human approves it. Reads run freely. This is not configurable per environment — it's the whole point of the audit trail.

## Status

Architecture drafted; initial scaffold in place (FastAPI gateway, Agent Runtime loop, Tool Layer over NetBox, DB schema + migration, Docker Compose stack). Business logic is a working skeleton, not production-hardened - see the TODOs in `backend/app/api/auth.py` and `scripts/restore_drill.sh` in particular. Open decisions (Ollama model choice, backup tool, SSO integration, frontend target, retention policy, Postgres HA) are tracked in the architecture doc, section 11.

## Getting started

Requires [`uv`](https://docs.astral.sh/uv/) and [Docker](https://docs.docker.com/get-docker/) (neither is installed yet on a fresh machine - install both first).

```bash
cp .env.example .env        # fill in secrets before running anything for real

# Bring up Postgres, NetBox, Ollama, Prometheus, Grafana, and the backend itself
docker compose --env-file .env -f docker/docker-compose.yml up -d

# Pull a tool-calling-capable model into the Ollama container (see architecture doc 4.4)
docker exec -it ipam-agent-ollama-1 ollama pull llama3.1:8b

# Apply the DB schema (sessions/messages/tool_calls/pending_actions/audit_log)
cd backend && uv run alembic upgrade head

# Or run the backend outside Docker for faster iteration:
uv sync
uv run uvicorn backend.app.main:app --reload
```

Then hit `GET /health` to confirm Postgres/Ollama/NetBox are all reachable, and `/docs` for interactive Swagger. `POST /v1/auth/token` (any username, dev-only - see the TODO in `backend/app/api/auth.py`) issues a JWT for the rest of the API.

Run tests with `uv run pytest` from the repo root.

## License

TBD.
