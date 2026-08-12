"""Shared FastAPI dependencies for the API layer - one import site so routers
don't reach into app.core / app.db directly.
"""

from app.core.security import UserContext, get_current_user, require_write_scope
from app.db.session import get_db

__all__ = ["UserContext", "get_current_user", "require_write_scope", "get_db"]
