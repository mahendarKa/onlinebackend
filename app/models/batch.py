from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Date,
    ForeignKey
)

from app.config.database import Base
from app.models.base import TimestampMixin


class Batch(TimestampMixin, Base):

    __tablename__ = "batches"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    course_id = Column(
        BigInteger,
        ForeignKey("courses.id"),
        nullable=False
    )

    name = Column(
        String(255),
        nullable=False
    )

    start_date = Column(
        Date,
        nullable=True
    )

    end_date = Column(
        Date,
        nullable=True
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