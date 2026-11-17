import os
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Force testing environment before importing settings/app
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AUDIT_ANCHOR_MODE"] = "mock"

from app.core.rate_limit import reset_rate_limiter
from app.db.base import Base
import app.models  # noqa: F401
from app.db.session import AsyncSessionLocal, engine as app_engine
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_test_database() -> AsyncGenerator[None, None]:
    """Ensure all 16 tables are created in the shared in-memory test database before each test."""
    reset_rate_limiter()
    async with app_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with app_engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys = OFF;")
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an async test client for the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an active AsyncSession bound to the shared test database."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def test_storage():
    """Yield a fresh InMemoryStorageAdapter for testing without external R2/MinIO dependencies."""
    from app.storage.adapter import InMemoryStorageAdapter, set_storage_adapter
    adapter = InMemoryStorageAdapter(bucket_name="test-vault")
    set_storage_adapter(adapter)
    yield adapter
    set_storage_adapter(None)
