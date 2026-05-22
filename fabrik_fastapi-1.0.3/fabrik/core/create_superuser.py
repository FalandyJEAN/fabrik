"""
Cree un super-utilisateur (admin) pour acceder a /admin

Usage : python create_superuser.py
"""
import asyncio
from getpass import getpass
from sqlalchemy import select
from src.database import AsyncSessionLocal, engine, Base
from src.users.models import User
from src.core.security import get_password_hash


async def main():
    # S'assurer que les tables existent
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n=== Creation d'un super-utilisateur ===\n")
    email = input("Email : ").strip()
    password = getpass("Mot de passe : ")
    confirm  = getpass("Confirmer       : ")

    if password != confirm:
        print("[!] Les mots de passe ne correspondent pas.")
        return
    if len(password) < 6:
        print("[!] Mot de passe trop court (min 6 caracteres).")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            existing.password = get_password_hash(password)
            existing.is_superuser = True
            existing.is_active = True
            await db.commit()
            print(f"\n  [OK] {email} promu super-utilisateur.")
        else:
            user = User(
                email=email,
                password=get_password_hash(password),
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            await db.commit()
            print(f"\n  [OK] Super-utilisateur cree : {email}")
        print("  Connectez-vous sur http://127.0.0.1:8000/admin/login\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
