"""
Background tasks (ARQ + Redis).

Pour lancer le worker :
    python worker.py                    # depuis la racine du projet
    # OU
    arq src.tasks.WorkerSettings

Pour enqueue depuis une route :
    from src.tasks import get_arq

    @router.post("/foo")
    async def foo(arq = Depends(get_arq)):
        job = await arq.enqueue_job("example_task", "hello")
        return {"job_id": job.job_id}
"""
import logging
from typing import Any

from arq.connections import ArqRedis, RedisSettings
from fastapi import Depends, HTTPException, Request, status

from src.core.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  TES TACHES -- ajoute les ici et n'oublie pas WorkerSettings.functions
# ═══════════════════════════════════════════════════════════════════════════

async def example_task(ctx: dict, message: str) -> str:
    """Tache exemple : remplace par tes vraies taches lourdes."""
    logger.info("example_task : %s", message)
    return f"processed: {message}"


# ═══════════════════════════════════════════════════════════════════════════
#  DEPENDANCE FastAPI pour enqueue depuis les routes
# ═══════════════════════════════════════════════════════════════════════════

async def get_arq(request: Request) -> ArqRedis:
    """
    Dependance FastAPI : Depends(get_arq) -> pool Redis pour enqueue_job().
    Renvoie 503 si Redis n'est pas joignable (degradation gracieuse).
    """
    pool = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background tasks indisponibles (Redis non connecte). "
                   "Lance Redis : docker compose up -d redis",
        )
    return pool


# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION DU WORKER (lue par `arq src.tasks.WorkerSettings`)
# ═══════════════════════════════════════════════════════════════════════════

class WorkerSettings:
    """
    Configuration du worker ARQ.
    Lance avec : python worker.py (ou : arq src.tasks.WorkerSettings)
    """
    functions: list = [example_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs: int = 10
    job_timeout: int = 300        # 5 minutes
    keep_result: int = 3600       # garde les resultats 1h
    poll_delay: float = 0.5

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        logger.info("ARQ worker demarre (max_jobs=%d)", WorkerSettings.max_jobs)

    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        logger.info("ARQ worker arrete")
