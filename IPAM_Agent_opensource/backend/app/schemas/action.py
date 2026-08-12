import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.pending_action import PendingActionStatus


class PendingActionRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    tool_name: str
    arguments: dict
    status: PendingActionStatus
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
