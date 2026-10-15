from sqlalchemy import Column, BigInteger, String, Integer, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionEssay(TimestampMixin, Base):
    __tablename__ = "question_essay"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        unique=True,
        nullable=False
    )

    response_format = Column(
        String(50),
        nullable=False,
        default="plain"
    )

    max_words = Column(
        Integer,
        nullable=True
    )