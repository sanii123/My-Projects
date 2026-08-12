import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.message import MessageRead


class SessionRead(BaseModel):
    id: uuid.UUID
    user_id: str
    created_at: datetime
    last_active_at: datetime

    model_config = {"from_attributes": True}


class SessionDetail(SessionRead):
    messages: list[MessageRead] = []
