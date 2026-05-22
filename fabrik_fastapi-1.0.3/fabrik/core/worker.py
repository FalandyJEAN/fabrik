"""
Lance le worker ARQ qui consomme les taches de la queue Redis.

Usage :
    python worker.py

Pre-requis : Redis demarre.
    docker compose up -d redis     # rapide
    # OU : redis-server localement

Equivalent CLI : arq src.tasks.WorkerSettings
"""
from arq.worker import run_worker
from src.tasks import WorkerSettings


if __name__ == "__main__":
    run_worker(WorkerSettings)
