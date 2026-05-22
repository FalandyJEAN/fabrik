import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from . import models, schemas
from src.core.security import get_password_hash

logger = logging.getLogger(__name__)


async def create_user(db: AsyncSession, user_in: schemas.UserCreate):
    new_user = models.User(
        email=user_in.email,
        password=get_password_hash(user_in.password),
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    logger.info("Nouvel utilisateur cree : %s", new_user.email)
    return new_user


async def get_user(db: AsyncSession, user_id: str):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user_id: str, update_data: schemas.UserUpdate):
    user = await get_user(db, user_id)
    if not user:
        return None
    if update_data.email is not None:
        user.email = update_data.email
    if update_data.password is not None:
        user.password = get_password_hash(update_data.password)
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
    await db.commit()
    await db.refresh(user)
    return user


async def deactivate_user(db: AsyncSession, user_id: str):
    user = await get_user(db, user_id)
    if not user:
        return None
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    logger.info("Utilisateur desactive : %s", user.id)
    return user
