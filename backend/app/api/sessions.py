"""Session + message endpoints. docs/architecture.md sections 3 and 5."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import UserContext, get_current_user, get_db
from app.db.models.message import Message, MessageRole
from app.db.models.pending_action import PendingAction, PendingActionStatus
from app.db.models.session import Session as SessionModel
from app.db.session import AsyncSessionLocal
from app.runtime.agent import AgentRuntime
from app.schemas.action import PendingActionRead
from app.schemas.message import MessageCreate
from app.schemas.session import SessionDetail, SessionRead

router = APIRouter()
runtime = AgentRuntime()


@router.post("/sessions", response_model=SessionRead)
async def create_session(
    user: UserContext = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> SessionModel:
    session = SessionModel(user_id=user.user_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionModel:
    return await _get_owned_session(session_id, user, db)


@router.post("/sessions/{session_id}/messages")
async def post_message(
    session_id: uuid.UUID,
    body: MessageCreate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    session = await _get_owned_session(session_id, user, db)
    db.add(Message(session_id=session.id, role=MessageRole.USER, content=body.content))
    await db.commit()

    async def event_stream() -> AsyncGenerator[dict, None]:
        # Deliberately a fresh DB session, not the request-scoped `db` above:
        # that dependency's cleanup can run before this generator - which
        # keeps going while the SSE response streams - is finished with it.
        async with AsyncSessionLocal() as turn_db:
            async for chunk in runtime.handle_turn(session_id=session.id, user=user, db=turn_db):
                yield {"event": "token", "data": chunk}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_stream())


@router.get("/sessions/{session_id}/pending", response_model=list[PendingActionRead])
async def list_pending(
    session_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PendingAction]:
    await _get_owned_session(session_id, user, db)
    result = await db.execute(
        select(PendingAction).where(
            PendingAction.session_id == session_id, PendingAction.status == PendingActionStatus.PENDING
        )
    )
    return list(result.scalars().all())


async def _get_owned_session(session_id: uuid.UUID, user: UserContext, db: AsyncSession) -> SessionModel:
    session = await db.get(SessionModel, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
