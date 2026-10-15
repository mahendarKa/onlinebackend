
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    func,
)
from app.config.database import Base
from app.models.base import TimestampMixin


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(
        String(50), nullable=False, default="general"
    )
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime, nullable=False, server_default=func.now()
    )
