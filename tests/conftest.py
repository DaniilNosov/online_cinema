from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.database.base import Base
from src.database.models.accounts import User, UserGroup, UserGroupEnum
from src.database.session import get_db
from src.main import app
from src.security.hash import hash_password
from src.security.jwt import create_access_token
from src.services.orders import _processed_stripe_events

# In-memory SQLite database for fast, isolated testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create all database tables before each test and drop them afterwards."""
    _processed_stripe_events.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session for tests."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def mock_email_sending(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Mock SMTP email sending globally so tests do not require MailHog."""
    mock_send = AsyncMock()
    monkeypatch.setattr("src.notifications.emails.send_email", mock_send)
    monkeypatch.setattr("src.services.accounts.send_email", mock_send)
    monkeypatch.setattr("src.services.orders.send_email", mock_send)
    return mock_send


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with overridden database dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict:
    """Create an active ADMIN user and return authorization headers."""
    for role in UserGroupEnum:
        db_session.add(UserGroup(name=role))
    await db_session.flush()

    admin_group = (
        await db_session.execute(UserGroup.__table__.select().where(UserGroup.name == UserGroupEnum.ADMIN))
    ).first()

    admin_user = User(
        email="admin@cinema.local",
        hashed_password=hash_password("AdminPass123"),
        is_active=True,
        group_id=admin_group.id,
    )
    db_session.add(admin_user)
    await db_session.commit()
    await db_session.refresh(admin_user)

    token = create_access_token(
        {
            "sub": str(admin_user.id),
            "email": admin_user.email,
            "role": "ADMIN",
            "pwd_fgp": admin_user.hashed_password[-16:],
        }
    )
    return {"Authorization": f"Bearer {token}"}
