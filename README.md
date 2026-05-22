<p align="center">
  <img src="https://raw.githubusercontent.com/FalandyJEAN/fabrik/main/docs/assets/logo.png" alt="Fabrik logo" width="200" />
</p>

<h1 align="center">Fabrik</h1>

<p align="center">
  <strong>Generateur de projet FastAPI async + opinionated.</strong><br>
  En 60 secondes : auth JWT, admin UI auto-decouverte, tests isoles,<br>
  background tasks (ARQ), migrations Alembic, CORS strict, responsive.
</p>

<p align="center">
  <a href="https://pypi.org/project/fabrik-fastapi/"><img src="https://img.shields.io/pypi/v/fabrik-fastapi.svg" alt="PyPI version" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python 3.13+" /></a>
  <a href="https://github.com/FalandyJEAN/fabrik/actions/workflows/ci.yml"><img src="https://github.com/FalandyJEAN/fabrik/actions/workflows/ci.yml/badge.svg" alt="Fabrik CI" /></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
</p>

<p align="center">
  <strong>Version :</strong> <code>1.0.1</code> &nbsp;&middot;&nbsp;
  <strong>Auteur :</strong> Falandy Jean &nbsp;&middot;&nbsp;
  <strong>Licence :</strong> MIT
</p>

---

## Installation

```bash
pip install fabrik-fastapi
```

Verifier l'installation :

```bash
fabrik --help
```

Pre-requis : **Python 3.13+**.

---

## 60 secondes pour demarrer

```bash
fabrik new mon-api
cd mon-api
venv\Scripts\activate                 # Windows
# source venv/bin/activate            # Linux/Mac
python create_superuser.py
python -m uvicorn main:app --reload
```

Ouvre :
- **Admin UI** : http://127.0.0.1:8000/admin
- **Swagger** : http://127.0.0.1:8000/docs

---

## Ce que tu obtiens out-of-the-box

| Domaine            | Choix par defaut                                              |
|--------------------|---------------------------------------------------------------|
| Framework          | FastAPI 0.136 + Starlette                                     |
| ORM                | SQLAlchemy 2.0 **async** (`AsyncSession`)                     |
| Driver DB          | `aiosqlite` (dev) / `asyncpg` (prod PostgreSQL)               |
| Auth               | JWT (access + refresh) avec bcrypt                            |
| Admin              | UI auto-decouverte responsive, multi-search, bulk delete, CSV |
| Migrations         | Alembic (autogenerate)                                        |
| Background tasks   | ARQ (Redis-backed, async-native) avec degradation gracieuse   |
| Tests              | pytest + pytest-asyncio + DB SQLite in-memory isolee          |
| CORS               | Strict via `BACKEND_CORS_ORIGINS` (pas de `*`)                |
| Config             | `pydantic-settings` (12-factor)                               |
| Docker             | `Dockerfile` Python 3.13-slim + `docker-compose.yml`          |

---

## Les 4 commandes

| Commande                            | Effet                                                         |
|-------------------------------------|---------------------------------------------------------------|
| `fabrik new <nom>`                  | Genere un projet complet (venv + deps + migration initiale)   |
| `fabrik add <module>`               | Ajoute un module CRUD (auto-wire + migration + tests)         |
| `fabrik upgrade`                    | Met a jour un projet existant a la derniere version           |
| `fabrik test-self`                  | Meta-test : verifie que le scaffold genere un projet OK       |

Detail complet dans [docs/USAGE.md](docs/USAGE.md).

---

## Pourquoi Fabrik ?

Fabrik couvre l'angle mort entre **Django** (rigide, monolithique, sync) et
**FastAPI nu** (zero opinion, 2 jours de plomberie a chaque projet).

| | FastAPI standard | Django | **Fabrik** |
|---|---|---|---|
| Stack async | oui | non | **oui** |
| Auth JWT prete | non | tierce | **oui** |
| Admin UI auto-genere | non | oui (sync) | **oui (async, responsive)** |
| Background tasks | non | Celery (tiers) | **oui (ARQ inclus)** |
| Tests isoles fournis | non | oui | **oui** |
| Architecture modulaire | a faire | apps | **`src/<module>/`** |
| Migration de projet | non | manuel | **`fabrik upgrade`** |
| Demarrage zero-config | 2j | 30 min | **60 secondes**          |

Detail des choix de conception : [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Structure d'un projet genere

```
mon-api/
├── main.py                       FastAPI app + lifespan + pool ARQ
├── worker.py                     Entrypoint ARQ (python worker.py)
├── docker-compose.yml            Redis + (PostgreSQL optionnel)
├── .env                          SECRET_KEY 256 bits + CORS + DB + Redis
├── .scaffold-version             Trace de la version Fabrik (pour upgrade)
├── create_superuser.py
├── requirements.txt
├── pytest.ini
├── alembic.ini + alembic/
├── src/
│   ├── database.py               AsyncEngine + get_db
│   ├── tasks.py                  ARQ tasks + WorkerSettings + get_arq dep
│   ├── core/                     Config, security, mixins, pagination
│   ├── users/                    Module exemple (models/schemas/service/router)
│   └── admin/                    UI auto-decouverte (router + templates + static)
└── tests/
    ├── conftest.py               Fixtures async (DB in-memory isolee)
    ├── test_users.py
    └── test_tasks.py
```

---

## Architecture du repo Fabrik

```
fabrik/                           Repo GitHub
├── pyproject.toml                Package metadata (PyPI)
├── MANIFEST.in
├── README.md, ARCHITECTURE.md, LICENSE
├── docs/
│   ├── USAGE.md                  Guide utilisateur
│   └── PUBLISHING.md             Workflow de release PyPI
├── .github/workflows/ci.yml      CI : lance test-self a chaque commit
└── fabrik/                       Package Python
    ├── __init__.py
    ├── __main__.py               Pour `python -m fabrik`
    ├── scaffold.py               Moteur CLI
    └── core/                     Templates copies a chaque `new`
```

---

## Developpement local

Si tu veux contribuer ou tester en local sans publier sur PyPI :

```bash
git clone https://github.com/FalandyJEAN/fabrik.git
cd fabrik
pip install -e .                  # installation en mode editable
fabrik test-self                  # verifie que tout fonctionne
```

Tout changement qui modifie la structure des projets generes doit :

1. Bumper `SCAFFOLD_VERSION` dans `fabrik/scaffold.py` (et `version` dans `pyproject.toml`)
2. Ajouter une fonction `patch_vN_to_vM(root)` **idempotente**
3. L'enregistrer dans `PATCHES`
4. `fabrik test-self` doit passer en local et en CI

---

## Publication PyPI

Workflow complet dans [docs/PUBLISHING.md](docs/PUBLISHING.md). En resume :

```bash
pip install -e ".[dev]"
python -m build
twine upload dist/*
```

---

## Licence

MIT &copy; 2026 Falandy Jean &mdash; voir [LICENSE](LICENSE).
