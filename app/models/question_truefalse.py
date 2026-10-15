from sqlalchemy import Column, BigInteger, Boolean, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionTrueFalse(TimestampMixin, Base):
    __tablename__ = "question_truefalse"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        unique=True,
        nullable=False
    )

    true_answer = Column(Boolean, nullable=False, default=False)
    false_answer = Column(Boolean, nullable=False, default=False)