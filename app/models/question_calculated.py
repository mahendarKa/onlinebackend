from sqlalchemy import Column, BigInteger, Text, Numeric, String, ForeignKey, JSON
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionCalculated(TimestampMixin, Base):
    __tablename__ = "question_calculated"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        unique=True,
        nullable=False
    )

    formula = Column(Text, nullable=False)
    tolerance = Column(Numeric(10, 4), nullable=False, default=0)
    units = Column(String(50), nullable=True)

    # Wildcard datasets for {name} placeholders, e.g.
    # [{"name": "a", "min": 1, "max": 10, "decimals": 0}]
    datasets = Column(JSON, nullable=True)