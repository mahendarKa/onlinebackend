from sqlalchemy import (
    Column, BigInteger, String, Text, ForeignKey
)
from app.config.database import Base
from app.models.base import TimestampMixin


class ProctorEvent(TimestampMixin, Base):
    """One proctoring violation/observation during an exam attempt.

    ``event_type`` is a short machine key (tab_hidden, no_face, ...);
    ``snapshot_url`` links to the uploaded webcam frame when the event
    carries photo evidence.
    """
    __tablename__ = "proctor_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id = Column(
        BigInteger,
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type = Column(String(50), nullable=False)
    detail = Column(Text, nullable=True)
    snapshot_url = Column(String(500), nullable=True)
