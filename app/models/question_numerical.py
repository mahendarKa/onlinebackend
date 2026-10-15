from sqlalchemy import Column, BigInteger, Numeric, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionNumerical(TimestampMixin, Base):
    __tablename__ = "question_numerical"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        unique=True,
        nullable=False
    )

    answer_value = Column(Numeric(10, 4), nullable=False)
    tolerance = Column(Numeric(10, 4), nullable=False, default=0)