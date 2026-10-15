
from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, Numeric,
    Boolean, DateTime, ForeignKey
)
from app.config.database import Base
from app.models.base import TimestampMixin


class Exam(TimestampMixin, Base):
    __tablename__ = "exams"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    course_id = Column(
        BigInteger, ForeignKey("courses.id"), nullable=False
    )
    created_by = Column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    total_marks = Column(Numeric(7, 2), nullable=False)
    passing_marks = Column(Numeric(7, 2), nullable=False)
    # Preferred way to set the pass bar: percentage of total_marks.
    # Kept separate because total_marks is unknown at exam-creation time.
    passing_percentage = Column(Numeric(5, 2), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    attempts_allowed = Column(Integer, nullable=True, default=1)
    shuffle_questions = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    @property
    def pass_cutoff(self):
        """Marks needed to pass. Percentage wins when set, else the
        legacy absolute passing_marks value is used."""
        if self.passing_percentage is not None:
            return (self.total_marks or 0) * self.passing_percentage / 100
        return self.passing_marks


class ExamQuestion(TimestampMixin, Base):
    __tablename__ = "exam_questions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exam_id = Column(
        BigInteger, ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False
    )
    question_id = Column(
        BigInteger, ForeignKey("questions.id"), nullable=False
    )
    marks = Column(Numeric(7, 2), nullable=False)
    sort_order = Column(Integer, default=0)


class ExamBatch(TimestampMixin, Base):
    __tablename__ = "exam_batches"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exam_id = Column(
        BigInteger, ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False
    )
    batch_id = Column(
        BigInteger, ForeignKey("batches.id"), nullable=False
    )
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)


class ExamGrader(TimestampMixin, Base):
    """Which teachers may grade a specific exam-batch assignment.

    Empty = every teacher of that batch may grade (default).
    """
    __tablename__ = "exam_graders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exam_batch_id = Column(
        BigInteger, ForeignKey("exam_batches.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
