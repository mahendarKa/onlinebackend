from sqlalchemy import Column, BigInteger, ForeignKey, JSON
from app.config.database import Base
from app.models.base import TimestampMixin


class QuestionParagraph(TimestampMixin, Base):
    """Links a paragraph (passage) question to its child questions.

    child_question_ids: list of question ids whose exam view should show
    this paragraph's passage above the question, e.g. [12, 15].
    """
    __tablename__ = "question_paragraph"

    id = Column(BigInteger, primary_key=True, index=True)

    question_id = Column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    child_question_ids = Column(JSON, nullable=True)
