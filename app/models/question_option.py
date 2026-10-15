from sqlalchemy import Column, BigInteger, Text, Boolean, Numeric, Integer, String, ForeignKey

from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionOption(TimestampMixin, Base):
    __tablename__ = "question_options"

    id = Column(BigInteger, primary_key=True, index=True)
    question_id = Column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False
    )
    option_text = Column(Text, nullable=False)
    # Optional image for image-based options (type="image" questions).
    image_url = Column(String(1000), nullable=True)
    is_correct = Column(Boolean, default=False, nullable=False)
    fraction = Column(Numeric(5, 2), default=0, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)