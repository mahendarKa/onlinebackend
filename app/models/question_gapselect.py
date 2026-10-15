from sqlalchemy import (
    Column, BigInteger, Text, Integer, Boolean, ForeignKey
)
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionGapSelect(TimestampMixin, Base):
    """One answer option inside a blank of a select-missing-word question.

    The question text carries [[n]] placeholders; rows with the same
    blank_no form that blank's dropdown. Exactly one row per blank
    must be marked is_correct.
    """

    __tablename__ = "question_gapselect"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False
    )

    blank_no = Column(Integer, nullable=False)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
