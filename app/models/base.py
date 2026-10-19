from sqlalchemy import Column, DateTime

from app.utils.time import utcnow


class TimestampMixin:

    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False
    )