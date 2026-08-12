"""Read adapters over NetBox. docs/architecture.md section 4.5.

Reads are retryable (idempotent by nature) - the retry policy itself lives in
the caller (app/runtime/agent.py), not here; these functions just make one
call and normalize the result into a ToolResult.
"""

from typing import Any

from app.core.security import UserContext
from app.tools.base import Tool, ToolResult, registry
from app.tools.netbox_client import NetBoxNotFoundError, NetBoxUnavailableError, netbox


async def get_subnet_utilization(arguments: dict[str, Any], _user: UserContext) -> ToolResult:
    prefix = arguments["prefix"]
    try:
        data = await netbox.get("/api/ipam/prefixes/", params={"prefix": prefix})
    except NetBoxNotFoundError:
        return ToolResult(success=False, error="not_found", summary=f"No subnet found matching {prefix}")
    except NetBoxUnavailableError as exc:
        return ToolResult(success=False, error="backend_unavailable", summary=str(exc))

    results = data.get("results", [])
    if not results:
        return ToolResult(success=False, error="not_found", summary=f"No subnet found matching {prefix}")

    prefix_obj = results[0]
    try:
        available = await netbox.get(f"/api/ipam/prefixes/{prefix_obj['id']}/available-ips/")
    except NetBoxUnavailableError as exc:
        return ToolResult(success=False, error="backend_unavailable", summary=str(exc))

    count = len(available) if isinstance(available, list) else None
    summary = f"{prefix} has at least {count} available IPs" if count is not None else f"Fetched {prefix}"
    return ToolResult(success=True, data={"prefix": prefix_obj, "available_sample": (available or [])[:5]}, summary=summary)


async def search_ip_address(arguments: dict[str, Any], _user: UserContext) -> ToolResult:
    address = arguments["address"]
    try:
        data = await netbox.get("/api/ipam/ip-addresses/", params={"address": address})
    except NetBoxUnavailableError as exc:
        return ToolResult(success=False, error="backend_unavailable", summary=str(exc))

    results = data.get("results", [])
    if not results:
        return ToolResult(success=True, data=[], summary=f"{address} is not currently allocated")
    return ToolResult(success=True, data=results, summary=f"Found {len(results)} record(s) for {address}")


async def list_vlans(arguments: dict[str, Any], _user: UserContext) -> ToolResult:
    params = {k: v for k, v in arguments.items() if v}
    try:
        data = await netbox.get("/api/ipam/vlans/", params=params)
    except NetBoxUnavailableError as exc:
        return ToolResult(success=False, error="backend_unavailable", summary=str(exc))

    results = data.get("results", [])
    return ToolResult(success=True, data=results, summary=f"Found {len(results)} VLAN(s)")


registry.register(
    Tool(
        name="get_subnet_utilization",
        description="Look up a subnet by CIDR prefix and report its available IP capacity.",
        parameters={
            "type": "object",
            "properties": {"prefix": {"type": "string", "description": "CIDR, e.g. 10.0.0.0/24"}},
            "required": ["prefix"],
        },
        handler=get_subnet_utilization,
        is_write=False,
    )
)
registry.register(
    Tool(
        name="search_ip_address",
        description="Look up whether a specific IP address is allocated and to what.",
        parameters={
            "type": "object",
            "properties": {"address": {"type": "string", "description": "IP address, e.g. 10.0.0.5"}},
            "required": ["address"],
        },
        handler=search_ip_address,
        is_write=False,
    )
)
registry.register(
    Tool(
        name="list_vlans",
        description="List VLANs, optionally filtered by name or VLAN group.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}, "group": {"type": "string"}},
        },
        handler=list_vlans,
        is_write=False,
    )
)
