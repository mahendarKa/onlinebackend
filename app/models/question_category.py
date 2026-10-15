from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    ForeignKey
)

from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionCategory(TimestampMixin, Base):

    __tablename__ = "question_categories"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    parent_id = Column(
        BigInteger,
        ForeignKey("question_categories.id"),
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