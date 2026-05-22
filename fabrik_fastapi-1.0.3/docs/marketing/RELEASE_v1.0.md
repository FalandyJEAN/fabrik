# Fabrik v1.0.1 — First stable PyPI release

<p align="center">
  <img src="https://raw.githubusercontent.com/FalandyJEAN/fabrik/main/docs/assets/logo.png" alt="Fabrik logo" width="160" />
</p>

> **En 60 secondes : un backend FastAPI production-ready.**
> Auth JWT, admin UI auto-decouverte, background tasks (ARQ), tests isoles,
> migrations Alembic, CORS strict, responsive mobile.

## Installation

```bash
pip install fabrik-fastapi
```

## Demarrer en 60 secondes

```bash
fabrik new mon-api
cd mon-api
venv\Scripts\activate                 # ou: source venv/bin/activate
python create_superuser.py
python -m uvicorn main:app --reload
```

Ouvre :
- **Admin UI** : http://127.0.0.1:8000/admin
- **Swagger** : http://127.0.0.1:8000/docs

## Highlights

| Domaine | Choix par defaut |
|---------|------------------|
| Stack | FastAPI 0.115+ · SQLAlchemy 2.0 **async** · asyncpg / aiosqlite |
| Auth | JWT (access + refresh) · bcrypt · super-admin via `create_superuser.py` |
| Admin UI | Auto-decouverte des modeles · multi-search · bulk delete · CSV export · responsive (drawer mobile) |
| Background tasks | ARQ + Redis · degradation gracieuse (l'API marche meme sans Redis) |
| Tests | pytest-asyncio · DB SQLite in-memory isolee par test |
| Migrations | Alembic auto-wirees a chaque `fabrik add` |
| Securite | CORS strict (`BACKEND_CORS_ORIGINS`) · SECRET_KEY 256 bits generee par projet |

## Les 4 commandes

| Commande | Effet |
|----------|-------|
| `fabrik new <nom>` | Genere un projet complet (venv + deps + migration initiale) |
| `fabrik add <module>` | Ajoute un module CRUD (auto-wire `main.py` + `alembic/env.py` + migration + tests) |
| `fabrik upgrade` | Met a jour un projet existant a la derniere version (patches idempotents) |
| `fabrik test-self` | Meta-test : verifie que le scaffold genere un projet qui demarre |

## Quoi de neuf depuis v1.0.0

- **README correct sur PyPI** (logo affiche, install command alignee sur le nom PyPI `fabrik-fastapi`)
- **Defensive Redis lifespan** : `asyncio.wait_for(timeout=3s)` empeche tout hang sur Redis injoignable
- **Requirements en bornes minimales** au lieu de pins exacts (resout les soucis de versions futures non publiees)
- **CI fix** : 11/11 tests passent dans GitHub Actions (cmd_add normalise au singulier)

## Documentation

- [README.md](https://github.com/FalandyJEAN/fabrik#readme) — vue d'ensemble
- [docs/USAGE.md](https://github.com/FalandyJEAN/fabrik/blob/main/docs/USAGE.md) — guide complet (10 sections + FAQ)
- [ARCHITECTURE.md](https://github.com/FalandyJEAN/fabrik/blob/main/ARCHITECTURE.md) — decisions de design
- [docs/PUBLISHING.md](https://github.com/FalandyJEAN/fabrik/blob/main/docs/PUBLISHING.md) — workflow de release

## Pourquoi Fabrik ?

|  | FastAPI seul | Django | **Fabrik** |
|---|---|---|---|
| Async natif | oui | non | **oui** |
| Auth JWT prete | non | tierce | **oui** |
| Admin UI auto-genere | non | oui (sync) | **oui (async, responsive)** |
| Background tasks integres | non | Celery (tiers) | **oui (ARQ inclus)** |
| Migration de projet versionnee | non | manuel | **`fabrik upgrade`** |
| Demarrage zero-config | 2 jours | 30 min | **60 secondes** |

## Roadmap

- v1.1 : tests d'integration avec un vrai Redis dans la CI
- v1.2 : RBAC (roles + permissions par modele dans l'admin)
- v1.3 : graphes d'activite Chart.js sur le dashboard admin
- v2.0 : ACL granulaire + multi-tenancy

## Contribuer

Issues + PR bienvenus : https://github.com/FalandyJEAN/fabrik

---

**Auteur :** Falandy Jean &middot; **Licence :** MIT &middot; **Python :** 3.13+
