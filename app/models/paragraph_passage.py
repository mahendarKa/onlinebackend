from sqlalchemy import Column, BigInteger, Text, ForeignKey, DateTime

from app.config.database import Base
from app.models.base import TimestampMixin
from app.utils.time import utcnow


class ParagraphPassage(TimestampMixin, Base):
    __tablename__ = "paragraph_passages"

    id = Column(BigInteger, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    created_by = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False
    )
    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False
    )