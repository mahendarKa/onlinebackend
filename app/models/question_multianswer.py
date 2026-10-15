from sqlalchemy import Column, BigInteger, Text, String, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionMultiAnswer(TimestampMixin, Base):
    __tablename__ = "question_multianswer"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        unique=True,
        nullable=False
    )

    answer_text = Column(Text, nullable=False)
    answer_format = Column(String(50), nullable=False, default="text")