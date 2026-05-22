from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from src.core.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
url = settings.async_database_url

if is_sqlite:
    engine = create_async_engine(url, connect_args={"check_same_thread": False})
else:
    engine = create_async_engine(url, pool_size=20, max_overflow=0, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
