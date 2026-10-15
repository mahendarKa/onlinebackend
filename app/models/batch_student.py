from datetime import datetime

from sqlalchemy import (
    Column,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey
)

from app.config.database import Base
from app.models.base import TimestampMixin


class BatchStudent(TimestampMixin, Base):

    __tablename__ = "batch_students"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    batch_id = Column(
        BigInteger,
        ForeignKey("batches.id"),
        nullable=False
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False
    )

    enrolled_at = Column(
        DateTime,
        default=datetime.now,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )