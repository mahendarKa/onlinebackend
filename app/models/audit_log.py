
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
)

from app.config.database import Base
from app.models.base import TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(BigInteger, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
