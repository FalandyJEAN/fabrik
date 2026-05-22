from sqlalchemy import Column, DateTime
from datetime import datetime, timezone


class TimestampMixin:
    """Ajoute created_at et updated_at a un modele SQLAlchemy."""
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
