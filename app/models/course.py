from datetime import datetime
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey
)

from app.config.database import Base
from app.models.base import TimestampMixin


class Course(TimestampMixin, Base):

    __tablename__ = "courses"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    code = Column(
        String(100),
        unique=True,
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    created_by = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False
    )