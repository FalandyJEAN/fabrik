from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"
    REDIS_URL: str = "redis://localhost:6379"

    @property
    def async_database_url(self) -> str:
        """Convertit la DATABASE_URL synchrone vers son equivalent asynchrone."""
        url = self.DATABASE_URL
        if url.startswith("sqlite+aiosqlite://") or url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("sqlite:///"):
            return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if url.startswith("postgresql+psycopg2://"):
            return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def cors_origins(self) -> list[str]:
        """Liste des origines autorisees pour le CORS (parse depuis BACKEND_CORS_ORIGINS)."""
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
