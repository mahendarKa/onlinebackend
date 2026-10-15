from sqlalchemy import Column, BigInteger, Text, Integer, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionMatch(TimestampMixin, Base):
    __tablename__ = "question_match"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False
    )

    sub_question = Column(Text, nullable=False)
    sub_answer = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)