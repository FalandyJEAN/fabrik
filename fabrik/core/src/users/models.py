from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from src.database import Base
from src.core.mixins import TimestampMixin
import uuid


def generate_id():
    return str(uuid.uuid4())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id           = Column(String, primary_key=True, default=generate_id)
    email        = Column(String, nullable=False, unique=True, index=True)
    password     = Column(String, nullable=False)
    is_active    = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Ajoute tes relations ici :
    # articles = relationship("Article", back_populates="author")
