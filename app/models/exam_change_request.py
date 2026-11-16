from sqlalchemy import (
    Column,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    JSON,
)

from app.config.database import Base
from app.models.base import TimestampMixin


class ExamChangeRequest(TimestampMixin, Base):
    """A teacher-proposed exam delete or grader change, awaiting
    admin approval. Applied only after an admin approves it."""

    __tablename__ = "exam_change_requests"

    id = Column(BigInteger, primary_key=True, index=True)

    exam_id = Column(
        BigInteger,
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action = Column(
        String(20),  # delete | graders
        nullable=False,
    )

    # For "graders": {"assignment_id": n, "grader_ids": [...],
    # "exam_name": str}. For "delete": {"exam_name": str}.
    payload = Column(JSON, nullable=True)

    status = Column(
        String(20),  # pending | approved | rejected
        nullable=False,
        default="pending",
        index=True,
    )

    requested_by = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )

    reviewed_by = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )

    reviewed_at = Column(DateTime, nullable=True)

    review_note = Column(String(500), nullable=True)
