"""
Fixtures de tests : DB SQLite en memoire isolee + client HTTP async.
Chaque test recoit une base vide grace au dependency_override de get_db.
"""
import os

# Forcer un environnement de test AVANT d'importer settings
os.environ.setdefault("SECRET_KEY", "test-secret-do-not-use-in-prod")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from main import app
from src.database import Base, get_db


@pytest_asyncio.fixture
async def test_engine():
    """Une base SQLite in-memory recreee a chaque test (isolation totale)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Session AsyncSession pour seeder ou inspecter la DB dans un test."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    """Client HTTP async qui appelle l'app FastAPI avec la DB de test."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
