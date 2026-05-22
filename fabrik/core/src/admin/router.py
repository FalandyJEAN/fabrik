import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from markupsafe import Markup
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, or_, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db, Base
from src.users.models import User
from src.core.security import verify_password, get_password_hash
from src.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="src/admin/templates")
ADMIN_COOKIE = "admin_session"
HIDDEN_FIELDS = {"password"}
READONLY_FIELDS = {"id", "created_at", "updated_at"}
FK_DISPLAY_CANDIDATES = ("email", "name", "title", "label", "username")


# ═══════════════════════════════════════════════════════════════════════
#  ICONES SVG (Lucide-style, stroke 1.75) -- pas d'emoji, partout
# ═══════════════════════════════════════════════════════════════════════

ICONS = {
    "home":      '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "users":     '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "logout":    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    "plus":      '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "search":    '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "edit":      '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><polygon points="18.5 2.5 21.5 5.5 12 15 9 15 9 12 18.5 2.5"/>',
    "trash":     '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "arrow-left":  '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
    "arrow-right": '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    "chevron-right": '<polyline points="9 18 15 12 9 6"/>',
    "check":     '<polyline points="20 6 9 17 4 12"/>',
    "x":         '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "zap":       '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "clock":     '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "book":      '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "database":  '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "box":       '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    "video":     '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>',
    "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "tag":       '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
    "shopping":  '<path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>',
    "layers":    '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "activity":  '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "external":  '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
    "code":      '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "save":      '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "shield":    '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "user":      '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "settings":  '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "menu":      '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
    "key":       '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
}

# Mapping table name -> nom d'icone (fallback : "database")
TABLE_ICON_MAP = {
    "users": "users", "user": "user",
    "videos": "video", "video": "video",
    "products": "box", "product": "box",
    "orders": "shopping", "order": "shopping",
    "articles": "file-text", "article": "file-text",
    "posts": "file-text", "post": "file-text",
    "categories": "tag", "category": "tag",
    "tags": "tag",
}


def icon(name: str, size: int = 18, klass: str = "") -> Markup:
    """Renvoie une balise SVG inline. Utilisable depuis Jinja : {{ icon('home') }}."""
    body = ICONS.get(name, ICONS["box"])
    cls = ("icon icon-" + name + " " + klass).strip()
    return Markup(
        '<svg xmlns="http://www.w3.org/2000/svg" width="' + str(size) +
        '" height="' + str(size) + '" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
        'stroke-linejoin="round" class="' + cls + '">' + body + '</svg>'
    )


def table_icon(table_name: str) -> str:
    return TABLE_ICON_MAP.get(table_name, "database")


def relative_time(dt: datetime) -> str:
    """Affichage humain d'une date : 'il y a 3 min', 'hier', etc."""
    if dt is None:
        return ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    s = int(delta.total_seconds())
    if s < 60: return "a l'instant"
    if s < 3600: return f"il y a {s // 60} min"
    if s < 86400: return f"il y a {s // 3600} h"
    if s < 172800: return "hier"
    if s < 604800: return f"il y a {s // 86400} j"
    return dt.strftime("%d/%m/%Y")


def greeting() -> str:
    h = datetime.now().hour
    if h < 12: return "Bonjour"
    if h < 18: return "Bon apres-midi"
    return "Bonsoir"


# Enregistre les helpers comme globales Jinja
templates.env.globals["icon"] = icon
templates.env.globals["table_icon"] = table_icon
templates.env.globals["relative_time"] = relative_time


def get_admin_models() -> dict:
    """Auto-decouvre tous les modeles SQLAlchemy enregistres dans Base."""
    return {m.class_.__tablename__: m.class_ for m in Base.registry.mappers}


def col_input_type(col) -> str:
    if col.foreign_keys:
        return "select"
    t = str(col.type).lower()
    if col.name == "password":
        return "password"
    if "bool" in t:
        return "checkbox"
    if "int" in t or "numeric" in t or "float" in t:
        return "number"
    if "datetime" in t:
        return "datetime-local"
    if "date" in t:
        return "date"
    if "email" in col.name.lower():
        return "email"
    return "text"


def fk_target_model(col, models: dict):
    """Renvoie la classe modele cible d'une colonne ForeignKey, ou None."""
    if not col.foreign_keys:
        return None
    fk = next(iter(col.foreign_keys))
    target_table = fk.column.table.name
    return models.get(target_table)


def fk_display_field(Model) -> str:
    """Choisit la meilleure colonne pour representer un objet dans un dropdown."""
    cols = {c.name for c in Model.__table__.columns}
    for candidate in FK_DISPLAY_CANDIDATES:
        if candidate in cols:
            return candidate
    return "id"


async def fk_options(db: AsyncSession, Model, limit: int = 500):
    """Charge jusqu'a `limit` enregistrements d'un modele pour un <select>."""
    rows = (await db.execute(select(Model).limit(limit))).scalars().all()
    display = fk_display_field(Model)
    return [(str(getattr(r, "id")), f"{getattr(r, display)} ({getattr(r, 'id')[:8]})") for r in rows]


def coerce_value(col, raw, form):
    """Convertit une valeur de formulaire vers le bon type Python."""
    t = str(col.type).lower()
    if "bool" in t:
        return col.name in form
    if raw is None or raw == "":
        return None
    if col.name == "password":
        return get_password_hash(raw)
    if "int" in t:
        return int(raw)
    if "float" in t or "numeric" in t:
        return float(raw)
    if "datetime" in t:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return raw
    return raw


async def get_admin_user(request: Request, db: AsyncSession) -> Optional[User]:
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        result = await db.execute(select(User).where(User.id == payload.get("sub")))
        user = result.scalar_one_or_none()
        if user and user.is_superuser and user.is_active:
            return user
    except Exception:
        return None
    return None


async def require_admin(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user = await get_admin_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )
    return user


async def build_fields(db: AsyncSession, Model, item=None) -> list:
    """Construit la liste des champs (avec options FK) pour le rendu de form.html."""
    models = get_admin_models()
    fields = []
    for c in Model.__table__.columns:
        input_type = col_input_type(c)
        val = getattr(item, c.name, "") if item is not None else ""
        if c.name == "password":
            val = ""
        if isinstance(val, datetime):
            val = val.strftime("%Y-%m-%dT%H:%M")

        field = {
            "name": c.name,
            "type": input_type,
            "required": (not c.nullable) and c.name != "password" and ("bool" not in str(c.type).lower()),
            "value": "" if val is None else val,
            "readonly": c.name in READONLY_FIELDS,
            "options": [],
        }
        if input_type == "select":
            target = fk_target_model(c, models)
            if target is not None:
                field["options"] = await fk_options(db, target)
            else:
                field["type"] = "text"  # fallback
        fields.append(field)
    return fields


# ── AUTH ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
async def login_submit(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password) or not user.is_superuser:
        logger.warning("Tentative admin echouee : %s", email)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Identifiants invalides ou compte non-administrateur."},
        )
    token = jwt.encode(
        {"sub": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        settings.SECRET_KEY, algorithm="HS256",
    )
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(ADMIN_COOKIE, token, httponly=True, max_age=8 * 3600, samesite="lax")
    logger.info("Connexion admin : %s", user.email)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE)
    return response


# ── DASHBOARD ────────────────────────────────────────────────────────────────

async def get_recent_activity(db: AsyncSession, models: dict, limit: int = 8) -> list:
    """Aggrege les N derniers enregistrements crees, toutes tables confondues."""
    items = []
    for name, Model in models.items():
        if "created_at" not in {c.name for c in Model.__table__.columns}:
            continue
        result = await db.execute(
            select(Model).order_by(Model.__table__.c.created_at.desc()).limit(limit)
        )
        display = fk_display_field(Model)
        for r in result.scalars().all():
            items.append({
                "table": name,
                "id": str(r.id),
                "label": str(getattr(r, display, r.id)),
                "created_at": r.created_at,
            })
    items.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)
    return items[:limit]


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    models = get_admin_models()
    stats = {}
    for name, Model in models.items():
        result = await db.execute(select(func.count()).select_from(Model))
        stats[name] = result.scalar() or 0
    activity = await get_recent_activity(db, models)
    total_records = sum(stats.values())
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "models": models,
        "stats": stats, "activity": activity, "table": None,
        "greeting": greeting(),
        "user_name": user.email.split("@")[0],
        "total_records": total_records,
        "model_count": len(models),
    })


# ── LIST ─────────────────────────────────────────────────────────────────────

async def resolve_fk_displays(db: AsyncSession, items: list, Model, models: dict) -> dict:
    """Pour chaque FK : charge les objets cibles et renvoie {col_name: {fk_id: display}}."""
    fk_maps = {}
    for col in Model.__table__.columns:
        if not col.foreign_keys:
            continue
        target = fk_target_model(col, models)
        if not target:
            continue
        ids = {getattr(i, col.name) for i in items if getattr(i, col.name, None)}
        if not ids:
            continue
        result = await db.execute(select(target).where(target.id.in_(list(ids))))
        display = fk_display_field(target)
        fk_maps[col.name] = {
            "table": target.__tablename__,
            "map": {str(r.id): str(getattr(r, display, r.id)) for r in result.scalars().all()},
        }
    return fk_maps


@router.get("/{table}", response_class=HTMLResponse)
async def list_view(
    table: str, request: Request, page: int = 1, q: str = "",
    db: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404, "Modele introuvable")
    Model = models[table]
    all_cols = list(Model.__table__.columns)
    display_cols = [c.name for c in all_cols if c.name not in HIDDEN_FIELDS][:6]

    stmt = select(Model)
    if q:
        # Recherche multi-colonnes : ILIKE sur toutes les colonnes textuelles
        # (sauf password). Genere un OR sur N colonnes.
        text_cols = [
            c for c in all_cols
            if c.name not in HIDDEN_FIELDS
            and any(t in str(c.type).lower() for t in ("varchar", "string", "text"))
        ]
        if text_cols:
            stmt = stmt.where(or_(*[c.ilike(f"%{q}%") for c in text_cols]))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    limit = 25
    items = (await db.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all()
    fk_maps = await resolve_fk_displays(db, items, Model, models)
    return templates.TemplateResponse(request, "list.html", {
        "user": user, "models": models,
        "table": table, "columns": display_cols, "items": items,
        "fk_maps": fk_maps,
        "total": total, "page": page,
        "pages": max(1, (total + limit - 1) // limit), "q": q,
    })


# ── CREATE ───────────────────────────────────────────────────────────────────

@router.get("/{table}/new", response_class=HTMLResponse)
async def new_view(
    table: str, request: Request,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404)
    Model = models[table]
    fields = await build_fields(db, Model, item=None)
    # Pour la creation, on retire id/created_at/updated_at
    fields = [f for f in fields if f["name"] not in READONLY_FIELDS]
    return templates.TemplateResponse(request, "form.html", {
        "user": user, "models": models,
        "table": table, "fields": fields,
        "action": f"/admin/{table}/new",
        "title": f"Nouveau {table[:-1] if table.endswith('s') else table}",
        "is_new": True,
    })


@router.post("/{table}/new")
async def create_item(
    table: str, request: Request,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404)
    Model = models[table]
    form = await request.form()
    data = {}
    for col in Model.__table__.columns:
        if col.name in READONLY_FIELDS:
            continue
        val = coerce_value(col, form.get(col.name), form)
        if val is not None:
            data[col.name] = val
    item = Model(**data)
    db.add(item)
    await db.commit()
    logger.info("Admin a cree %s : %s", table, getattr(item, "id", "?"))
    return RedirectResponse(url=f"/admin/{table}", status_code=303)


# ── BULK ACTIONS  + EXPORT (declares avant /{item_id} sinon route conflict) ──

@router.post("/{table}/bulk-delete")
async def bulk_delete(
    table: str, request: Request,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404)
    Model = models[table]
    form = await request.form()
    ids = form.getlist("ids")
    if not ids:
        return RedirectResponse(url=f"/admin/{table}", status_code=303)
    result = await db.execute(sql_delete(Model).where(Model.id.in_(ids)))
    await db.commit()
    logger.info("Admin a supprime %d %s en bulk", result.rowcount or 0, table)
    return RedirectResponse(url=f"/admin/{table}", status_code=303)


@router.get("/{table}/export.csv")
async def export_csv(
    table: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404)
    Model = models[table]
    cols = [c.name for c in Model.__table__.columns if c.name not in HIDDEN_FIELDS]

    rows = (await db.execute(select(Model))).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for row in rows:
        writer.writerow([
            ("" if getattr(row, c, "") is None else str(getattr(row, c, "")))
            for c in cols
        ])

    today = datetime.now().strftime("%Y-%m-%d")
    logger.info("Admin a exporte %d %s en CSV", len(rows), table)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}-{today}.csv"'},
    )


# ── DETAIL / UPDATE ──────────────────────────────────────────────────────────

@router.get("/{table}/{item_id}", response_class=HTMLResponse)
async def detail_view(
    table: str, item_id: str, request: Request,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404)
    Model = models[table]
    result = await db.execute(select(Model).where(Model.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Element introuvable")
    fields = await build_fields(db, Model, item=item)
    return templates.TemplateResponse(request, "form.html", {
        "user": user, "models": models,
        "table": table, "fields": fields,
        "action": f"/admin/{table}/{item_id}", "title": f"Editer {table}",
        "is_new": False, "item_id": item_id,
    })


@router.post("/{table}/{item_id}")
async def update_item(
    table: str, item_id: str, request: Request,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404)
    Model = models[table]
    result = await db.execute(select(Model).where(Model.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404)
    form = await request.form()
    for col in Model.__table__.columns:
        if col.name in READONLY_FIELDS:
            continue
        raw = form.get(col.name)
        if col.name == "password" and not raw:
            continue
        val = coerce_value(col, raw, form)
        setattr(item, col.name, val)
    await db.commit()
    logger.info("Admin a modifie %s : %s", table, item_id)
    return RedirectResponse(url=f"/admin/{table}", status_code=303)


# ── DELETE ───────────────────────────────────────────────────────────────────

@router.post("/{table}/{item_id}/delete")
async def delete_item(
    table: str, item_id: str,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    models = get_admin_models()
    if table not in models:
        raise HTTPException(404)
    Model = models[table]
    result = await db.execute(select(Model).where(Model.id == item_id))
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
        logger.info("Admin a supprime %s : %s", table, item_id)
    return RedirectResponse(url=f"/admin/{table}", status_code=303)
