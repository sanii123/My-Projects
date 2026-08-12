"""Write adapters over NetBox. docs/architecture.md section 4.5.

These are only ever meant to run after a human has approved the matching
PendingAction row:

  1. The model calls one of these tool names during a turn.
  2. app/runtime/agent.py sees `is_write=True` on the tool and does NOT call
     the handler - it creates a `pending_actions` row instead and tells the
     model (and therefore the user) the action is queued for confirmation.
  3. A human approves via POST /v1/actions/{id}/approve (app/api/actions.py),
     which is the only caller that invokes these handlers directly, and only
     after re-checking the row's status is APPROVED.

As defense in depth against something calling a handler directly and
skipping that flow, every handler here still refuses to run unless
`_pending_action_id` is present in arguments - only api/actions.py sets it,
and only post-approval. Never auto-retry any of these on failure (section 6):
a failed write goes back to the model as an error, it is not silently
retried into a duplicate reservation.
"""

from typing import Any

from app.core.security import UserContext
from app.tools.base import Tool, ToolResult, registry
from app.tools.netbox_client import NetBoxNotFoundError, NetBoxUnavailableError, netbox


def _require_approval(arguments: dict[str, Any]) -> ToolResult | None:
    if not arguments.get("_pending_action_id"):
        return ToolResult(
            success=False,
            error="not_approved",
            summary="This action has not been approved yet and cannot execute.",
        )
    return None


async def reserve_ip_address(arguments: dict[str, Any], _user: UserContext) -> ToolResult:
    if (refusal := _require_approval(arguments)) is not None:
        return refusal
    try:
        created = await netbox.post(
            "/api/ipam/ip-addresses/",
            json={
                "address": arguments["address"],
                "status": "active",
                "description": arguments.get("description", ""),
            },
        )
    except NetBoxUnavailableError as exc:
        return ToolResult(success=False, error="backend_unavailable", summary=str(exc))
    return ToolResult(success=True, data=created, summary=f"Reserved {arguments['address']}")


async def release_ip_address(arguments: dict[str, Any], _user: UserContext) -> ToolResult:
    if (refusal := _require_approval(arguments)) is not None:
        return refusal
    try:
        existing = await netbox.get("/api/ipam/ip-addresses/", params={"address": arguments["address"]})
        results = existing.get("results", [])
        if not results:
            return ToolResult(success=False, error="not_found", summary=f"{arguments['address']} is not allocated")
        await netbox.delete(f"/api/ipam/ip-addresses/{results[0]['id']}/")
    except NetBoxNotFoundError:
        return ToolResult(success=False, error="not_found", summary=f"{arguments['address']} is not allocated")
    except NetBoxUnavailableError as exc:
        return ToolResult(success=False, error="backend_unavailable", summary=str(exc))
    return ToolResult(success=True, summary=f"Released {arguments['address']}")


async def create_subnet(arguments: dict[str, Any], _user: UserContext) -> ToolResult:
    if (refusal := _require_approval(arguments)) is not None:
        return refusal
    try:
        created = await netbox.post(
            "/api/ipam/prefixes/",
            json={"prefix": arguments["prefix"], "description": arguments.get("description", "")},
        )
    except NetBoxUnavailableError as exc:
        return ToolResult(success=False, error="backend_unavailable", summary=str(exc))
    return ToolResult(success=True, data=created, summary=f"Created subnet {arguments['prefix']}")


registry.register(
    Tool(
        name="reserve_ip_address",
        description="Reserve/allocate a specific IP address in NetBox. Requires human confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "IP address, e.g. 10.0.0.5"},
                "description": {"type": "string"},
            },
            "required": ["address"],
        },
        handler=reserve_ip_address,
        is_write=True,
        retryable=False,
    )
)
registry.register(
    Tool(
        name="release_ip_address",
        description="Release a previously reserved IP address in NetBox. Requires human confirmation.",
        parameters={
            "type": "object",
            "properties": {"address": {"type": "string"}},
            "required": ["address"],
        },
        handler=release_ip_address,
        is_write=True,
        retryable=False,
    )
)
registry.register(
    Tool(
        name="create_subnet",
        description="Create a new subnet/prefix in NetBox. Requires human confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "prefix": {"type": "string", "description": "CIDR, e.g. 10.1.0.0/24"},
                "description": {"type": "string"},
            },
            "required": ["prefix"],
        },
        handler=create_subnet,
        is_write=True,
        retryable=False,
    )
)
