from sqlalchemy import Column, BigInteger, String, Integer, ForeignKey
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionImage(TimestampMixin, Base):
    __tablename__ = "question_images"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False
    )

    image_url = Column(String(1000), nullable=False)
    alt_text = Column(String(255), nullable=True)
    position = Column(Integer, default=0, nullable=False)