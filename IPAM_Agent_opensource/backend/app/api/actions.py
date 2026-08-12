"""POST /v1/actions/{id}/approve and /reject. docs/architecture.md sections 3 and 5.

`approve` is the only call site that ever invokes a write tool's handler
directly with `_pending_action_id` set - see app/tools/write_tools.py for
why that matters.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, get_current_user, get_db, require_write_scope
from app.core.logging import get_logger
from app.db.models.audit_log import AuditLog
from app.db.models.pending_action import PendingAction, PendingActionStatus
from app.db.models.session import Session as SessionModel
from app.tools.base import registry

router = APIRouter()
logger = get_logger("tool")


@router.post("/actions/{action_id}/approve")
async def approve_action(
    action_id: uuid.UUID,
    user: UserContext = Depends(require_write_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pending = await _get_owned_pending(action_id, user, db)
    if pending.status != PendingActionStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Action is already {pending.status.value}")

    pending.status = PendingActionStatus.APPROVED
    await db.flush()

    # The only place `_pending_action_id` gets injected - write_tools.py
    # handlers refuse to execute without it.
    arguments = {**pending.arguments, "_pending_action_id": str(pending.id)}
    result = await registry.execute(pending.tool_name, arguments, user)

    pending.status = PendingActionStatus.EXECUTED if result.success else PendingActionStatus.PENDING
    pending.resolved_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            pending_action_id=pending.id,
            tool_name=pending.tool_name,
            arguments=pending.arguments,
            result=result.to_dict(),
            executed_by=user.user_id,
            approved_by=user.user_id,
        )
    )

    try:
        await db.commit()
    except Exception:
        # Section 6: a failed audit-log write after a mutating action executed
        # must be loud, never swallowed - replace with a real page/alert, not
        # just this log line, before this touches production data.
        logger.error(
            "audit_log.write_failed", pending_action_id=str(pending.id), tool_name=pending.tool_name
        )
        raise

    if not result.success:
        raise HTTPException(status_code=502, detail=result.summary or "Action failed to execute")

    return {"status": "executed", "result": result.to_dict()}


@router.post("/actions/{action_id}/reject")
async def reject_action(
    action_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pending = await _get_owned_pending(action_id, user, db)
    if pending.status != PendingActionStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Action is already {pending.status.value}")

    pending.status = PendingActionStatus.REJECTED
    pending.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "rejected"}


async def _get_owned_pending(action_id: uuid.UUID, user: UserContext, db: AsyncSession) -> PendingAction:
    pending = await db.get(PendingAction, action_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Pending action not found")
    session = await db.get(SessionModel, pending.session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Pending action not found")
    return pending
