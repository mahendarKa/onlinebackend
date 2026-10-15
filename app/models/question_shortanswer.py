from sqlalchemy import Column, BigInteger, String, Boolean, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionShortAnswer(TimestampMixin, Base):
    __tablename__ = "question_shortanswer"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        unique=True,
        nullable=False
    )

    answer_text = Column(String(255), nullable=False)
    case_sensitive = Column(Boolean, default=False, nullable=False)