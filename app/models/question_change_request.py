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
from app.utils.time import utcnow


class QuestionChangeRequest(TimestampMixin, Base):
    """A proposed edit/delete of a question, awaiting admin approval.

    While a request for a question is ``pending`` the question is frozen:
    it cannot be edited again and every un-attempted exam that contains
    it cannot be attempted until an admin approves or rejects.
    """

    __tablename__ = "question_change_requests"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False,
        index=True,
    )

    action = Column(
        String(20),  # update | delete
        nullable=False,
    )

    # For "update": the full desired state
    # {"base": {...}, "options": [...], "truefalse": {...}, ...,
    #  "full_state": true}.
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
