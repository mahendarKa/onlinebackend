from sqlalchemy import Column, BigInteger, Text, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionDescription(TimestampMixin, Base):
    __tablename__ = "question_description"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        unique=True,
        nullable=False
    )

    content = Column(Text, nullable=False)