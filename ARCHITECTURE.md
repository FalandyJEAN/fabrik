# Architecture de Fabrik

> Document de reference sur les decisions de conception, le decoupage du code,
> et le cycle de vie d'un projet genere.

**Auteur :** Falandy Jean
**Version :** 1.0.0

---

## 1. Philosophie

Fabrik est un **opinionated framework** construit au-dessus de FastAPI. Il
prend des decisions pour toi sur :

- L'asynchronisme (tout est `async`, pas de blocage thread sur les I/O DB)
- La structure de fichiers (`src/<module>/` avec separation
  `models / schemas / service / router`)
- La securite par defaut (CORS strict, SECRET_KEY 256 bits, bcrypt, JWT)
- Les outils de developpement (tests isoles, migrations, admin UI)

**Ce que Fabrik refuse de faire :**
- Devenir un framework "universel" (pas de plugins, pas d'ecosysteme tiers)
- Cacher SQLAlchemy ou FastAPI (tu vois et controle tout)
- Etre retro-compatible avec les vieux Python (Python 3.13+ uniquement)

---

## 2. Decoupage du repo

```
fabrik/                          ← repo GitHub
├── pyproject.toml               Metadata PyPI (nom, version, deps, entry_points)
├── MANIFEST.in                  Inclusion de core/ dans la sdist
├── README.md                    Vitrine + installation
├── ARCHITECTURE.md              ← ce fichier
├── LICENSE                      MIT
├── docs/
│   ├── USAGE.md                 Guide utilisateur complet
│   └── PUBLISHING.md            Workflow de release PyPI
├── .github/workflows/ci.yml     CI (lance test-self a chaque commit)
└── fabrik/                      ← PACKAGE Python publie sur PyPI
    ├── __init__.py              Version + exports
    ├── __main__.py              Pour `python -m fabrik`
    ├── scaffold.py              Moteur CLI
    └── core/                    Templates copies dans chaque projet
```

Quand l'utilisateur fait `pip install fabrik-fastapi`, c'est le dossier
**inner `fabrik/`** qui est installe dans le `site-packages` de son Python.
La commande `fabrik` est creee par l'entry point `[project.scripts]` de
`pyproject.toml` qui pointe vers `fabrik.scaffold:main`.

### 2.1 Pourquoi `core/` est un dossier separe ?

A la version 0 du prototype, **tous les templates etaient des chaines Python
embarquees dans `scaffold.py`** (3902 lignes). Probleme :

- Pas de coloration syntaxique dans l'IDE pour les templates Jinja2 / HTML / CSS
- Difficile de chercher et editer un fichier specifique
- Mauvais ratio signal/bruit a la lecture de `scaffold.py`

Depuis v1.0, **les templates vivent comme de vrais fichiers dans `core/`** :

- `core/<chemin>` -> fichier statique copie tel quel
- `core/_templates/*.tpl` -> fichier avec substitution `string.Template`
  (`${title}`, `${port}`, `${secret_key}`, `${db_url}`)

`build_files()` est passe de 2750 lignes hardcodees a 20 lignes qui font un
`rglob` sur `core/`.

---

## 3. Cycle de vie d'un projet

### 3.1 `scaffold.py new mon-api`

```
   cmd_new()
       │
       ├── build_files(title, port, db_url)
       │       └── walk core/ -> dict {chemin: contenu}
       │       └── string.Template.substitute() pour core/_templates/*.tpl
       │
       ├── Pour chaque (chemin, contenu) : f.write_text(contenu)
       │
       ├── Ecrit .scaffold-version (JSON : version + date + patches_applied)
       │
       ├── subprocess: python -m venv venv
       ├── subprocess: venv/pip install -r requirements.txt
       └── subprocess: venv/python -m alembic revision/upgrade
```

### 3.2 `scaffold.py add videos` (depuis la racine du projet)

```
   cmd_add()
       │
       ├── Genere les 5 fichiers du module
       │   (models.py, schemas.py, service.py, router.py, test_videos.py)
       │   via les Templates string.Template MODULE_MODELS, MODULE_SCHEMAS, ...
       │
       ├── Auto-wiring (idempotent) :
       │   ├── main.py             : ajoute import + include_router
       │   ├── alembic/env.py      : ajoute import src.videos.models
       │   └── src/users/models.py : ajoute relation back_populates
       │
       ├── subprocess: alembic revision --autogenerate -m add_videos
       ├── subprocess: alembic upgrade head
       └── subprocess: pytest tests/test_videos.py
```

L'auto-wiring utilise `_insert_after(content, anchor, new_line)` qui :
1. Verifie que la ligne (strip) n'est pas deja presente dans le fichier
2. Trouve la premiere occurrence de l'anchor
3. Insere la nouvelle ligne juste apres

Cette idempotence permet de relancer `add` sans dupliquer les imports.

### 3.3 `scaffold.py upgrade` (depuis la racine du projet)

```
   cmd_upgrade()
       │
       ├── Lit .scaffold-version -> version courante du projet
       ├── Compare avec SCAFFOLD_VERSION (constante en haut de scaffold.py)
       ├── Si projet < scaffold :
       │   └── Pour chaque patch dans PATCHES dont [from, to] est compris :
       │       └── patch["apply"](root)   ← fonction idempotente
       │       └── Met a jour .scaffold-version
       │
       └── Si projet >= scaffold : "deja a jour"
```

Les fonctions de patch :
- Recoivent `root: Path` (racine du projet a patcher)
- Doivent etre **idempotentes** : safe a relancer N fois
- Doivent ecrire un backup `.bak` avant tout ecrasement destructif
- Retournent un `dict {chemin: statut}` pour le rapport

---

## 4. Decisions de conception : le projet genere

### 4.1 Pourquoi `src/<module>/` au lieu d'un layout plat ?

Le decoupage en `models / schemas / service / router` impose **la separation
des responsabilites** :

- `models.py` : ORM SQLAlchemy (donnees + relations)
- `schemas.py` : validation Pydantic (input/output API)
- `service.py` : logique metier (operations sur la DB)
- `router.py` : routes HTTP (mapping URL -> service)

Effet de bord : chaque module est **extractible en microservice** plus tard
sans refactor douloureux.

### 4.2 Pourquoi tout en async ?

FastAPI + Starlette + uvicorn sont conçus pour async. Une route sync bloque
le worker pendant l'attente DB. Avec `AsyncSession` + `asyncpg`, un seul
process Python peut servir des milliers de requetes/seconde.

Cout : la syntaxe `await` partout, et `db.execute(select(...))` au lieu de
`db.query(...).filter(...).all()`. Mais c'est le standard SQLAlchemy 2.0.

### 4.3 Pourquoi un `lifespan` ?

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
```

Le lifespan remplace l'ancien `@app.on_event("startup")` deprecie. Il :
- Cree les tables si elles n'existent pas (utile en dev sans Alembic)
- Garantit le `dispose()` du pool de connexions a l'arret (pas de leak)
- Est `async` natif (vs les hooks synchrones de l'ancienne API)

### 4.4 Pourquoi SECRET_KEY est generee a chaque `new` ?

`secrets.token_urlsafe(32)` = 256 bits d'entropie. Chaque projet a son propre
secret des le depart, jamais commit accidentellement (le `.env` est dans
`.gitignore`). PyJWT exige 32+ bytes pour HMAC-SHA256.

### 4.5 Pourquoi CORS strict par defaut ?

```python
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Avec `allow_origins=["*"]` + `allow_credentials=True`, Starlette desactive
silencieusement les cookies (specification CORS). En forcant une liste
explicite, on evite cette piege ET on empeche un site malveillant de
proxifier l'API au nom de l'utilisateur.

### 4.6 Pourquoi tests isoles via fixture `client` ?

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def client(test_engine):
    async def override_get_db():
        async with TestSession() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), ...) as c:
        yield c
    app.dependency_overrides.clear()
```

Chaque test recoit une **SQLite in-memory toute fraiche** (avec `StaticPool`
pour partager la meme connexion entre fixture et requete). La vraie `app.db`
de dev n'est jamais touchee par pytest.

---

## 5. Decisions de conception : l'admin UI

### 5.1 Auto-discovery via `Base.registry.mappers`

Plutot que de demander aux utilisateurs de declarer leurs modeles dans
l'admin (a la Django `admin.site.register()`), Fabrik **scanne dynamiquement
SQLAlchemy** :

```python
def get_admin_models() -> dict:
    return {m.class_.__tablename__: m.class_ for m in Base.registry.mappers}
```

Resultat : des qu'un module ajoute une classe heritant de `Base`, elle
apparait dans la sidebar. Zero configuration.

### 5.2 Formulaires generes par introspection des colonnes

`col_input_type(col)` mappe les types SQLAlchemy vers des `<input type="...">` :

| Type SQLAlchemy        | input HTML        |
|------------------------|-------------------|
| `Boolean`              | `checkbox`        |
| `Integer`, `Numeric`   | `number`          |
| `DateTime`             | `datetime-local`  |
| `Date`                 | `date`            |
| nom contient "email"   | `email`           |
| nom == "password"      | `password`        |
| presence de FK         | `select` (dropdown avec resolution display field) |
| autre                  | `text`            |

### 5.3 FK dropdowns intelligents

Quand une colonne est une FK, l'admin :
1. Detecte la table cible via `col.foreign_keys`
2. Charge jusqu'a 500 lignes de la table cible
3. Choisit la meilleure colonne d'affichage : `email` > `name` > `title` >
   `label` > `username` > `id`
4. Rend un `<select>` avec `<option value="{uuid}">email@example.com ({uuid_court})</option>`

### 5.4 Multi-column search (v1)

Recherche sans configuration : `?q=foo` -> ILIKE `%foo%` sur **toutes** les
colonnes `varchar`/`string`/`text` (sauf `password`), combinees en `or_(...)`.

### 5.5 Bulk delete (v1)

Checkboxes par ligne + action bar sticky. La route `POST /admin/{table}/bulk-delete`
recoit `ids[]` et execute `delete().where(Model.id.in_(ids))` -- **une seule
requete SQL** pour N suppressions.

### 5.6 CSV export (v1)

`GET /admin/{table}/export.csv` -> `StreamingResponse` avec `csv.writer`.
Nom de fichier : `{table}-{YYYY-MM-DD}.csv`. Toutes les colonnes sauf
`password`.

### 5.7 Responsive design

Le CSS utilise un `@media (max-width: 768px)` qui transforme la sidebar en
**drawer slide-in** avec hamburger + backdrop. Les `input` mobile sont en
`font-size: 16px` pour empecher le zoom iOS au focus.

---

## 6. Background tasks : pourquoi ARQ

### 6.1 Le besoin

Toute application un peu serieuse a besoin de **deleguer des operations
lentes** hors du cycle requete/reponse HTTP :
- Envoi d'emails / notifications push
- Ingestion / parsing de fichiers volumineux (PDFs, CSVs)
- Calculs longs (rapports, exports, machine learning)
- Appels d'API externes lents ou peu fiables (retry)

Faire ces operations dans la route bloque le worker et timeout cote client.

### 6.2 Pourquoi pas un worker Go ?

Tentation classique : "Python est lent, mettons un worker en Go pour la
performance." En realite, **95% des taches typiques sont I/O-bound** (attente
API externe, requete DB, lecture disque). Sur ces operations, Python async
= Go en performance, a la milliseconde pres.

Le cout d'ajouter Go est massif :
- Nouvelle toolchain (`go build`, `go mod`)
- 2e langage a maintenir / debugger
- 2e binaire / image Docker / pipeline de deploy
- Communication inter-langage (queue ou cgo) avec sa propre complexite

Reserve Go pour le 1% de cas ou tu as **vraiment** mesure que Python CPU
est le bottleneck (parsing binaire intensif, math sur grands tenseurs).

### 6.3 Pourquoi ARQ et pas Celery ?

| | Celery | ARQ |
|---|---|---|
| Age | 2009 | 2017 |
| Async natif | Non (sync, support async ajoute apres) | **Oui** |
| Broker | RabbitMQ/Redis/etc. | Redis uniquement |
| Taille code | Lourd | Leger (~3k lignes) |
| Battle-tested | Instagram, Mozilla, Pinterest | Plus modeste |
| Ecosysteme | Flower, beat, multiple plugins | Minimal |
| Cohabitation FastAPI | Demande plomberie | Naturelle |

ARQ est **conçu pour Python async** depuis le debut. Dans un projet ou
**tout** est `async def` (routes, services, dependances), Celery introduit
une rupture mentale (workers sync) ; ARQ reste coherent.

Pour des cas de scale extreme (millions de jobs/jour, multi-broker, monitoring
sophistique), Celery garde l'avantage. Pour 99% des projets, ARQ suffit
largement.

### 6.4 Architecture cote API

Le pool Redis est cree dans le `lifespan` :

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... create_all tables ...
    try:
        app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    except Exception as e:
        logger.warning("Redis indisponible (%s) -- background tasks desactives", e)
        app.state.arq_pool = None
    yield
    if app.state.arq_pool is not None:
        await app.state.arq_pool.close()
```

**Degradation gracieuse** : si Redis n'est pas joignable au demarrage, l'app
demarre quand meme. Les routes qui veulent enqueue retournent 503 via la
dependance `get_arq`. Le reste (admin, CRUD users, API) fonctionne sans
difference.

### 6.5 Architecture cote worker

`worker.py` a la racine = entrypoint trivial qui appelle `run_worker(WorkerSettings)`.
`WorkerSettings` vit dans `src/tasks.py` (a cote des taches qu'il execute) :

- `functions: list` -> liste des fonctions appelables via `enqueue_job(name, ...)`
- `redis_settings` -> connexion Redis (meme URL que cote API)
- `max_jobs` -> concurrence par worker (10 par defaut)
- `job_timeout` -> timeout par tache (5 min par defaut)

Tu peux lancer N workers en parallele sur N machines : Redis joue le role
de broker partage. C'est exactement le pattern Celery sans la lourdeur.

---

## 7. Le mecanisme `test-self`

`cmd_test_self()` est la garantie que **Fabrik genere toujours un projet qui
demarre vraiment**. Le workflow :

1. `tempfile.mkdtemp()` -> projet jetable
2. `cmd_new(absolute_path, no_input=True)` -> generation complete
3. Verifications : venv existe, `.scaffold-version` ecrit, migration appliquee
4. `subprocess pytest tests/ -q` -> doit retourner 0
5. `subprocess uvicorn main:app --port <random>` en background
6. Attente de l'ouverture du port (timeout 25s)
7. HTTP GET sur `/`, `/admin/login`, `/docs` -> doit retourner 200
8. Kill du serveur
9. `cmd_add("articles")` -> test du module + auto-wiring
10. `ast.parse()` sur les 5 fichiers generes -> doit etre du Python valide
11. `shutil.rmtree(tmp)` (sauf si `--keep`)

Le CI (`.github/workflows/ci.yml`) lance ce test a chaque push -- un commit
qui casse la generation se voit immediatement.

---

## 8. Limites connues

- **Pas de plugins externes.** Fabrik est volontairement monolithique. Le
  jour ou tu veux brancher un module tiers (ex: OAuth Google), tu copies le
  code dans `src/<module>/` au lieu de `pip install fabrik-plugin-X`.
- **Python 3.13+ obligatoire.** On utilise les nouveautes (PEP 695, etc.) et
  on ne supporte pas les versions plus anciennes.
- **PostgreSQL recommande en prod.** SQLite marche pour le dev mais
  manque de concurrence pour la production.
- **L'admin scanne TOUS les modeles SQLAlchemy.** Pas (encore) de mecanisme
  pour exclure des modeles internes.

---

## 9. Ressources

- [README.md](README.md) : presentation generale
- [docs/USAGE.md](docs/USAGE.md) : guide utilisateur complet
- [scaffold.py](scaffold.py) : code source du moteur
- [core/](core/) : templates copies dans chaque projet
