"""GET /health - liveness/readiness. docs/architecture.md section 5.

Checks the three things this service cannot function without: Postgres,
Ollama, and the NetBox IPAM API.
"""

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.health import DependencyStatus, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    deps: list[DependencyStatus] = []

    try:
        await db.execute(text("SELECT 1"))
        deps.append(DependencyStatus(name="postgres", ok=True))
    except Exception as exc:  # noqa: BLE001 - health check: report every failure mode, don't hide any
        deps.append(DependencyStatus(name="postgres", ok=False, detail=str(exc)))

    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            deps.append(DependencyStatus(name="ollama", ok=resp.status_code == 200))
        except httpx.HTTPError as exc:
            deps.append(DependencyStatus(name="ollama", ok=False, detail=str(exc)))

        try:
            resp = await client.get(f"{settings.netbox_url}/api/status/")
            deps.append(DependencyStatus(name="netbox", ok=resp.status_code == 200))
        except httpx.HTTPError as exc:
            deps.append(DependencyStatus(name="netbox", ok=False, detail=str(exc)))

    overall = "ok" if all(d.ok for d in deps) else "degraded"
    return HealthResponse(status=overall, dependencies=deps)
