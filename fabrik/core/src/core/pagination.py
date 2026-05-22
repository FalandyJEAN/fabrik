from pydantic import BaseModel
from typing import TypeVar, Generic
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int

    class Config:
        from_attributes = True


async def paginate(db: AsyncSession, stmt, page: int, limit: int) -> dict:
    """Paginer un Select SQLAlchemy async. Retourne un dict compatible Page[T]."""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    items_stmt = stmt.offset((page - 1) * limit).limit(limit)
    items = (await db.execute(items_stmt)).scalars().all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, (total + limit - 1) // limit),
    }
