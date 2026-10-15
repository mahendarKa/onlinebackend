
from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, DateTime,
    Numeric, Boolean, ForeignKey, JSON
)
from app.config.database import Base
from app.models.base import TimestampMixin


class ExamAttempt(TimestampMixin, Base):
    __tablename__ = "exam_attempts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exam_id = Column(
        BigInteger,
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    attempt_no = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=True, default="in_progress")
    total_marks = Column(Numeric(7, 2), nullable=True, default=0)


class StudentAnswer(TimestampMixin, Base):
    __tablename__ = "student_answers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exam_attempt_id = Column(
        BigInteger,
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id = Column(
        BigInteger, ForeignKey("questions.id"), nullable=False
    )
    selected_option_id = Column(
        BigInteger, ForeignKey("question_options.id"), nullable=True
    )
    selected_option_ids = Column(JSON, nullable=True)
    match_answers = Column(JSON, nullable=True)
    answer_text = Column(Text, nullable=True)
    answer_file = Column(String(1000), nullable=True)
    code_text = Column(Text, nullable=True)
    marks_obtained = Column(Numeric(7, 2), nullable=True, default=0)
    is_correct = Column(Boolean, nullable=True)
    evaluated_by = Column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    evaluated_at = Column(DateTime, nullable=True)


class ExamResult(TimestampMixin, Base):
    __tablename__ = "exam_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exam_attempt_id = Column(
        BigInteger,
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    total_questions = Column(Integer, nullable=False)
    attempted = Column(Integer, nullable=False)
    correct = Column(Integer, nullable=False)
    wrong = Column(Integer, nullable=False)
    skipped = Column(Integer, nullable=False)
    total_marks = Column(Numeric(7, 2), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)
    pass_fail = Column(String(10), nullable=False)
