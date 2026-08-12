"""Shared pytest fixtures. pytest-asyncio runs in "auto" mode (pyproject.toml),
so async fixtures and async def test_* functions need no extra markers.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
