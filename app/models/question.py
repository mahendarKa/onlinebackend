from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Numeric,
    Boolean,
    ForeignKey
)

from app.config.database import Base
from app.models.base import TimestampMixin


class Question(TimestampMixin, Base):

    __tablename__ = "questions"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True
    )

    category_id = Column(
        BigInteger,
        ForeignKey("question_categories.id"),
        nullable=False
    )

    type = Column(
        String(50),
        nullable=False,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    question_text = Column(
        Text,
        nullable=False
    )

    default_mark = Column(
        Numeric(5, 2),
        nullable=False
    )

    general_feedback = Column(
        Text,
        nullable=True
    )

    created_by = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )