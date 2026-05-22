# Fabrik : j'en avais marre de re-coder le meme backend FastAPI a chaque projet

*60 secondes pour passer de `pip install` a un backend async, JWT, admin UI,
tests isoles, migrations Alembic, background tasks. Voici comment.*

---

![Fabrik logo](https://raw.githubusercontent.com/FalandyJEAN/fabrik/main/docs/assets/logo.png)

## Le probleme

Chaque fois que je demarre un nouveau projet FastAPI, c'est la meme corvee
de 2 jours :

- Setup du venv, du `requirements.txt`, des bonnes versions
- Brancher SQLAlchemy en async (`AsyncSession`, `engine`, `get_db` dependency)
- Configurer Alembic (`env.py`, `script.py.mako`, premier `revision`)
- Coder l'auth JWT (access + refresh, bcrypt, `get_current_user`)
- Configurer pydantic-settings pour le 12-factor
- Configurer le CORS sans le casser (`allow_credentials=True` + `allow_origins=["*"]` ne marche pas, surprise !)
- Mettre en place pytest-asyncio avec une DB isolee par test
- Ecrire un Dockerfile
- ...et seulement la, je peux ecrire ma premiere ligne de code metier.

J'ai fait ce parcours sur 4 projets en 2025. Au 5e, j'ai dit non.

## Django ne m'allait pas

Django resout tout ca, oui. Mais :

- **Tout est synchrone** : sur une route qui attend un appel OpenAI ou un
  `pg_query` lourd, le worker est bloque
- **L'ORM Django** n'est pas SQLAlchemy. J'aime SQLAlchemy
- **Django Admin** est genial, mais il est tellement integre que tu ne peux
  pas le sortir de son ecosysteme
- **L'architecture monolithique** est dure a casser en microservices si ton
  projet explose

## FastAPI seul ne suffit pas non plus

FastAPI est un moteur excellent. Mais c'est un moteur. Tu dois tout coder
toi-meme. Pour un dev solo ou une petite equipe, c'est 2 jours perdus par
projet.

J'ai cherche un middle-ground : la productivite de Django avec la
flexibilite + l'async de FastAPI.

J'ai rien trouve qui me satisfasse.

J'ai donc ecrit **Fabrik**.

## Fabrik en 60 secondes

```bash
pip install fabrik-fastapi
fabrik new mon-api
cd mon-api
venv\Scripts\activate
python create_superuser.py
python -m uvicorn main:app --reload
```

Et la, ouvre `http://127.0.0.1:8000/admin` dans ton navigateur :

- Login admin (utilise le compte que tu viens de creer)
- Sidebar avec les modeles (pour l'instant : `users`)
- Dashboard avec stats + activite recente + quick links
- Liste paginee avec recherche multi-colonnes + bulk delete + export CSV
- Formulaires CRUD generes automatiquement depuis les colonnes SQLAlchemy

`/docs` te donne Swagger. `/redoc` te donne ReDoc.

Et tu as deja :
- JWT (access + refresh tokens)
- DB SQLite (passe en PostgreSQL avec une variable d'env)
- Tests isoles : `pytest tests/` tourne avec une DB in-memory toute fraiche
- Alembic configure
- Docker `Dockerfile` + `docker-compose.yml` pour Redis
- ARQ pour les background tasks (avec degradation gracieuse si Redis est down)

## Ajouter un module : 1 commande

Disons que tu veux ajouter des produits :

```bash
fabrik add products
```

Fabrik :

1. Cree `src/product/` avec 5 fichiers : `models.py`, `schemas.py`,
   `service.py`, `router.py`, plus le test `tests/test_product.py`
2. **Modifie automatiquement** :
   - `main.py` : ajoute `from src.product.router import router as products_router`
     puis `app.include_router(products_router)`
   - `alembic/env.py` : ajoute `import src.product.models`
   - `src/users/models.py` : ajoute `products = relationship("Product", back_populates="author")`
3. Lance `alembic revision --autogenerate -m "add_product"` puis `upgrade head`
4. Joue `pytest tests/test_product.py` (4 tests par defaut)
5. **Le module apparait automatiquement dans l'admin UI** (auto-discovery
   via `Base.registry.mappers`)

Tu n'as plus qu'a ouvrir `src/product/models.py` et ajouter tes colonnes :

```python
class Product(TimestampMixin, Base):
    __tablename__ = "products"
    id          = Column(String, primary_key=True, default=generate_id)
    title       = Column(String, nullable=False, index=True)
    price       = Column(Numeric(10, 2), nullable=False)         # NOUVEAU
    stock       = Column(Integer, nullable=False, default=0)     # NOUVEAU
    is_active   = Column(Boolean, default=True)                  # NOUVEAU
    user_id     = Column(String, ForeignKey("users.id"))
    author      = relationship("User", back_populates="products")
```

Puis re-genere la migration et `upgrade`. C'est tout. L'admin detecte
automatiquement les nouvelles colonnes (price -> input `number`, is_active
-> `checkbox`, user_id -> dropdown FK avec emails resolus).

## Sous le capot : 4 decisions opinionatedes

### 1. Tout est async, sans compromis

`AsyncSession` partout. Toutes les routes en `async def`. ARQ pour les
background tasks. Le lifespan FastAPI gere la creation/cleanup du pool DB.

Pourquoi ? Un seul process Python peut servir des milliers de
requetes/seconde si l'I/O n'est pas bloque. Le cout : tu dois ecrire
`await db.execute(select(...))` au lieu de `db.query(...).all()`. C'est le
standard SQLAlchemy 2.0.

### 2. Admin UI par auto-discovery

Plutot que de demander a l'utilisateur de declarer ses modeles dans l'admin
(a la Django `admin.site.register()`), Fabrik **scanne dynamiquement** :

```python
def get_admin_models() -> dict:
    return {m.class_.__tablename__: m.class_ for m in Base.registry.mappers}
```

Resultat : zero configuration. Tu ajoutes une classe SQLAlchemy, elle
apparait dans la sidebar. Les types de colonnes sont mappes vers les bons
inputs HTML (`Boolean` -> checkbox, FK -> dropdown). Les UUIDs sont
tronques. Les booleens s'affichent comme badges colores. Les FK sont
resolues en batch et affichees comme liens avec l'email/nom de l'objet
cible.

### 3. ARQ plutot que Celery pour les background tasks

Celery, c'est le standard de l'industrie. Mais c'est ne avant async Python
et necessite plus de plomberie pour cohabiter avec FastAPI. ARQ est
async-native, ecrit pour Python 3.7+, et tient dans 3000 lignes.

Bonus : **degradation gracieuse**. Si Redis est down, l'API marche quand
meme. Les routes qui veulent enqueue retournent 503 ; le reste fonctionne
sans difference. Tu n'as pas besoin de Redis pour developper.

### 4. Versioning du scaffold + patches idempotents

J'ai eu le probleme suivant : je modifie Fabrik, mais mes 10 projets deja
generes restent figes a l'ancienne version. Soit je copie/colle les fixes
dans chaque projet (corvee), soit je perds tout.

Solution : chaque projet genere ecrit un `.scaffold-version` (JSON avec la
version qui l'a cree). Quand je bump Fabrik, j'ajoute une fonction
`patch_vN_to_vM(root)` idempotente dans `PATCHES`. Les utilisateurs lancent
`fabrik upgrade` dans leurs projets, et les patches sont appliques en
chaine (avec backups `.bak` automatiques).

```python
PATCHES = [
    {
        "from": 1, "to": 2,
        "name": "Add rate limiting middleware",
        "apply": patch_v1_to_v2,
    },
]
```

## test-self : la garantie que ca marche

Le risque d'un generateur de code : un commit casse les projets generes
sans qu'on s'en rende compte avant qu'un utilisateur essaie. Fabrik a une
parade : `fabrik test-self`.

Cette commande :

1. Cree un projet jetable dans `/tmp/scaffold-test-xxx`
2. Lance la generation complete (venv + deps + migration)
3. Joue toute la suite pytest
4. Demarre uvicorn sur un port libre
5. Fait des HTTP GET sur `/`, `/admin/login`, `/docs` (verifie HTTP 200)
6. Ajoute un module via `fabrik add`
7. Verifie que les fichiers generes sont du Python valide
8. Nettoie le tempdir

Le tout en 60-120 secondes. Bonus : c'est lance dans la CI GitHub Actions
a chaque commit. Si un commit casse la generation, je le sais avant
release.

## Pour qui ?

- **Dev solo** qui demarre un MVP / un projet client
- **Petite equipe** qui veut une structure coherente sans imposer Django
- **Startup** en phase 0-100 utilisateurs qui prevoit de scaler

Pas pour :
- Une equipe qui a deja un standard interne et n'en veut pas changer
- Quelqu'un qui veut un framework "tout faire" avec admin, ecosysteme,
  plugins... -> prends Django

## Limites assumees

- **Python 3.13+ seulement** : j'utilise les nouveautes recentes, je ne
  supporte pas les anciennes versions
- **Pas de plugins externes** : Fabrik est monolithique par choix.
  Pour un module specialise (OAuth Google, Stripe...), copie le code dans
  `src/<module>/`, pas `pip install fabrik-plugin-x`
- **L'admin scanne TOUS les modeles** : pas (encore) de mecanisme pour
  exclure certains modeles internes

## Roadmap

- v1.1 : RBAC (roles + permissions par modele dans l'admin)
- v1.2 : graphes Chart.js sur le dashboard admin
- v1.3 : tests d'integration avec un vrai Redis dans la CI
- v2.0 : multi-tenancy + ACL granulaire

## Try it

```bash
pip install fabrik-fastapi
fabrik new mon-api
```

- **PyPI** : https://pypi.org/project/fabrik-fastapi/
- **GitHub** : https://github.com/FalandyJEAN/fabrik
- **Docs** : https://github.com/FalandyJEAN/fabrik/blob/main/docs/USAGE.md
- **Issues** : https://github.com/FalandyJEAN/fabrik/issues

Si Fabrik te fait gagner 2 jours sur ton prochain projet, file-moi une
star sur GitHub :)

---

*Falandy Jean &mdash; auteur de Fabrik, dev backend Python a son compte. Licence MIT.*

---

**Tags :** `python` `fastapi` `sqlalchemy` `async` `cli` `scaffold` `framework`
