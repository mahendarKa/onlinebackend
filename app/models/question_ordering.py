from sqlalchemy import Column, BigInteger, Text, Integer, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionOrdering(TimestampMixin, Base):
    """One draggable item of an ordering question.

    position is the item's index in the CORRECT sequence (1-based).
    Students see the items shuffled and must restore this order.
    """

    __tablename__ = "question_ordering"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False
    )

    item_text = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
