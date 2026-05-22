import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import uvicorn

from arq import create_pool
from arq.connections import RedisSettings

from src.users.router import router as users_router
from src.admin.router import router as admin_router
from src.database import engine, Base
from src.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cree les tables au demarrage (utile en dev ; en prod, prefere Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Pool Redis pour ARQ (background tasks)
    # Si Redis est down, l'API marche quand meme : les routes qui veulent
    # enqueue renvoient 503 (voir src/tasks.py:get_arq).
    # asyncio.wait_for(timeout=2) protege contre un hang (Redis injoignable
    # mais TCP qui ne fail pas vite, ex: derriere un firewall qui drop).
    app.state.arq_pool = None
    try:
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        # Force un conn_timeout court pour fail-fast en CI / dev sans Redis
        redis_settings.conn_timeout = 2
        app.state.arq_pool = await asyncio.wait_for(
            create_pool(redis_settings),
            timeout=3.0,
        )
        logger.info("ARQ pool connecte a %s", settings.REDIS_URL)
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("Redis indisponible (%s) -- background tasks desactives",
                       type(e).__name__)

    yield

    if app.state.arq_pool is not None:
        await app.state.arq_pool.close()
    await engine.dispose()


app = FastAPI(title="${title}", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/admin/static", StaticFiles(directory="src/admin/static"), name="admin_static")

app.include_router(users_router)
app.include_router(admin_router)

# ── Tes modules ici ──────────────────────────────────────────────────────────
# from src.videos.router import router as videos_router
# app.include_router(videos_router)
# (les modules sont detectes automatiquement dans l'admin via Base.registry)

@app.get("/")
async def health_check():
    arq_pool = getattr(app.state, "arq_pool", None)
    return {
        "status": "ok",
        "project": "${title}",
        "background_tasks": arq_pool is not None,
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=${port}, reload=True)
