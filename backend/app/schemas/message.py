import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.message import MessageRole


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageRead(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
