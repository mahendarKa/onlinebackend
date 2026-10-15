from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    func,
)

from app.config.database import Base
from app.models.base import TimestampMixin


class ExamFeedback(TimestampMixin, Base):
    __tablename__ = "exam_feedback"

    id = Column(BigInteger, primary_key=True, index=True)
    exam_id = Column(
        BigInteger,
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_id = Column(
        BigInteger,
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    student_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating = Column(Integer, nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )