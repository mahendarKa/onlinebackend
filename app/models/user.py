from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, func
from sqlalchemy.ext.hybrid import hybrid_property
from app.config.database import Base
from app.models.base import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Display name — computed as "first last"; no column is stored.
    # As a hybrid_property it also works in queries, e.g.
    # db.query(User.id, User.name).
    @hybrid_property
    def name(self):
        return " ".join(
            p for p in (self.first_name, self.last_name) if p
        )

    @name.expression
    def name(cls):
        return func.concat_ws(" ", cls.first_name, cls.last_name)

    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)

    role = Column(String(20), nullable=False)

    mobile_number = Column(String(20), nullable=True)
    profile_pic = Column(String(500), nullable=True)

    is_active = Column(Boolean, default=True)