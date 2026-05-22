import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from . import schemas, service
from src.database import get_db
from src.core.security import (
    verify_password, create_access_token, create_refresh_token,
    decode_refresh_token, get_current_user
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.post("/", response_model=schemas.UserResponse, status_code=201)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    if await service.get_user_by_email(db, user.email):
        raise HTTPException(status_code=409, detail="Cet email est deja utilise")
    return await service.create_user(db, user)


@router.post("/login", response_model=schemas.Token)
async def login(credentials: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_email(db, credentials.email)
    if not user or not verify_password(credentials.password, user.password):
        logger.warning("Tentative de connexion echouee pour : %s", credentials.email)
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    logger.info("Connexion reussie : %s", user.email)
    return {
        "access_token": create_access_token({"sub": user.id}),
        "refresh_token": create_refresh_token({"sub": user.id}),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=schemas.Token)
async def refresh(body: schemas.RefreshRequest, db: AsyncSession = Depends(get_db)):
    user_id = decode_refresh_token(body.refresh_token)
    user = await service.get_user(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")
    return {
        "access_token": create_access_token({"sub": user.id}),
        "refresh_token": create_refresh_token({"sub": user.id}),
        "token_type": "bearer",
    }


@router.get("/me", response_model=schemas.UserResponse)
async def get_me(db: AsyncSession = Depends(get_db), current_user_id: str = Depends(get_current_user)):
    user = await service.get_user(db, current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return user


@router.put("/me", response_model=schemas.UserResponse)
async def update_me(
    user_update: schemas.UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    return await service.update_user(db, current_user_id, user_update)


@router.delete("/me", response_model=schemas.UserResponse)
async def deactivate_me(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    user = await service.deactivate_user(db, current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return user
