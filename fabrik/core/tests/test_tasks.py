"""
Tests pour le module tasks. Ne necessite PAS Redis : on appelle les fonctions
de tache directement (sans passer par la queue).

Pour tester l'integration reelle avec Redis, lance le worker manuellement
(docker compose up -d redis ; python worker.py) puis ecris des tests qui
font enqueue_job + wait_for_result.
"""
from src.tasks import example_task, WorkerSettings


async def test_example_task_returns_processed_string():
    result = await example_task({}, "hello")
    assert result == "processed: hello"


async def test_worker_settings_has_functions():
    assert example_task in WorkerSettings.functions
    assert WorkerSettings.max_jobs > 0
    assert WorkerSettings.job_timeout > 0


async def test_health_check_reports_background_tasks(client):
    # En mode test (ASGITransport), lifespan ne tourne pas donc
    # arq_pool est absent -> background_tasks: false. Le endpoint reste OK.
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["background_tasks"] is False
