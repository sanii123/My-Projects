# IPAM Support Agent — Architecture Document

**Author:** Sana Mazhar / Digitata Networks
**Date:** 2026-08-10
**Status:** Draft for review — revised: dropped NetCM, added IPAM backend recommendation and production DB backup/DR plan

## 1. Overview and Assumptions

This document describes the architecture for an AI support agent that answers questions about IP address management and performs read/write actions against IPAM data on a user's behalf. It follows the stack you specified:

```
Frontend -> FastAPI -> Agent Runtime -> LLM -> Tool Layer -> Business APIs -> Database -> Logging -> Monitoring
```

Locked-in decisions from our earlier conversation:

- **LLM**: local, served via Ollama. Not a hosted API — everything stays on infrastructure you control.
- **Tool Layer / IPAM Backend**: no NetCM. This is now a standalone internal agent talking to one dedicated IPAM system of record over its REST API. Recommended default is **NetBox** (self-hosted, open source, Python/Django) — see section 4.6 for the full comparison against phpIPAM and commercial DDI platforms (Infoblox, BlueCat) and why NetBox wins for this use case.
- **Database**: Postgres, with a real backup and disaster-recovery plan — see section 9. This was hand-waved in the first draft; it isn't anymore.
- **Logging**: structured JSON.
- **Monitoring**: Prometheus + Grafana.

Assumptions I'm making that you should confirm before this goes further: the agent is read-heavy with occasional write actions (e.g. reserve an IP, create a subnet) that need explicit confirmation before execution; a handful to a few dozen concurrent users, not thousands; and this runs on-prem or in a VPC you control, since "local LLM" usually means "we don't want IPAM data leaving the building." If any of that is wrong, the sizing numbers in section 7 change. I'm also assuming this is greenfield — no existing IPAM system of record you need to wrap instead of replace. If you already run Infoblox, BlueCat, or a legacy homegrown system, say so and section 4.6's recommendation flips from "stand up NetBox" to "write an adapter for what you've already got."

## 2. High-Level Architecture

```
                     ┌─────────────┐
                     │  Frontend   │  (web chat widget / internal tool UI)
                     └──────┬──────┘
                            │ HTTPS, JWT
                     ┌──────▼──────┐
                     │   FastAPI   │  auth, rate limiting, request validation,
                     │  (Gateway)  │  session management, SSE streaming out
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │Agent Runtime│  orchestration loop: build context,
                     │             │  call LLM, parse tool calls, execute,
                     │             │  loop until final answer or step limit
                     └──┬───────┬──┘
                        │       │
                 ┌──────▼──┐ ┌──▼──────────┐
                 │  Ollama │ │  Tool Layer │  registry + adapters,
                 │  (LLM)  │ │             │  schema validation,
                 └─────────┘ │             │  auth-scoping, retries
                              └──────┬──────┘
                                     │
                          ┌──────────▼──────────┐
                          │   IPAM Backend API   │  NetBox REST/GraphQL
                          │   (system of record)  │  (or Infoblox/BlueCat)
                          └──────────┬────────────┘
                                     │
                     ┌───────────────▼─────────────────┐
                     │          Postgres              │  agent state + audit trail
                     │  (agent state + audit trail)   │  (separate from IPAM's own DB)
                     └───────────────┬─────────────────┘
                                     │
                     ┌───────────────▼─────────────────┐
                     │  Backup / DR (Barman + WAL archive)│  nightly full + continuous WAL,
                     │  offsite object storage           │  PITR, tested restores
                     └───────────────┬─────────────────┘
                                     │
                     ┌───────────────▼─────────────────┐
                     │     Logging (structured JSON)    │  every layer emits
                     │     → shipped to log store       │  correlated by trace_id
                     └───────────────┬─────────────────┘
                                     │
                     ┌───────────────▼─────────────────┐
                     │   Monitoring (Prometheus/Grafana)│  latency, error rate,
                     │                                   │  tool call success,
                     │                                   │  token throughput
                     └───────────────────────────────────┘
```

Two things worth calling out about this diagram versus the stack you gave me. First, the Agent Runtime talks to both the LLM and the Tool Layer directly and loops between them — it's not a strictly linear pipeline, it's a cycle that terminates when the model stops asking for tools. Second, Logging and Monitoring aren't a downstream stage that only the database feeds — every layer (gateway, runtime, tool layer, IPAM API) emits logs and metrics independently, tied together by a trace ID. Drawing it as a single line at the bottom of the stack undersells how much you actually want visibility into the middle of that request, which is where things go wrong. Note also that Postgres here is the agent's own database, not NetBox's — NetBox (or whatever IPAM backend you pick) runs its own Postgres instance behind its own API, with its own backup story that you inherit separately, covered in section 9.

## 3. Request Lifecycle

1. User sends a message from the frontend. FastAPI authenticates the request (JWT or session cookie), attaches a `trace_id`, and validates the payload.
2. FastAPI loads (or creates) the conversation session from Postgres and hands the message plus session history to the Agent Runtime.
3. Agent Runtime builds the prompt: system instructions, tool schemas, conversation history, and the new message. Sends it to Ollama.
4. The model either answers directly or emits a tool call (e.g. `get_subnet_utilization`, `reserve_ip_address`).
5. Agent Runtime validates the tool call against its JSON schema, checks the caller's permissions for that tool, and dispatches it through the Tool Layer.
6. Tool Layer routes to the matching adapter — an HTTP client against the IPAM backend's REST API — executes with a timeout and retry policy, and returns a normalized result.
7. The result is appended to the conversation and sent back to the model, which either calls another tool or produces a final answer. Step limit (e.g. 8 tool calls per turn) prevents runaway loops.
8. Final answer streams back to the frontend over SSE. Every tool call, its arguments, its result, and the model's reasoning trace are written to Postgres as an audit record.
9. Structured logs are written at every step above with the shared `trace_id`. Metrics (latency per stage, tool success/failure, token counts) are pushed to Prometheus.

Any action that mutates IPAM state (reserving an IP, deleting a subnet entry) is treated as a two-step flow: the model proposes the action, the runtime returns it to the frontend as a confirmation card, and execution only happens once the user approves. This is not optional for an agent that can write to IPAM — a hallucinated subnet deletion is a bad Tuesday for everyone.

## 4. Component Deep Dive

### 4.1 Frontend

Not specified yet, so I'm treating it as a black box that talks to FastAPI over HTTPS and consumes an SSE or WebSocket stream for token-by-token responses, plus a REST call for the confirm/reject step on write actions. Whether this is a new chat widget or bolted onto an existing internal tool doesn't change anything below it.

### 4.2 FastAPI Gateway

Responsibilities: authentication (JWT validation against your identity provider, or session-based if this sits inside an already-authenticated internal tool), request validation via Pydantic models, rate limiting per user, session/conversation lookup, and streaming the runtime's output back to the client. It should not contain business logic or talk to the LLM or tools directly — its job is to be a thin, boring, well-tested boundary. Boring is good here; the interesting failure modes belong in the runtime and tool layer, not the gateway.

Suggested endpoints in section 5.

### 4.3 Agent Runtime

This is the orchestration loop — the part that actually makes it an "agent" rather than a chatbot with plugins. It owns:

- Context assembly: system prompt, relevant conversation history (with truncation/summarization once history gets long), and the set of tool schemas the current user is allowed to invoke.
- The tool-call loop: send to LLM, parse response, if it's a tool call validate and execute, feed the result back, repeat until a final answer or step limit.
- Guardrails: step limits, timeout on the whole turn, and the confirm-before-write gate described above.
- Permission scoping: the runtime should not expose write tools to a read-only user, full stop. That check belongs here, not in the tool implementation.

For implementation, a hand-rolled loop is entirely reasonable at this scale — you don't need LangGraph or a heavyweight agent framework to run "call model, maybe call tool, repeat." A framework earns its complexity once you have multiple agent types or need persistent multi-step workflows; a single support agent with a handful of tools doesn't need it yet, and every framework here has abandoned or half-supported features and a changelog longer than your actual code. Keep this as a plain Python loop with clean interfaces and revisit if the tool count or agent count grows.

### 4.4 LLM Layer (Ollama)

Ollama serves the model over its local OpenAI-compatible API (`/api/chat` or the `/v1/chat/completions` shim). Model choice matters more than usual here because tool calling quality varies a lot between local models — pick one that Ollama documents as function-calling capable: Llama 3.1 (8B for latency, 70B if you have the GPU memory and can tolerate slower responses), Qwen2.5, or Mistral Nemo are the current reasonable choices for structured tool use. Test tool-call reliability on your actual tool schemas before committing — a model that's great at chat can still be unreliable at emitting well-formed function calls, and that failure mode is silent until it corrupts a request to the IPAM API.

Practical notes: run Ollama on a machine with enough VRAM to hold the model plus context window without swapping to CPU (swapping is where "local LLM" quietly becomes "slower than the API you were trying to avoid"). Keep the Agent Runtime's client for Ollama behind the same interface you'd use for a hosted API, so swapping models or even swapping in a hosted fallback later is a config change, not a rewrite.

### 4.5 Tool Layer

A registry of tools, each with a JSON schema (name, description, parameters) that gets handed to the LLM, and an adapter function that actually executes it. With a single IPAM backend, adapters group by function rather than by system:

- **Read adapters**: subnet lookup, IP address lookup/search, utilization/availability queries, VLAN and VRF lookups.
- **Write adapters**: reserve/release an IP, create/delete a subnet, update a description or tag. Every one of these routes through the confirm-before-write gate in section 3 — the adapter itself should refuse to execute a write tool call that hasn't been marked approved in `pending_actions`.

Normalize every adapter's return value to a common result shape (success/failure, data, human-readable summary) so the model gets a consistent contract regardless of which endpoint answered. Each adapter call gets a timeout, a retry policy for idempotent reads (never for writes — don't blindly retry a "reserve this IP" call), and its own log line with the tool name, arguments, duration, and outcome.

### 4.6 IPAM Backend

This is the actual system of record for subnets, IP addresses, VLANs, and (optionally) DNS/DHCP — and the piece you asked me to source options for.

**NetBox — recommended default.** Open source, self-hosted, Python/Django under the hood, which matters here for two reasons: it fits the rest of your stack instead of introducing a foreign runtime, and its ecosystem (pynetbox client, custom scripts, plugins) is Python-native. REST API with token-based auth (`Authorization: Bearer nbt_<key>.<token>` on current versions), full CRUD on `/api/ipam/prefixes/`, `/api/ipam/ip-addresses/`, `/api/ipam/vlans/`, offset- and cursor-based pagination, and a read-only GraphQL API for complex queries in one round trip instead of chaining REST calls. Also gives you webhooks, which is genuinely useful here — NetBox can push a change event to your agent's FastAPI service when something changes IP state outside the agent (another admin, a script, an import), keeping the agent's world-view current without polling. Actively maintained, large community, and it is a source-of-truth tool for network infrastructure rather than a general CMDB, so its data model already matches what a support agent needs to reason about. ([NetBox REST API docs](https://netboxlabs.com/docs/netbox/integrations/rest-api/))

**phpIPAM — not recommended for this.** Also open source and has a REST API (dynamic token or static token auth, `/api/{app}/subnets/` and `/api/{app}/addresses/` endpoints), but it shows its age: encryption falls back to deprecated `mcrypt`, there's no real pagination on large result sets, and filtering is thinner than NetBox's. Fine for a small team managing IPAM by hand; a worse foundation to build a production agent's tool layer on top of. ([phpIPAM API docs](https://phpipam.net/api/api_documentation/))

**Infoblox / BlueCat — the commercial alternative.** Consider these only if you already run one (common in larger telecom/network-ops shops) or specifically need integrated DNS/DHCP/IPAM (DDI) with enterprise support contracts. Both expose REST APIs (Infoblox's WAPI, BlueCat's Address Manager API) that your Tool Layer can wrap exactly the same way as NetBox's — same adapter interface, different HTTP client underneath. The cost is licensing plus vendor lock-in; the benefit is you're not standing up new infrastructure if one is already deployed and trusted. Worth checking before you build anything: if Digitata already has one of these somewhere, wrapping it beats running NetBox in parallel as a second source of truth.

Whichever you land on, the Tool Layer talks to it over its REST API using a scoped service account, not a personal credential. Rate limits and auth token refresh belong in that adapter, not scattered through the runtime — and keeping the adapter interface identical across backends is what lets you swap NetBox for Infoblox later without touching the Agent Runtime at all.

### 4.7 Database (Postgres)

Minimum schema to support the flow above:

- `sessions` — id, user_id, created_at, last_active_at.
- `messages` — id, session_id, role (user/assistant/tool), content, created_at.
- `tool_calls` — id, message_id, tool_name, arguments (jsonb), result (jsonb), status, duration_ms, created_at.
- `pending_actions` — id, session_id, tool_name, arguments (jsonb), status (pending/approved/rejected/executed), created_at, resolved_at. This is the confirm-before-write queue.
- `audit_log` — append-only record of every IPAM-mutating action actually executed, who approved it, and when. Treat this table as write-once; if you ever need to explain to someone why a subnet got deleted, this is the table that answers it.

This is deliberately not the IPAM system of record — NetBox (or whichever backend you choose) owns that data in its own database. This Postgres instance holds conversation state and the audit trail, which is a much smaller and simpler surface than trying to mirror IPAM records locally, and it needs its own backup plan independent of whatever backup story ships with the IPAM backend — see section 9.

### 4.8 Logging

Structured JSON, one line per event, minimum fields: `timestamp`, `trace_id`, `session_id`, `layer` (gateway/runtime/llm/tool/db), `event`, `duration_ms`, `status`, and a `details` object specific to the event. Every layer writes its own logs rather than the gateway trying to log everything centrally — that's how you end up with a "logging module" that becomes its own outage. Ship to whatever aggregator you already run (Loki, ELK, or just files rotated and shipped — this doc doesn't assume one); the important part is the shared `trace_id` so you can pull every log line for one user request across all five layers in one query.

### 4.9 Monitoring (Prometheus + Grafana)

Metrics worth exposing from day one: request latency by layer (gateway, LLM call, each tool call), tool call success/failure rate by tool name, LLM token throughput and time-to-first-token, active sessions, and the size of the `pending_actions` queue (a growing queue of unapproved actions is a UX problem before it's anything else). Alert on: elevated tool error rate, Ollama response latency crossing a threshold (a strong signal you're swapping to CPU or the model's too big for the box), and any spike in rejected write actions (could mean the model is proposing bad actions, or users don't trust it — worth knowing either way).

## 5. API Contracts

```
POST   /v1/sessions                 create a new conversation session
GET    /v1/sessions/{id}             fetch session + message history
POST   /v1/sessions/{id}/messages    send a user message, stream response (SSE)
GET    /v1/sessions/{id}/pending     list pending write actions awaiting confirmation
POST   /v1/actions/{id}/approve      approve and execute a pending write action
POST   /v1/actions/{id}/reject       reject a pending write action
GET    /health                       liveness/readiness (checks Ollama + Postgres + IPAM API reachability)
```

Internal (Agent Runtime <-> Tool Layer, not exposed externally): a single `execute_tool(name, arguments, user_context) -> ToolResult` interface that every adapter implements. Keeping this interface identical across read and write adapters — and across IPAM backends — is what lets you swap NetBox for a commercial DDI platform later without touching the runtime.

## 6. Reliability and Failure Handling

- **LLM unavailable or slow**: Ollama down or overloaded should fail fast with a clear error to the user, not hang the request. Set a hard timeout on the LLM call and surface "the assistant is temporarily unavailable" rather than a spinner that never resolves.
- **Tool call failure**: reads retry with backoff (2-3 attempts, idempotent by nature); writes never auto-retry — a failed write action goes back to the model as a tool error so it can decide to ask the user or report failure, not silently retried into a duplicate reservation.
- **IPAM backend unavailable**: if the IPAM API times out or errors, the tool call fails cleanly back to the model with a typed error, not a generic exception — the model needs to know it was a backend outage, not "no such subnet," so it can tell the user rather than confidently making something up.
- **Database write failure on audit log**: this is the one write you cannot silently drop. If the audit log write fails after a mutating action executed, that needs to be a loud alert, not a swallowed exception — you now have an IPAM change with no record of it.

## 7. Scale Considerations

At the "handful to a few dozen concurrent users" scale assumed in section 1, a single Ollama instance on one GPU box, a single Postgres instance, and a couple of FastAPI/runtime replicas behind a load balancer is enough — no need to reach for a queue, a model-serving cluster, or read replicas yet. Things that change this: if concurrent load grows past what one Ollama instance can serve without queueing badly, that's when vLLM (better request batching, built for concurrency) becomes worth the operational overhead it adds over Ollama. If tool calls start dominating latency, look at parallelizing independent tool calls within a single turn rather than scaling the LLM layer. If audit/compliance requirements grow, the `audit_log` table is the first thing to move to its own durable, possibly append-only store rather than living in the same Postgres instance as session chat.

## 8. Security and Access Control

This is an agent that can touch network infrastructure records, so a few things are not optional: every tool call must be scoped to the calling user's actual permissions, not the agent's — a support agent shouldn't have a blanket service account that can do anything any IPAM API can do just because it's convenient. Write actions require explicit human confirmation, per section 3. The audit log is the accountability mechanism when something goes wrong, so it needs to be tamper-resistant (append-only, ideally with restricted write access even from the app's own service account beyond inserts). And since the LLM is local, make sure "local" actually means what you think it means — if Ollama is on a shared box, confirm no other tenant or process can read its logs or memory in a way that leaks IPAM data through the model's context.

## 9. Database Backup and Disaster Recovery

You asked for this explicitly, so it gets its own section instead of a bullet point. There are two Postgres instances in this system that both need a real backup story: the agent's own database (sessions, messages, tool calls, audit log) and NetBox's database (subnets, IPs, VLANs — the actual IPAM data). Same tooling applies to both; treat them as two backup targets, not one.

**Tool choice.** Recommend **Barman** as the default: it's maintained by EnterpriseDB, written in Python (fits the rest of this stack), supports centralized backup management if you ever run more than one Postgres instance, and pushes to cloud or local storage. Worth knowing before you commit: **pgBackRest**, long the default recommendation for this kind of setup, had its original maintainer step away and the project got archived in April 2026 — Percona has since sponsored it and continues recommending it as of this document, but that's a very recent transition and worth watching rather than betting on blind. If you're deploying primarily on Kubernetes with S3-compatible storage, **WAL-G** is the more cloud-native option and is a reasonable alternative to Barman for that specific case. Don't reach for a plain cron job running `pg_dump` for a production system that holds an audit trail of network changes — you want continuous WAL archiving, not just periodic snapshots, so recovery isn't bounded by "how much data are you willing to lose since last night's dump."

**Backup strategy:**

- **Continuous WAL archiving** to durable storage, so you get point-in-time recovery (PITR) rather than being limited to whatever the last full backup happened to capture. This is the difference between "restore to last night at 2am" and "restore to 30 seconds before someone fat-fingered a subnet delete."
- **Full backup nightly**, incremental/differential between fulls if the database size justifies it (unlikely to matter for the agent's own DB at the scale in section 7; more relevant for NetBox's DB once your IP inventory is large).
- **Retention**: a rolling PITR window (30 days is a reasonable starting point) plus weekly full backups retained longer (90 days, or whatever your compliance posture requires) for the audit log specifically — that data has a different retention need than routine chat history.
- **Offsite / off-host storage**: backups land on S3-compatible object storage physically or logically separate from wherever Postgres runs. A backup that lives on the same disk as the database it backs up is a backup in name only.
- **Encryption**: at rest in object storage and in transit during the backup/restore transfer — this is network infrastructure data, treat it accordingly.

**High availability, separate from backup.** Backups protect against data loss; they don't protect against downtime while you restore from one. If uptime matters here, add Postgres streaming replication to a standby replica that can be promoted on primary failure — this is a different mechanism from Barman/WAL-G/pgBackRest and solves a different problem. At the scale assumed in section 7, decide deliberately whether you need this yet or whether "restore from backup, accept some downtime" is an acceptable trade for now; don't build HA you don't need.

**Verification — the step everyone skips.** A backup you haven't test-restored is a hypothesis, not a backup. Schedule an automated restore drill (weekly is reasonable) that spins up a throwaway Postgres instance from the latest backup, runs a checksum or row-count sanity check against known data, and alerts if the restore fails or the check doesn't match. This is the single highest-leverage thing in this section — most backup failures are discovered at restore time, which is the worst possible time to discover them.

**Monitoring hook.** Feed backup job success/failure, last-successful-backup timestamp, and restore-drill results into the same Prometheus/Grafana setup from section 4.9. Alert if the last successful backup is older than your RPO tolerance (e.g. no successful backup in 25 hours when you run nightly) — a silently failing backup job is worse than no backup job, because it looks fine on the dashboard right up until you need it.

Sources: [pgBackRest is no longer maintained](https://lwn.net/Articles/1069951/), [Percona: pgBackRest is archived, what now?](https://percona.community/blog/2026/04/28/pgbackrest-is-archived-what-now/), [Top open-source PostgreSQL backup tools (Bytebase)](https://www.bytebase.com/blog/top-open-source-postgres-backup-solution/), [NetBox REST API overview](https://netboxlabs.com/docs/netbox/integrations/rest-api/), [phpIPAM API documentation](https://phpipam.net/api/api_documentation/).

## 10. Trade-off Analysis

**Local LLM (Ollama) vs. hosted API**: you get data control and no per-token cost, at the price of managing your own GPU capacity and accepting that local models are currently behind frontier hosted models on tool-calling reliability and complex reasoning. For an IPAM support agent with a bounded, well-defined tool set, this is a reasonable trade — the task doesn't need frontier reasoning, it needs reliable structured output on a small number of well-specified functions.

**NetBox (open source) vs. commercial DDI (Infoblox/BlueCat)**: NetBox costs nothing to license and fits the Python-first stack, but you own its uptime, upgrades, and backups entirely yourself. Commercial DDI platforms cost real money and add vendor lock-in, but come with support contracts and, if already deployed at Digitata, zero new infrastructure to stand up. Default to NetBox for a greenfield build; default to wrapping what already exists if something already exists.

**Barman/WAL-G vs. pg_dump on a cron job**: WAL-based continuous archiving costs more setup than a nightly dump script, and it's the difference between losing a day of audit trail and losing thirty seconds of it. Not a close call for a system whose entire job is being the record of what changed on the network.

**Hand-rolled agent loop vs. an agent framework**: less abstraction to fight, more code you own. Revisit if you end up needing multiple agent types, persistent long-running workflows, or a plugin ecosystem of tools beyond what one team maintains.

**Confirm-before-write vs. autonomous writes**: slower for the user, and the right call for anything touching production network config. An agent that can silently delete a subnet because a token got sampled wrong is not a feature.

## 11. Open Decisions

These need your input before implementation starts:

- Confirm this is greenfield — no existing IPAM system of record at Digitata that this should wrap instead of NetBox. This is the single biggest fork in the whole document.
- Which Ollama model, decided by testing tool-call reliability against your actual IPAM tool schemas, not by benchmark leaderboards.
- Backup tool: Barman (recommended), pgBackRest (mature but recently orphaned, now Percona-sponsored), or WAL-G (if this ends up Kubernetes/S3-native) — pick one and build the restore drill from day one, not after the first incident.
- Identity provider for FastAPI auth — does this integrate with existing SSO, or is it standalone?
- Whether "frontend" means a new chat widget or an addition to an existing internal tool.
- Retention policy for the `audit_log` and `messages` tables — this is as much a compliance question as an engineering one.
- Whether you need Postgres HA (streaming replication + failover) now, or whether "restore from backup, accept some downtime" is acceptable at current scale.
