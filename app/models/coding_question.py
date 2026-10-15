
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Integer,
    Boolean,
    Numeric,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.config.database import Base
from app.models.base import TimestampMixin


class CodingQuestion(TimestampMixin, Base):
    __tablename__ = "coding_questions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    question_id = Column(
        BigInteger,
        ForeignKey("questions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    language = Column(String(50), nullable=False)
    starter_code = Column(Text, nullable=True)
    time_limit = Column(Integer, nullable=False, default=2)
    memory_limit = Column(Integer, nullable=False, default=256)
    execution_limit = Column(Integer, nullable=False, default=10)
    compiler_version = Column(String(100), nullable=True)

    test_cases = relationship(
        "CodingTestCase",
        back_populates="coding_question",
        cascade="all, delete-orphan",
    )


class CodingTestCase(TimestampMixin, Base):
    __tablename__ = "coding_test_cases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    coding_question_id = Column(
        BigInteger,
        ForeignKey("coding_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_text = Column(Text, nullable=True)
    expected_output = Column(Text, nullable=False)
    is_hidden = Column(Boolean, nullable=False, default=False)
    marks = Column(Numeric(5, 2), nullable=False, default=1)
    sort_order = Column(Integer, nullable=False, default=0)

    coding_question = relationship(
        "CodingQuestion",
        back_populates="test_cases",
    )
