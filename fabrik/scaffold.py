#!/usr/bin/env python3
"""
Fabrik -- Generateur de projet FastAPI async + opinionated.

Commandes :
  fabrik new <nom>       -- Creer un nouveau projet
  fabrik add <module>    -- Ajouter un module (depuis la racine du projet)
  fabrik upgrade         -- Mettre a jour un projet existant
  fabrik test-self       -- Meta-test du scaffold
"""

import os
import sys
import subprocess
import platform
import argparse
import secrets
import json
from datetime import datetime
from pathlib import Path
from string import Template


# ───────────────────────────────────────────────────────────────────────────────
# Version du scaffold -- bumpe a chaque breaking change dans les templates.
# Voir la registry PATCHES pour les migrations entre versions.
# ───────────────────────────────────────────────────────────────────────────────
SCAFFOLD_VERSION = 1


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI DESIGN -- couleurs ANSI + symboles Unicode avec fallback ASCII
# ═══════════════════════════════════════════════════════════════════════════════

# Force UTF-8 sur Windows pour pouvoir afficher les symboles Unicode (cocher,
# fleches, encadres, etc.) sans UnicodeEncodeError sur cp1252.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Active les couleurs ANSI sur Windows 10+ (VT100 sequences)
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


class _C:
    """Codes ANSI -- desactives si stdout n'est pas un TTY (CI, pipes, etc.)."""
    _enabled = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    RESET   = "\033[0m"   if _enabled else ""
    BOLD    = "\033[1m"   if _enabled else ""
    DIM     = "\033[2m"   if _enabled else ""

    RED     = "\033[31m"  if _enabled else ""
    GREEN   = "\033[32m"  if _enabled else ""
    YELLOW  = "\033[33m"  if _enabled else ""
    BLUE    = "\033[34m"  if _enabled else ""
    MAGENTA = "\033[35m"  if _enabled else ""
    CYAN    = "\033[36m"  if _enabled else ""
    GRAY    = "\033[90m"  if _enabled else ""

    BR_GREEN = "\033[92m" if _enabled else ""
    BR_CYAN  = "\033[96m" if _enabled else ""


# Symboles : Unicode si stdout supporte UTF-8, sinon fallback ASCII
def _can_unicode() -> bool:
    enc = (sys.stdout.encoding or "").lower().replace("-", "")
    return enc in ("utf8", "utf16", "utf32")


_UNI = _can_unicode()
SYM_OK   = "✓" if _UNI else "OK"
SYM_FAIL = "✗" if _UNI else "X "
SYM_WARN = "!" if _UNI else "! "
SYM_INFO = "i" if _UNI else "i "
SYM_STEP = "›" if _UNI else ">"
SYM_DOT  = "·" if _UNI else "."
SYM_ARROW = "→" if _UNI else "->"
LINE_H   = "─" if _UNI else "-"
LINE_HH  = "━" if _UNI else "="
BOX_TL   = "╭" if _UNI else "+"
BOX_TR   = "╮" if _UNI else "+"
BOX_BL   = "╰" if _UNI else "+"
BOX_BR   = "╯" if _UNI else "+"
BOX_V    = "│" if _UNI else "|"
BOX_H    = "─" if _UNI else "-"


def success(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{_C.BR_GREEN}{SYM_OK}{_C.RESET}  {msg}")


def fail(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{_C.RED}{SYM_FAIL}{_C.RESET}  {msg}")


def warn(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{_C.YELLOW}{SYM_WARN}{_C.RESET}  {msg}")


def info(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{_C.BLUE}{SYM_INFO}{_C.RESET}  {msg}")


def step(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{_C.CYAN}{SYM_STEP}{_C.RESET}  {msg}")


def dim(msg: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{_C.DIM}{msg}{_C.RESET}")


def header(title: str, subtitle: str = "") -> None:
    """Encadre un titre principal avec une ligne au-dessus et en-dessous."""
    line = LINE_HH * 60
    print()
    print(f"{_C.GRAY}{line}{_C.RESET}")
    print(f"  {_C.BOLD}{title}{_C.RESET}", end="")
    if subtitle:
        print(f"  {_C.DIM}{SYM_DOT} {subtitle}{_C.RESET}")
    else:
        print()
    print(f"{_C.GRAY}{line}{_C.RESET}")


def section(title: str) -> None:
    """Sous-titre de section avec une simple ligne au-dessus."""
    print()
    print(f"  {_C.BOLD}{title}{_C.RESET}")
    print(f"  {_C.GRAY}{LINE_H * (len(title) + 2)}{_C.RESET}")


def box(lines: list, color: str = "") -> None:
    """Affiche un encadre rounded avec une liste de lignes a l'interieur."""
    width = max((len(_strip_ansi(ln)) for ln in lines), default=40)
    width = max(width, 50)
    c = color or _C.CYAN
    print()
    print(f"  {c}{BOX_TL}{BOX_H * (width + 2)}{BOX_TR}{_C.RESET}")
    for ln in lines:
        visible_len = len(_strip_ansi(ln))
        pad = " " * (width - visible_len)
        print(f"  {c}{BOX_V}{_C.RESET} {ln}{pad} {c}{BOX_V}{_C.RESET}")
    print(f"  {c}{BOX_BL}{BOX_H * (width + 2)}{BOX_BR}{_C.RESET}")
    print()


def _strip_ansi(s: str) -> str:
    """Supprime les codes ANSI pour calculer la longueur visible."""
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)


def kv(key: str, value: str, key_width: int = 12, indent: int = 4) -> None:
    """Affiche une paire cle/valeur alignee : 'Serveur     uvicorn ...'."""
    print(f"{' ' * indent}{_C.DIM}{key.ljust(key_width)}{_C.RESET} {value}")


def bold(text: str) -> str:
    return f"{_C.BOLD}{text}{_C.RESET}"


def cyan(text: str) -> str:
    return f"{_C.CYAN}{text}{_C.RESET}"


def gray(text: str) -> str:
    return f"{_C.GRAY}{text}{_C.RESET}"


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMPLATES — NOUVEAU PROJET
# ═══════════════════════════════════════════════════════════════════════════════

def build_files(title: str, port: int, db_url: str) -> dict:
    """
    Construit le dict {chemin_relatif: contenu} pour un nouveau projet.
    Les fichiers proviennent de /core/ :
      - /core/_templates/*.tpl      -> substitution ${title}, ${port}, ${db_url}, ${secret_key}
      - /core/<reste>               -> copies tels quels
    """
    files = {}
    core_dir = Path(__file__).parent / "core"

    # 1. Fichiers templates (substitution)
    secret_key = secrets.token_urlsafe(32)
    tpl_subst = {
        "title":      title,
        "port":       str(port),
        "db_url":     db_url,
        "secret_key": secret_key,
    }
    tpl_to_target = {
        "main.py.tpl":       "main.py",
        "env.tpl":           ".env",
        "Dockerfile.tpl":    "Dockerfile",
    }
    tpl_dir = core_dir / "_templates"
    for tpl_name, target in tpl_to_target.items():
        raw = (tpl_dir / tpl_name).read_text(encoding="utf-8")
        files[target] = Template(raw).substitute(**tpl_subst)

    # 2. Fichiers statiques (copies directes)
    for path in core_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(core_dir)
        # Skip _templates (deja traites)
        if rel.parts[0] == "_templates":
            continue
        files[str(rel).replace(os.sep, "/")] = path.read_text(encoding="utf-8")

    return files


MODULE_MODELS = Template('''\
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base
from src.core.mixins import TimestampMixin
import uuid


def generate_id():
    return str(uuid.uuid4())


class ${Model}(TimestampMixin, Base):
    __tablename__ = "${modules}"

    id      = Column(String, primary_key=True, default=generate_id)
    title   = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    author  = relationship("User", back_populates="${modules}")

    # Ajoute tes champs ici :
    # description  = Column(String, nullable=True)
    # is_published = Column(Boolean, default=False)
''')

MODULE_SCHEMAS = Template('''\
from pydantic import BaseModel
from src.core.pagination import Page


class ${Model}Create(BaseModel):
    title: str
    # Ajoute tes champs ici


class ${Model}Response(BaseModel):
    id: str
    title: str
    user_id: str

    class Config:
        from_attributes = True


class ${Model}Update(BaseModel):
    title: str | None = None
    # Ajoute tes champs ici


${Model}Page = Page[${Model}Response]
''')

MODULE_SERVICE = Template('''\
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from . import models, schemas
from src.core.pagination import paginate

logger = logging.getLogger(__name__)


async def create_${module}(db: AsyncSession, data: schemas.${Model}Create, user_id: str):
    item = models.${Model}(title=data.title, user_id=user_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    logger.info("${Model} cree : %s", item.id)
    return item


async def get_${module}(db: AsyncSession, item_id: str):
    result = await db.execute(select(models.${Model}).where(models.${Model}.id == item_id))
    return result.scalar_one_or_none()


async def list_${modules}(db: AsyncSession, user_id: str, page: int = 1, limit: int = 20):
    stmt = select(models.${Model}).where(models.${Model}.user_id == user_id)
    return await paginate(db, stmt, page, limit)


async def update_${module}(db: AsyncSession, item_id: str, data: schemas.${Model}Update):
    item = await get_${module}(db, item_id)
    if not item:
        return None
    if data.title is not None:
        item.title = data.title
    await db.commit()
    await db.refresh(item)
    return item


async def delete_${module}(db: AsyncSession, item_id: str):
    item = await get_${module}(db, item_id)
    if item:
        await db.delete(item)
        await db.commit()
        return True
    return False
''')

MODULE_ROUTER = Template('''\
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from . import schemas, service
from src.database import get_db
from src.core.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/${modules}", tags=["${Models}"])


@router.post("/", response_model=schemas.${Model}Response, status_code=201)
async def create_${module}(
    data: schemas.${Model}Create,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    return await service.create_${module}(db, data, user_id)


@router.get("/", response_model=schemas.${Model}Page)
async def list_${modules}(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    return await service.list_${modules}(db, user_id, page=page, limit=limit)


@router.get("/{item_id}", response_model=schemas.${Model}Response)
async def get_${module}(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    item = await service.get_${module}(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="${Model} introuvable")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Action non autorisee")
    return item


@router.put("/{item_id}", response_model=schemas.${Model}Response)
async def update_${module}(
    item_id: str,
    data: schemas.${Model}Update,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    item = await service.get_${module}(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="${Model} introuvable")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Action non autorisee")
    return await service.update_${module}(db, item_id, data)


@router.delete("/{item_id}", status_code=204)
async def delete_${module}(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    item = await service.get_${module}(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="${Model} introuvable")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Action non autorisee")
    await service.delete_${module}(db, item_id)
''')

MODULE_TESTS = Template('''\
EMAIL = "test${module}@example.com"
PASSWORD = "password123"


async def get_token(client):
    await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    r = await client.post("/users/login", json={"email": EMAIL, "password": PASSWORD})
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_create_${module}(client):
    token = await get_token(client)
    r = await client.post("/${modules}/", json={"title": "Test"}, headers=auth(token))
    assert r.status_code == 201
    assert r.json()["title"] == "Test"


async def test_list_${modules}(client):
    token = await get_token(client)
    r = await client.get("/${modules}/", headers=auth(token))
    assert r.status_code == 200
    assert "items" in r.json()
    assert "total" in r.json()


async def test_get_${module}_not_found(client):
    token = await get_token(client)
    r = await client.get("/${modules}/inexistant", headers=auth(token))
    assert r.status_code == 404


async def test_create_${module}_unauthorized(client):
    r = await client.post("/${modules}/", json={"title": "Test"})
    assert r.status_code == 401
''')


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def run_cmd(cmd: list, cwd: Path) -> bool:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0 and r.stderr:
        print(f"    [!] {r.stderr.strip()[:200]}")
    return r.returncode == 0


def to_pascal(name: str) -> str:
    return "".join(w.capitalize() for w in name.replace("-", "_").split("_"))


def ask(question: str, default: str) -> str:
    answer = input(f"  {question} [{default}] : ").strip()
    return answer if answer else default


def _insert_after(content: str, anchor: str, new_line: str) -> tuple:
    """
    Insere new_line apres la premiere ligne contenant anchor.
    Idempotent : compare ligne-a-ligne (strip) pour ne pas matcher les exemples commentes.
    Renvoie (nouveau_contenu, a_modifie).
    """
    stripped = new_line.strip()
    if not stripped:
        return content, False
    # Idempotence : verifie qu'aucune ligne (strip) n'est exactement egale a new_line.
    # Evite de matcher un exemple comme `# app.include_router(videos_router)`.
    if any(ln.strip() == stripped for ln in content.splitlines()):
        return content, False
    if anchor not in content:
        return content, False
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if anchor in line:
            if not new_line.endswith("\n"):
                new_line += "\n"
            lines.insert(i + 1, new_line)
            return "".join(lines), True
    return content, False


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDE : new
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_new(project_name: str, no_input: bool):
    root = Path(project_name).resolve()

    if root.exists():
        fail(f"Le dossier {bold(project_name)} existe deja.")
        sys.exit(1)

    # Titre = nom du dossier final uniquement (pas le chemin absolu)
    display_name = root.name
    title = display_name.replace("-", "_").replace("_", " ").title()

    header(f"Fabrik · Nouveau projet", title)

    # ── Questions interactives ────────────────────────────────────
    if not no_input:
        title  = ask("Titre de l'API", title)
        port   = int(ask("Port", "8000"))
        db_choice = ask("Base de donnees  [1] SQLite  [2] PostgreSQL", "1")
        if db_choice == "2":
            db_url = ask("DATABASE_URL PostgreSQL", "postgresql://user:password@localhost:5432/mydb")
        else:
            db_url = "sqlite:///./app.db"
    else:
        port   = 8000
        db_url = "sqlite:///./app.db"

    # ── Dossiers ──────────────────────────────────────────────────
    for d in ["src/core", "src/users", "src/admin/templates", "src/admin/static",
              "alembic/versions", "tests"]:
        (root / d).mkdir(parents=True, exist_ok=True)
    success("Arborescence creee")

    # ── Fichiers projet (tous viennent de /core/) ────────────────
    files = build_files(title, port, db_url)
    for path, content in files.items():
        f = root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")

    # Etat du scaffold (utilise par `fabrik upgrade`)
    scaffold_state = {
        "scaffold_version": SCAFFOLD_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "patches_applied": [],
    }
    (root / ".scaffold-version").write_text(
        json.dumps(scaffold_state, indent=2), encoding="utf-8",
    )
    success(f"{len(files)} fichiers generes depuis /core/")

    # ── Venv ──────────────────────────────────────────────────────
    venv_dir = root / "venv"
    step("Creation du venv...")
    if run_cmd([sys.executable, "-m", "venv", str(venv_dir)], root):
        success("Venv pret")
    else:
        warn("Venv echoue -- cree manuellement : python -m venv venv")

    is_win = platform.system() == "Windows"
    pip    = str(venv_dir / ("Scripts/pip.exe" if is_win else "bin/pip"))
    python = str(venv_dir / ("Scripts/python.exe" if is_win else "bin/python"))

    # ── Dependances ───────────────────────────────────────────────
    step("Installation des dependances (1-2 min)...")
    if run_cmd([pip, "install", "-r", "requirements.txt", "-q"], root):
        success("Dependances installees")
    else:
        warn(f"Lance manuellement : pip install -r requirements.txt")

    # ── Migration initiale ────────────────────────────────────────
    step("Migration initiale Alembic...")
    ok = run_cmd([python, "-m", "alembic", "revision", "--autogenerate", "-m", "initial_schema"], root)
    if ok:
        run_cmd([python, "-m", "alembic", "upgrade", "head"], root)
        success("Base de donnees initialisee")
    else:
        warn(f"Lance manuellement : alembic revision --autogenerate -m initial_schema")
        warn(f"                     alembic upgrade head")

    # ── Resume ────────────────────────────────────────────────────
    activate   = "venv\\Scripts\\Activate.ps1" if is_win else "source venv/bin/activate"

    box([
        f"{bold('Projet')} {cyan(title)} {gray('· async · FastAPI + SQLAlchemy 2.0')}",
    ], color=_C.GREEN)

    section("Demarrer")
    kv("cd",          project_name)
    kv("activate",    activate)
    kv("superuser",   "python create_superuser.py")
    kv("serveur",     "python -m uvicorn main:app --reload")

    section("URLs locales")
    kv("API",         cyan(f"http://127.0.0.1:{port}"))
    kv("Swagger",     cyan(f"http://127.0.0.1:{port}/docs"))
    kv("Admin",       cyan(f"http://127.0.0.1:{port}/admin"))

    section("Background tasks (optionnel)")
    kv("Redis",       gray("docker compose up -d redis"))
    kv("Worker",      gray("python worker.py"))

    section("Ajouter un module")
    kv("CLI",         f"{bold('fabrik add')} {gray('<nom-du-module>')}")

    print()


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDE : add
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_add(module_name: str, no_migrate: bool = False, no_wire: bool = False, no_test: bool = False):
    root = Path(".").resolve()

    # Verification qu'on est dans un projet FastAPI scaffold
    if not (root / "main.py").exists() or not (root / "src").exists():
        fail("Lance cette commande depuis la racine d'un projet scaffold.")
        dim("(le dossier doit contenir main.py et src/)")
        sys.exit(1)

    module   = module_name.lower().replace("-", "_").rstrip("s")  # force singulier
    modules  = module + "s"
    Model    = to_pascal(module)
    Models   = to_pascal(modules)
    mod_dir  = root / "src" / module

    if mod_dir.exists():
        fail(f"Le module {bold(module)} existe deja dans src/")
        sys.exit(1)

    vars_ = {
        "module":  module,
        "modules": modules,
        "Model":   Model,
        "Models":  Models,
    }

    header(f"Fabrik · Nouveau module", module)

    # ── 1. Fichiers du module ─────────────────────────────────────
    mod_dir.mkdir(parents=True)
    (mod_dir / "__init__.py").write_text("", encoding="utf-8")
    (mod_dir / "models.py").write_text(MODULE_MODELS.substitute(**vars_), encoding="utf-8")
    (mod_dir / "schemas.py").write_text(MODULE_SCHEMAS.substitute(**vars_), encoding="utf-8")
    (mod_dir / "service.py").write_text(MODULE_SERVICE.substitute(**vars_), encoding="utf-8")
    (mod_dir / "router.py").write_text(MODULE_ROUTER.substitute(**vars_), encoding="utf-8")

    # ── 2. Tests ──────────────────────────────────────────────────
    tests_dir = root / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / f"test_{module}.py").write_text(MODULE_TESTS.substitute(**vars_), encoding="utf-8")

    success(f"src/{module}/ {gray('(models, schemas, service, router)')}")
    success(f"tests/test_{module}.py")

    # ── 3. Auto-wiring ────────────────────────────────────────────
    if no_wire:
        section("Auto-wiring")
        info("Desactive (--no-wire). Branche manuellement.")
    else:
        section("Auto-wiring")
        # main.py : import + include_router
        main_py = root / "main.py"
        if main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            new_import  = f"from src.{module}.router import router as {modules}_router"
            new_include = f"app.include_router({modules}_router)"
            content, a1 = _insert_after(content,
                "from src.admin.router import router as admin_router", new_import)
            content, a2 = _insert_after(content,
                "app.include_router(admin_router)", new_include)
            if a1 or a2:
                main_py.write_text(content, encoding="utf-8")
                success(f"{cyan('main.py'):<40}  {gray('import + include_router')}")
            else:
                info(f"{cyan('main.py'):<40}  {gray('deja branche')}")

        # alembic/env.py : import du modele
        env_py = root / "alembic" / "env.py"
        if env_py.exists():
            content = env_py.read_text(encoding="utf-8")
            new_imp = f"import src.{module}.models  # noqa: F401"
            content, a = _insert_after(content,
                "import src.users.models  # noqa: F401", new_imp)
            if a:
                env_py.write_text(content, encoding="utf-8")
                success(f"{cyan('alembic/env.py'):<40}  {gray('import du modele')}")
            else:
                info(f"{cyan('alembic/env.py'):<40}  {gray('deja a jour')}")

        # src/users/models.py : relation back_populates
        users_models = root / "src" / "users" / "models.py"
        if users_models.exists():
            content = users_models.read_text(encoding="utf-8")
            new_rel = f'    {modules} = relationship("{Model}", back_populates="author")'
            content, a = _insert_after(content, "# Ajoute tes relations ici :", new_rel)
            if a:
                users_models.write_text(content, encoding="utf-8")
                success(f"{cyan('src/users/models.py'):<40}  {gray(f'relation {modules}')}")
            else:
                info(f"{cyan('src/users/models.py'):<40}  {gray('deja a jour')}")

    # ── 4. Migration alembic automatique ──────────────────────────
    is_win = platform.system() == "Windows"
    venv_python = root / "venv" / ("Scripts/python.exe" if is_win else "bin/python")

    if no_migrate:
        section("Migration Alembic")
        info("Desactivee (--no-migrate). Lance manuellement :")
        dim(f"    alembic revision --autogenerate -m \"add_{module}\"")
        dim(f"    alembic upgrade head")
    elif not venv_python.exists():
        section("Migration Alembic")
        warn("Venv introuvable. Lance manuellement :")
        dim(f"    alembic revision --autogenerate -m \"add_{module}\"")
        dim(f"    alembic upgrade head")
    else:
        section("Migration Alembic")
        step("Generation + application...")
        ok1 = run_cmd([str(venv_python), "-m", "alembic",
                       "revision", "--autogenerate", "-m", f"add_{module}"], root)
        if ok1:
            ok2 = run_cmd([str(venv_python), "-m", "alembic", "upgrade", "head"], root)
            if ok2:
                success(f"Migration appliquee {gray(f'(add_{module})')}")
            else:
                warn("Migration generee mais 'upgrade head' a echoue")
        else:
            warn("Generation de migration echouee (verifie le venv)")

    # ── 5. Auto-test du nouveau module ────────────────────────────
    if no_test:
        section("Tests")
        info("Auto-test desactive (--no-test).")
    elif not venv_python.exists():
        section("Tests")
        info("Venv introuvable, tests non joues.")
    else:
        section("Tests")
        import re
        test_file = root / "tests" / f"test_{module}.py"
        r = subprocess.run(
            [str(venv_python), "-m", "pytest", str(test_file), "-q", "--tb=line"],
            cwd=root, capture_output=True, text=True,
        )
        m_pass = re.search(r"(\d+) passed",  r.stdout)
        m_fail = re.search(r"(\d+) failed",  r.stdout)
        n_pass = m_pass.group(1) if m_pass else "0"
        n_fail = m_fail.group(1) if m_fail else "0"
        if r.returncode == 0:
            success(f"{bold(n_pass)} test(s) du module passent")
        else:
            warn(f"{bold(n_fail)} echec(s) / {n_pass} OK")
            dim(f"    pytest tests/test_{module}.py -v  pour le detail")

    # ── 6. Resume ─────────────────────────────────────────────────
    box([
        f"{bold('Module')} {cyan(module)} {gray('· branche · visible dans /admin')}",
    ], color=_C.GREEN)

    section("Personnaliser")
    kv("models",     f"src/{module}/models.py    {gray('colonnes SQLAlchemy')}", key_width=10)
    kv("schemas",    f"src/{module}/schemas.py   {gray('champs Pydantic')}",     key_width=10)
    kv("router",     f"src/{module}/router.py    {gray('endpoints HTTP')}",      key_width=10)

    section("Apres modification des colonnes")
    dim(f"    alembic revision --autogenerate -m \"update_{module}\"")
    dim(f"    alembic upgrade head")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDE : upgrade  -- met a jour un projet genere a une version anterieure
# ═══════════════════════════════════════════════════════════════════════════════

# Registry des patches : chaque breaking change ajoute une entree ici.
# Format : {"from": N, "to": N+1, "name": "description", "apply": fn(root: Path) -> dict}
# La fonction apply doit etre idempotente et retourner {chemin: statut}.
#
# Exemple d'ajout futur :
#   def patch_v1_to_v2(root: Path) -> dict:
#       # modifications idempotentes des fichiers du projet
#       return {"src/admin/router.py": "patched"}
#
#   PATCHES.append({"from": 1, "to": 2, "name": "...", "apply": patch_v1_to_v2})

PATCHES: list = []


def cmd_upgrade(dry_run: bool = False) -> bool:
    root = Path(".").resolve()

    if not (root / "main.py").exists() or not (root / "src").exists():
        fail("Lance cette commande depuis la racine d'un projet scaffold.")
        sys.exit(1)

    state_file = root / ".scaffold-version"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {"scaffold_version": 1, "patches_applied": []}
    else:
        # Projet pre-versioning : assume v1
        state = {"scaffold_version": 1, "patches_applied": []}

    current = state.get("scaffold_version", 1)
    target  = SCAFFOLD_VERSION

    header("Fabrik · Upgrade", f"v{current} {SYM_ARROW} v{target}")

    if current >= target:
        success(f"Projet deja a jour {gray(f'(v{current})')}")
        print()
        return True

    to_apply = [p for p in PATCHES if p["from"] >= current and p["to"] <= target]
    if not to_apply:
        warn(f"Aucun patch defini entre v{current} et v{target}.")
        print()
        return False

    info(f"{bold(str(len(to_apply)))} patch(es) a appliquer :")
    for p in to_apply:
        version_arrow = gray(f"v{p['from']} {SYM_ARROW} v{p['to']}")
        print(f"      {version_arrow}  {p['name']}")

    if dry_run:
        print()
        warn(f"{bold('[DRY-RUN]')} Aucune modification ecrite.")
        dim("    Relance sans --dry-run pour appliquer.")
        print()
        return True

    for p in to_apply:
        section(f"Patch v{p['from']} {SYM_ARROW} v{p['to']}")
        try:
            res = p["apply"](root)
            for path, status in res.items():
                if "skip" in status.lower() or "deja" in status.lower():
                    info(f"{cyan(path):<40}  {gray(status)}")
                elif "fail" in status.lower() or "missing" in status.lower():
                    warn(f"{cyan(path):<40}  {status}")
                else:
                    success(f"{cyan(path):<40}  {gray(status)}")
            state["scaffold_version"] = p["to"]
            state.setdefault("patches_applied", []).append({
                "from": p["from"], "to": p["to"], "name": p["name"],
                "applied_at": datetime.now().isoformat(timespec="seconds"),
            })
        except Exception as e:
            fail(f"Echec : {type(e).__name__}: {e}")
            return False

    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    box([
        f"{bold('Projet a jour')} {gray(f'· version v{target}')}",
    ], color=_C.GREEN)
    dim(f"  Historique des patches : .scaffold-version")
    print()
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDE : test-self  -- meta-test du scaffold lui-meme
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_test_self(keep: bool = False) -> bool:
    """
    Genere un projet jetable, lance migrations + pytest + serveur + add module,
    nettoie tout, et retourne True si tout passe.
    """
    import tempfile
    import socket
    import time
    import shutil
    import stat
    import urllib.request
    import urllib.error
    import re

    header("Fabrik · test-self", "self-test du scaffold")
    dim("  Genere un projet complet, lance pytest + uvicorn + add module,")
    dim("  puis nettoie tout. Compte 60-120 secondes selon ta connexion.")

    results: list = []

    def record(name: str, status: str, elapsed: float, detail: str = ""):
        results.append((name, status, elapsed, detail))
        time_str = gray(f"{elapsed:5.1f}s")
        suffix = f"  {gray(detail)}" if detail else ""
        line = f"{name:<42s} {time_str}{suffix}"
        if status == "ok":
            success(line)
        elif status == "fail":
            fail(line)
        else:
            info(line)

    tmp = tempfile.mkdtemp(prefix="scaffold-test-")
    project_dir = Path(tmp) / "test_project"
    proc = None

    try:
        # ── 1. Generation du projet ─────────────────────────────────
        section("Generation du projet")
        dim("  Logs de cmd_new ci-dessous (venv + pip + alembic)...")
        t0 = time.time()
        try:
            cmd_new(str(project_dir), no_input=True)
        except SystemExit as e:
            record("Generation projet (cmd_new)", "fail", time.time() - t0, f"sys.exit({e.code})")
            return False
        except Exception as e:
            record("Generation projet (cmd_new)", "fail", time.time() - t0, f"{type(e).__name__}: {e}")
            return False

        section("Verifications")
        record("Generation projet (cmd_new)", "ok", time.time() - t0)

        # ── 2. Verification du venv ─────────────────────────────────
        t0 = time.time()
        is_win = platform.system() == "Windows"
        venv_python = project_dir / "venv" / ("Scripts/python.exe" if is_win else "bin/python")
        if venv_python.exists():
            record("Venv operationnel", "ok", time.time() - t0)
        else:
            record("Venv operationnel", "fail", time.time() - t0, "venv/python introuvable")
            return False

        # ── 3. Verification de la DB Alembic ────────────────────────
        t0 = time.time()
        db_file = project_dir / "app.db"
        versions = list((project_dir / "alembic" / "versions").glob("*.py"))
        if db_file.exists() and versions:
            record("Migration initiale Alembic", "ok", time.time() - t0,
                   f"{len(versions)} revision(s), DB {db_file.stat().st_size} bytes")
        else:
            record("Migration initiale Alembic", "fail", time.time() - t0,
                   f"db={db_file.exists()} versions={len(versions)}")

        # ── 4. Lancement de pytest ──────────────────────────────────
        t0 = time.time()
        r = subprocess.run(
            [str(venv_python), "-m", "pytest", "tests/", "-q", "--tb=short"],
            cwd=project_dir, capture_output=True, text=True,
        )
        passed_match = re.search(r"(\d+) passed", r.stdout)
        passed = passed_match.group(1) if passed_match else "?"
        if r.returncode == 0:
            record("pytest (suite complete)", "ok", time.time() - t0, f"{passed} tests OK")
        else:
            record("pytest (suite complete)", "fail", time.time() - t0, f"exit={r.returncode}")
            dim("    --- stdout (tail) ---")
            print("    " + r.stdout[-800:].replace("\n", "\n    "))
            dim("    --- stderr (tail) ---")
            print("    " + r.stderr[-400:].replace("\n", "\n    "))
            return False

        # ── 5. Demarrage du serveur uvicorn ─────────────────────────
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        t0 = time.time()
        proc = subprocess.Popen(
            [str(venv_python), "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        port_open = False
        deadline = time.time() + 25
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    port_open = True
                    break
            except OSError:
                time.sleep(0.3)

        if not port_open:
            stderr_tail = ""
            if proc.stderr:
                try:
                    stderr_tail = proc.stderr.read().decode("utf-8", errors="replace")[-400:]
                except Exception:
                    pass
            record("Uvicorn (port d'ecoute)", "fail", time.time() - t0, "port jamais ouvert")
            if stderr_tail:
                dim("    --- uvicorn stderr ---")
                print("    " + stderr_tail.replace("\n", "\n    "))
            return False
        record("Uvicorn (port d'ecoute)", "ok", time.time() - t0, f"port {port}")

        # ── 6-8. HTTP checks ────────────────────────────────────────
        def http_get(path: str):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read().decode("utf-8", errors="replace")

        for path, name, expect in [
            ("/",            "GET /  (health)",        '"status"'),
            ("/admin/login", "GET /admin/login (UI)",  "Console"),
            ("/docs",        "GET /docs  (Swagger)",   "swagger"),
        ]:
            t0 = time.time()
            try:
                status, body = http_get(path)
                if status == 200 and expect.lower() in body.lower():
                    record(name, "ok", time.time() - t0, f"HTTP 200 ({len(body)} B)")
                else:
                    record(name, "fail", time.time() - t0, f"HTTP {status}, '{expect}' absent")
                    return False
            except urllib.error.HTTPError as e:
                record(name, "fail", time.time() - t0, f"HTTP {e.code}")
                return False
            except Exception as e:
                record(name, "fail", time.time() - t0, f"{type(e).__name__}: {e}")
                return False

        # ── 9. Stop server ──────────────────────────────────────────
        t0 = time.time()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        proc = None
        record("Arret propre uvicorn", "ok", time.time() - t0)

        # ── 10. cmd_add (verifie la commande 'add') ─────────────────
        t0 = time.time()
        old_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            cmd_add("articles")
        except SystemExit as e:
            record("fabrik add articles", "fail", time.time() - t0, f"exit={e.code}")
            return False
        except Exception as e:
            record("fabrik add articles", "fail", time.time() - t0, f"{type(e).__name__}: {e}")
            return False
        finally:
            os.chdir(old_cwd)
        record("fabrik add articles", "ok", time.time() - t0)

        # Verify generated module parses
        t0 = time.time()
        import ast
        article_dir = project_dir / "src" / "articles"
        files_ok = True
        for fname in ["models.py", "schemas.py", "service.py", "router.py", "__init__.py"]:
            f = article_dir / fname
            if not f.exists():
                files_ok = False
                break
            try:
                ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                files_ok = False
                break
        if files_ok:
            record("Module articles/ (5 fichiers OK)", "ok", time.time() - t0)
        else:
            record("Module articles/ (5 fichiers OK)", "fail", time.time() - t0)
            return False

        return True

    except KeyboardInterrupt:
        print()
        warn("Interrompu par l'utilisateur")
        return False
    finally:
        # ── Stop server si encore vivant ─────────────────────────
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try: proc.kill()
                except Exception: pass

        # ── Cleanup ──────────────────────────────────────────────
        if keep:
            print()
            info(f"Projet de test conserve : {project_dir}")
        else:
            def _force_remove(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            shutil.rmtree(tmp, onerror=_force_remove)
            print()
            info(f"Nettoye : {tmp}")

        # ── Summary ──────────────────────────────────────────────
        passed_n = sum(1 for _, st, _, _ in results if st == "ok")
        failed_n = sum(1 for _, st, _, _ in results if st == "fail")
        total = passed_n + failed_n
        if failed_n == 0 and total > 0:
            box([
                f"{bold('Scaffold sain')} {gray(f'· {passed_n}/{total} etapes OK')}",
            ], color=_C.GREEN)
        else:
            box([
                f"{bold('Echec')} {gray(f'· {passed_n}/{total} OK, {failed_n} echec(s)')}",
            ], color=_C.RED)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTREE
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="fabrik",
        description="Fabrik -- Generateur de projet FastAPI async + opinionated.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  fabrik new api-videos
  fabrik new konprann-jwet --no-input
  fabrik add videos             (depuis la racine du projet)
  fabrik add video-category     (depuis la racine du projet)
  fabrik upgrade                (met a jour un projet ancien)
  fabrik upgrade --dry-run      (montre les patches sans les appliquer)
  fabrik test-self              (meta-test du scaffold, 1-2 min)
  fabrik test-self --keep       (garde le projet de test pour inspection)
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Creer un nouveau projet")
    p_new.add_argument("name", help="Nom du projet (ex: api-videos)")
    p_new.add_argument("--no-input", action="store_true", help="Utiliser les valeurs par defaut")

    p_add = sub.add_parser("add", help="Ajouter un module au projet courant")
    p_add.add_argument("module", help="Nom du module (ex: videos)")
    p_add.add_argument("--no-migrate", action="store_true",
                       help="Ne pas lancer alembic apres l'ajout")
    p_add.add_argument("--no-wire", action="store_true",
                       help="Ne pas modifier main.py / env.py / users.models")
    p_add.add_argument("--no-test", action="store_true",
                       help="Ne pas jouer pytest sur le nouveau module")

    p_upgrade = sub.add_parser("upgrade",
        help="Mettre a jour un projet existant a la derniere version du scaffold")
    p_upgrade.add_argument("--dry-run", action="store_true",
                           help="Afficher les patches sans les appliquer")

    p_test = sub.add_parser("test-self", help="Verifier que le scaffold est fonctionnel (1-2 min)")
    p_test.add_argument("--keep", action="store_true", help="Garder le projet genere au lieu de le supprimer")

    args = parser.parse_args()

    if args.command == "new":
        cmd_new(args.name, getattr(args, "no_input", False))
    elif args.command == "add":
        cmd_add(args.module,
                no_migrate=getattr(args, "no_migrate", False),
                no_wire=getattr(args, "no_wire", False),
                no_test=getattr(args, "no_test", False))
    elif args.command == "upgrade":
        ok = cmd_upgrade(dry_run=getattr(args, "dry_run", False))
        sys.exit(0 if ok else 1)
    elif args.command == "test-self":
        ok = cmd_test_self(keep=getattr(args, "keep", False))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
