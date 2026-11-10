
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.exam import Exam, ExamQuestion
from app.models.exam_attempt import ExamAttempt, StudentAnswer, ExamResult
from app.models.question import Question
from app.services.activity_service import log_audit
from app.services.evaluation_service import (
    answer_has_content,
    auto_grade_answer,
)
from app.utils.time import utcnow


def attempt_deadline(attempt: ExamAttempt, exam: Exam):
    """Latest instant the attempt stays writable: start + duration,
    capped by the exam's availability end."""
    deadline = attempt.start_time + timedelta(minutes=exam.duration_minutes)
    if exam.end_time:
        deadline = min(deadline, exam.end_time)
    return deadline


def finalize_attempt(db: Session, attempt: ExamAttempt, exam: Exam) -> dict:
    """Close an attempt: stamp end_time, mark it submitted, auto-grade
    saved answers and persist the ExamResult.

    Shared by the submit endpoint and by lazy expiry — a stale
    in_progress attempt whose deadline already passed gets graded the
    same way as if the student had pressed Submit.
    """
    now = utcnow()
    deadline = attempt_deadline(attempt, exam)

    # Submission is accepted even after time expires; only saved answers count.
    attempt.end_time = min(now, deadline)
    attempt.status = "submitted"

    exam_items = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id
    ).all()

    question_types = {
        q.id: q.type for q in db.query(Question).filter(
            Question.id.in_([i.question_id for i in exam_items])
        ).all()
    }

    # Description/paragraph items are informational text, not questions.
    exam_items = [
        i for i in exam_items
        if question_types.get(i.question_id) not in ("description", "paragraph")
    ]

    answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_attempt_id == attempt.id
    ).all()
    answers_by_question = {a.question_id: a for a in answers}

    total_questions = len(exam_items)
    attempted = 0
    correct = 0
    wrong = 0
    scored_marks = Decimal("0.00")
    pending_manual = False

    for item in exam_items:
        answer = answers_by_question.get(item.question_id)
        if not answer:
            continue

        if not answer_has_content(answer):
            continue

        attempted += 1
        question = db.query(Question).filter(
            Question.id == item.question_id
        ).first()

        if not question:
            continue

        graded = auto_grade_answer(
            db, question, answer, Decimal(str(item.marks))
        )

        if graded is None:
            # Type requires manual evaluation by teacher/admin.
            answer.is_correct = None
            answer.marks_obtained = None
            pending_manual = True
            continue

        is_correct, marks = graded
        answer.is_correct = is_correct
        answer.marks_obtained = marks
        scored_marks += marks

        if is_correct:
            correct += 1
        else:
            wrong += 1

    skipped = total_questions - attempted
    attempt.total_marks = scored_marks

    percentage = (
        (scored_marks / Decimal(str(exam.total_marks))) * Decimal("100")
        if exam.total_marks else Decimal("0.00")
    )

    pass_fail = "PENDING" if pending_manual else (
        "PASS" if scored_marks >= exam.pass_cutoff else "FAIL"
    )

    # exam_attempt_id is unique on exam_results — a lazily-expired
    # attempt must never try to write a second row.
    existing_result = db.query(ExamResult).filter(
        ExamResult.exam_attempt_id == attempt.id
    ).first()
    if not existing_result:
        db.add(ExamResult(
            exam_attempt_id=attempt.id,
            total_questions=total_questions,
            attempted=attempted,
            correct=correct,
            wrong=wrong,
            skipped=skipped,
            total_marks=scored_marks,
            percentage=percentage,
            pass_fail=pass_fail,
        ))

    log_audit(
        db, attempt.user_id, "exam.submit", "exam_attempt", attempt.id,
        details=f"exam {exam.id} '{exam.name}': "
                f"{attempted}/{total_questions} attempted, "
                f"{scored_marks} marks",
    )
    db.commit()

    return {
        "attempted": attempted,
        "total_questions": total_questions,
    }


def expire_if_due(db: Session, attempt: ExamAttempt, exam: Exam) -> bool:
    """Auto-submit an in_progress attempt whose deadline already passed.
    Returns True when the attempt was finalized."""
    if attempt.status != "in_progress":
        return False
    if utcnow() < attempt_deadline(attempt, exam):
        return False
    finalize_attempt(db, attempt, exam)
    return True
