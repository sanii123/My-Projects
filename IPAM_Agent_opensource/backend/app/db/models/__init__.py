"""Import every model so Base.metadata is complete for Alembic autogenerate
and so cross-module string relationship() targets resolve at mapper-configure time.
"""

from app.db.models.audit_log import AuditLog
from app.db.models.message import Message, MessageRole
from app.db.models.pending_action import PendingAction, PendingActionStatus
from app.db.models.session import Session
from app.db.models.tool_call import ToolCall, ToolCallStatus

__all__ = [
    "AuditLog",
    "Message",
    "MessageRole",
    "PendingAction",
    "PendingActionStatus",
    "Session",
    "ToolCall",
    "ToolCallStatus",
]
