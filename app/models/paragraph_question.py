from sqlalchemy import Column, BigInteger, Integer, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class ParagraphQuestion(TimestampMixin, Base):
    __tablename__ = "paragraph_questions"

    id = Column(BigInteger, primary_key=True, index=True)

    passage_id = Column(
        BigInteger,
        ForeignKey("paragraph_passages.id"),
        nullable=False
    )

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False
    )

    sort_order = Column(Integer, default=0, nullable=False)