"""Async engine/session factory for the agent's own Postgres database.

This is NOT NetBox's database — see docs/architecture.md section 4.7 and 9.
This instance holds sessions/messages/tool_calls/pending_actions/audit_log only.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields one session per request, always closed."""
    async with AsyncSessionLocal() as session:
        yield session
