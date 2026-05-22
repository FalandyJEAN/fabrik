# Guide d'utilisation Fabrik

> Toutes les commandes, options, workflows. Pour les decisions de design,
> voir [ARCHITECTURE.md](../ARCHITECTURE.md).

**Version :** 1.0.0
**Auteur :** Falandy Jean

---

## Sommaire

1. [Pre-requis](#1-pre-requis)
2. [Installation](#2-installation)
3. [`new` &mdash; creer un projet](#3-new--creer-un-projet)
4. [`add` &mdash; ajouter un module](#4-add--ajouter-un-module)
5. [`upgrade` &mdash; mettre a jour un projet](#5-upgrade--mettre-a-jour-un-projet)
6. [`test-self` &mdash; meta-test du scaffold](#6-test-self--meta-test-du-scaffold)
7. [Utiliser l'admin UI](#7-utiliser-ladmin-ui)
8. [Workflows types](#8-workflows-types)
9. [Personnalisation](#9-personnalisation)
10. [Background tasks (ARQ + Redis)](#10-background-tasks-arq--redis)
11. [FAQ](#11-faq)

---

## 1. Pre-requis

- **Python 3.13+** (`python --version`)
- **pip** a jour : `python -m pip install --upgrade pip`

Optionnel mais recommande :
- **Redis** pour les background tasks (`docker compose up -d redis`)
- **PostgreSQL 14+** pour la production (le dev utilise SQLite par defaut)
- **Docker** pour containeriser (`Dockerfile` et `docker-compose.yml` generes)

---

## 2. Installation

### Via pip (recommande)

```bash
pip install fabrik-cli
```

Cela installe la commande globale `fabrik` (et `python -m fabrik` comme alternative).

Verifier :

```bash
fabrik --help
```

Tu dois voir :

```
usage: fabrik [-h] {new,add,upgrade,test-self} ...
```

### Depuis le source (developpement)

```bash
git clone https://github.com/FalandyJEAN/fabrik.git
cd fabrik
pip install -e .       # mode editable
```

### Mise a jour

```bash
pip install -U fabrik-cli
```

---

## 3. `new` &mdash; creer un projet

### Syntaxe

```bash
fabrik new <nom-du-projet> [--no-input]
```

### Exemple interactif

```bash
fabrik new mon-api
```

Le scaffold te demande :
- Titre de l'API (defaut : nom du projet en title-case)
- Port (defaut : 8000)
- Base de donnees (1 = SQLite, 2 = PostgreSQL)
- Si PostgreSQL : DATABASE_URL complete

### Exemple non-interactif

```bash
fabrik new mon-api --no-input
```

Utilise les valeurs par defaut (SQLite, port 8000).

### Ce qui se passe

1. Cree le dossier `mon-api/` avec ~41 fichiers
2. Cree un `venv/` dans le projet
3. `pip install -r requirements.txt` (FastAPI, SQLAlchemy, ARQ, etc.)
4. Lance la 1ere migration Alembic (cree la table `users`)
5. Affiche un resume avec les commandes pour demarrer

### Apres la generation

```bash
cd mon-api
venv\Scripts\activate                 # Windows
# source venv/bin/activate            # Linux/Mac

python create_superuser.py            # cree ton compte admin
python -m uvicorn main:app --reload   # demarre le serveur
```

Le serveur est sur http://127.0.0.1:8000.

---

## 4. `add` &mdash; ajouter un module

### Syntaxe

A lancer **depuis la racine du projet** (n'importe ou tant que tu es dans
`mon-api/`) :

```bash
fabrik add <nom-module> [options]
```

### Options

| Flag           | Effet                                                          |
|----------------|----------------------------------------------------------------|
| `--no-wire`    | Ne modifie pas `main.py` / `alembic/env.py` / `users/models.py`|
| `--no-migrate` | Ne lance pas `alembic revision --autogenerate`                 |
| `--no-test`    | Ne joue pas `pytest tests/test_<module>.py`                    |

Par defaut, tout est fait automatiquement.

### Exemple

Depuis `mon-api/` (venv active) :

```bash
fabrik add videos
```

Sortie :

```
  [OK] Module 'video' cree dans src/video/
  [OK] Tests crees dans tests/test_video.py

  >> Auto-wiring :
  [OK] main.py             : import + include_router ajoutes
  [OK] alembic/env.py      : import du modele ajoute
  [OK] src/users/models.py : relation 'videos' ajoutee

  >> Migration Alembic :
  [OK] Migration appliquee : add_video

  >> Tests du nouveau module :
  [OK] 4 test(s) du module passent
```

### Ce qui est genere

```
src/video/
├── __init__.py
├── models.py        # Class Video(TimestampMixin, Base)
├── schemas.py       # VideoCreate / VideoResponse / VideoUpdate / VideoPage
├── service.py       # CRUD async : create_video, get_video, list_videos, ...
└── router.py        # /videos/ CRUD endpoints (avec auth)

tests/
└── test_video.py    # 4 tests : create, list, get-not-found, unauthorized
```

### Personnaliser le module

Apres `fabrik add videos`, le module a une seule colonne `title`. Pour
ajouter des champs :

1. **Edite `src/video/models.py`** :
   ```python
   class Video(TimestampMixin, Base):
       __tablename__ = "videos"
       id          = Column(String, primary_key=True, default=generate_id)
       title       = Column(String, nullable=False, index=True)
       description = Column(String, nullable=True)           # NOUVEAU
       duration    = Column(Integer, nullable=False, default=0)  # NOUVEAU
       user_id     = Column(String, ForeignKey("users.id"), nullable=False)
       author      = relationship("User", back_populates="videos")
   ```

2. **Edite `src/video/schemas.py`** pour exposer ces champs :
   ```python
   class VideoCreate(BaseModel):
       title: str
       description: str | None = None
       duration: int = 0
   ```

3. **Genere la migration et applique-la** :
   ```bash
   python -m alembic revision --autogenerate -m "add_description_duration_to_video"
   python -m alembic upgrade head
   ```

---

## 5. `upgrade` &mdash; mettre a jour un projet

### Cas d'usage

Tu as cree un projet avec Fabrik v1.0.0. Plus tard, Fabrik passe en v2.0.0
avec une mise a jour du middleware CORS. Au lieu de regenerer ton projet
(perdre ton code), tu fais :

```bash
# Depuis la racine de ton projet
fabrik upgrade
```

### Dry-run (preview)

```bash
fabrik upgrade --dry-run
```

Affiche les patches qui seraient appliques sans rien ecrire.

### Comment ca marche

1. Lit `.scaffold-version` (cree a la generation du projet)
2. Compare avec `SCAFFOLD_VERSION` de la version Fabrik installee
3. Applique en chaine chaque patch entre les deux versions
4. Met a jour `.scaffold-version`

Les patches sont **idempotents** -- safe a relancer.

Les fichiers ecrases ont un backup `.bak` ecrit a cote (pour diff/rollback).

---

## 6. `test-self` &mdash; meta-test du scaffold

```bash
fabrik test-self [--keep]
```

### Ce qui se passe

1. Cree un projet jetable dans `/tmp/scaffold-test-xxx/`
2. Genere le projet via `fabrik new` (cree venv + installe deps + migration)
3. Lance `pytest tests/`
4. Demarre `uvicorn` sur un port libre
5. HTTP GET sur `/`, `/admin/login`, `/docs` -> verifie HTTP 200
6. Arrete le serveur
7. Lance `fabrik add articles` (test du module + auto-wiring)
8. Verifie que les 5 fichiers generes parsent en Python
9. Nettoie le tempdir (ou le garde avec `--keep`)

### Sortie type

```
  [OK] Generation projet (cmd_new)         57.3s
  [OK] Venv operationnel                    0.0s
  [OK] Migration initiale Alembic           0.0s   1 revision(s)
  [OK] pytest (suite complete)              4.2s   7 tests OK
  [OK] Uvicorn (port d'ecoute)              2.1s   port 54321
  [OK] GET /  (health)                      0.1s   HTTP 200
  [OK] GET /admin/login (UI)                0.0s   HTTP 200
  [OK] GET /docs (Swagger)                  0.0s   HTTP 200
  [OK] Arret propre uvicorn                 0.3s
  [OK] fabrik add articles                  0.0s
  [OK] Module articles/ (5 fichiers OK)     0.0s

  RESULTAT : 11/11 etapes OK  --  scaffold sain
```

Utilise en CI dans `.github/workflows/ci.yml`.

---

## 7. Utiliser l'admin UI

### Connexion

http://127.0.0.1:8000/admin/login

Connecte-toi avec l'utilisateur cree via `python create_superuser.py`.

### Sidebar

3 sections :
- **General** : Dashboard
- **Modeles** : tous les modeles auto-decouverts (users + tous les modules ajoutes)
- **Outils** : Swagger, ReDoc

Sur mobile, la sidebar se transforme en drawer (clique sur l'icone hamburger
en haut a gauche).

### Dashboard

- Salutation contextuelle (Bonjour / Bon apres-midi / Bonsoir)
- 4 KPI cards : nombre de modeles, total enregistrements, activite recente,
  role
- Grille des collections avec compteurs
- **Activite recente** : derniers items crees toutes tables confondues
- **Demarrage rapide** : liens vers Swagger, creation user, etc.

### Liste d'un modele (ex: `/admin/users`)

- **Recherche multi-colonnes** : tape dans la barre, ca filtre ILIKE sur toutes
  les colonnes texte
- **Checkboxes** : clique pour selectionner des lignes
- **Bulk delete** : quand au moins 1 ligne est cochee, une action bar apparait
  -> "Supprimer la selection"
- **Export CSV** : bouton "CSV" en haut a droite (respecte le filtre de
  recherche courant)
- **Pagination** : 25 lignes par page
- **FK affichees comme liens** : si une colonne est une FK, l'admin affiche
  le `email`/`name`/`title` de l'objet cible (cliquable)

### Formulaire (creer / editer)

- Genere automatiquement depuis les colonnes SQLAlchemy
- Types adaptes : checkbox pour Boolean, datetime-local pour DateTime,
  select pour FK, etc.
- Champs `id` / `created_at` / `updated_at` en readonly
- Champ `password` masque + placeholder "Laissez vide pour ne pas changer"
  en edition

---

## 8. Workflows types

### Demarrer un MVP en 5 minutes

```bash
pip install fabrik-cli
fabrik new mon-mvp
cd mon-mvp
venv\Scripts\activate
python create_superuser.py
python -m uvicorn main:app --reload
# -> Ouvre /admin et commence a creer des donnees
```

### Ajouter une feature "produits"

```bash
cd mon-mvp
fabrik add products
# Edite src/product/models.py pour ajouter price, stock, etc.
python -m alembic revision --autogenerate -m "add_product_fields"
python -m alembic upgrade head
# /admin/products fonctionne maintenant
```

### Passer en production avec PostgreSQL + Redis

1. Cree une DB PostgreSQL et lance un Redis (ou utilise le compose fourni :
   `docker compose up -d`)
2. Edite `.env` :
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/mydb
   BACKEND_CORS_ORIGINS=https://mon-front.com
   REDIS_URL=redis://prod-redis:6379
   ```
3. Applique les migrations :
   ```bash
   python -m alembic upgrade head
   ```
4. Lance l'API + le worker :
   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port 8000   # API
   python worker.py                                         # worker ARQ
   ```
5. Ou build l'image Docker :
   ```bash
   docker build -t mon-mvp .
   docker run -p 8000:8000 --env-file .env mon-mvp
   ```

### Mettre a jour Fabrik dans un vieux projet

```bash
# Met a jour le package Fabrik lui-meme
pip install -U fabrik-cli

# Applique les patches a chaque projet
cd mon-mvp
fabrik upgrade --dry-run    # voir d'abord
fabrik upgrade              # appliquer
```

---

## 9. Personnalisation

### Modifier les templates pour les futurs projets

Si tu as installe Fabrik en mode editable (`pip install -e .` depuis le clone
git), edite `fabrik/core/<chemin>` :

| Tu veux changer...                  | Edite...                                       |
|-------------------------------------|------------------------------------------------|
| Le titre par defaut de l'app        | `fabrik/core/_templates/main.py.tpl`           |
| Les origines CORS par defaut        | `fabrik/core/_templates/env.tpl`               |
| Les dependances Python              | `fabrik/core/requirements.txt`                 |
| Le style de l'admin                 | `fabrik/core/src/admin/static/admin.css`       |
| Les templates HTML de l'admin       | `fabrik/core/src/admin/templates/*.html`       |
| La duree des tokens                 | `fabrik/core/src/core/config.py`               |
| La logique JWT                      | `fabrik/core/src/core/security.py`             |

Apres modification, **lance `fabrik test-self`** pour verifier que les
futurs projets generes demarrent encore.

Si tu as installe via `pip install fabrik-cli`, les templates sont dans
le dossier site-packages (`<venv>/lib/pythonX.Y/site-packages/fabrik/core/`).
Pour customiser durablement, mieux vaut cloner le repo et installer en mode
editable.

### Patcher des projets deja generes

Voir la section [`upgrade`](#5-upgrade--mettre-a-jour-un-projet).
Le mecanisme `PATCHES` dans `fabrik/scaffold.py` permet de propager les
changements.

---

## 10. Background tasks (ARQ + Redis)

Fabrik integre **ARQ** pour les taches lourdes en arriere-plan (envoi
d'emails, ingestion de fichiers, calculs longs, appels d'API externes).

### Pourquoi ARQ et pas Celery ?

ARQ est **async-native** : il colle parfaitement a la philosophie Fabrik
ou tout est `async def`. Celery date d'avant async Python et necessite plus
de plomberie pour cohabiter avec FastAPI.

### Degradation gracieuse

**L'API marche meme sans Redis.** Si Redis est down :
- Le serveur demarre normalement (warning dans les logs)
- Les routes qui veulent enqueue renvoient `503 Service Unavailable`
- Le reste de l'app (admin, CRUD users, API) fonctionne sans difference

C'est le bon defaut pour le dev (pas besoin de Redis pour bricoler).

### Demarrer Redis + le worker

```bash
# 1. Lance Redis (laisse tourner)
docker compose up -d redis

# 2. Dans un terminal separe : lance le worker ARQ
python worker.py
# Equivalent : arq src.tasks.WorkerSettings
```

Tu verras dans les logs :
```
ARQ pool connecte a redis://localhost:6379    (cote API)
ARQ worker demarre (max_jobs=10)              (cote worker)
```

### Ecrire une tache

Dans `src/tasks.py`, ajoute ta fonction et reference-la dans `WorkerSettings.functions` :

```python
async def send_email(ctx: dict, to: str, subject: str, body: str) -> None:
    # Ta logique (SMTP, SendGrid, etc.)
    logger.info("Email envoye a %s : %s", to, subject)


async def ingest_pdf(ctx: dict, file_id: str) -> dict:
    # Telecharge, parse, embeds, stocke en DB
    return {"status": "done", "chunks": 142}


class WorkerSettings:
    functions = [example_task, send_email, ingest_pdf]
    # ... reste inchange
```

### Enqueue depuis une route

```python
from fastapi import Depends
from arq.connections import ArqRedis
from src.tasks import get_arq

@router.post("/users/{user_id}/email")
async def trigger_email(
    user_id: str,
    arq: ArqRedis = Depends(get_arq),
):
    job = await arq.enqueue_job(
        "send_email",
        to="user@example.com",
        subject="Bienvenue",
        body="...",
    )
    return {"job_id": job.job_id, "status": "queued"}
```

Le client recoit `202 Accepted` immediatement, le worker traite la tache en
background.

### Recuperer le resultat d'une tache

```python
from arq.jobs import Job

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, arq: ArqRedis = Depends(get_arq)):
    job = Job(job_id, arq)
    info = await job.info()
    result = await job.result(timeout=5)
    return {"status": str(info.status), "result": result}
```

### Planifier des taches recurrentes

Dans `src/tasks.py`, ajoute `cron_jobs` a `WorkerSettings` :

```python
from arq.cron import cron

async def cleanup_old_logs(ctx: dict) -> None:
    # Tourne toutes les nuits a 3h
    ...

class WorkerSettings:
    functions = [...]
    cron_jobs = [cron(cleanup_old_logs, hour=3, minute=0)]
```

---

## 11. FAQ

**Q : Pourquoi `pip install fabrik-cli` mais `fabrik` comme commande ?**

R : Convention PyPI : le nom du paquet sur PyPI est `fabrik-cli` (plus
specifique, evite les collisions), mais une fois installe, il expose la
commande courte `fabrik` (definie dans `pyproject.toml [project.scripts]`).
Tu peux aussi utiliser `python -m fabrik` comme alternative.

**Q : Pourquoi mon module 'videos' devient 'video' en interne ?**

R : Fabrik force le singulier pour le nom de module Python (`src/video/`) et
le pluriel pour la table SQL (`videos`). C'est la convention Rails/Django.
Tu peux quand meme appeler `fabrik add videos` ou `add video`, le
resultat est le meme.

**Q : Mon module a echoue a la migration, je fais quoi ?**

R : Verifie la sortie d'Alembic. Si c'est un conflit de modele :

```bash
# Reset la derniere migration
python -m alembic downgrade -1

# Edite le modele si besoin

# Refais la migration
python -m alembic revision --autogenerate -m "add_<module>"
python -m alembic upgrade head
```

**Q : Puis-je avoir plusieurs super-utilisateurs ?**

R : Oui. Relance `python create_superuser.py` avec un email different.

**Q : Comment desactiver l'admin UI en production ?**

R : Commente la ligne `app.include_router(admin_router)` dans `main.py`. Ou
plus propre : conditionne-la sur `if settings.DEBUG: app.include_router(...)`.

**Q : Comment exclure un modele de l'admin ?**

R : Pour l'instant, l'admin scanne tous les modeles `Base.registry.mappers`.
Pour exclure, tu peux soit :
- Ne pas faire heriter ton modele de `Base` (mais alors il n'est pas dans la DB)
- Patcher `get_admin_models()` dans `src/admin/router.py` pour ajouter une
  liste d'exclusion

**Q : Le test-self prend 1 minute, c'est normal ?**

R : Oui. La majorite du temps est `pip install` des dependances dans le venv
du projet jetable. En CI, le cache pip de GitHub Actions reduit ca a ~20s.

**Q : Comment desinstaller Fabrik ?**

R : `pip uninstall fabrik-cli`. Les projets que tu as deja generes restent
intacts (ils ne dependent pas de Fabrik au runtime, seulement de leurs propres
dependances dans `requirements.txt`).

**Q : Fabrik fonctionne-t-il sur Windows / macOS / Linux ?**

R : Oui, sur les trois. Tous les chemins utilisent `pathlib.Path` et toutes
les commandes subprocess utilisent `sys.executable`. Le seul prerequis est
Python 3.13+.
