
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt, ExamResult
from app.models.user import User
from app.utils.dependencies import require_role
from app.utils.permissions import require_exam_view

router = APIRouter(
    prefix="/api/exam-analytics",
    tags=["Exam Analytics"],
)

teacher_admin = Depends(require_role("admin", "teacher"))


# --------------------------------------------------
# EXAM PERFORMANCE SUMMARY
# --------------------------------------------------

@router.get("/exams/{exam_id}/summary")
def exam_summary(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    require_exam_view(current_user, exam, db)

    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam_id
    ).all()

    results = (
        db.query(ExamResult)
        .join(
            ExamAttempt,
            ExamResult.exam_attempt_id == ExamAttempt.id,
        )
        .filter(ExamAttempt.exam_id == exam_id)
        .all()
    )

    total_attempts = len(attempts)
    in_progress = sum(1 for a in attempts if a.status == "in_progress")
    submitted = sum(1 for a in attempts if a.status == "submitted")
    evaluated = sum(1 for a in attempts if a.status == "evaluated")

    pass_count = sum(1 for r in results if r.pass_fail == "PASS")
    fail_count = sum(1 for r in results if r.pass_fail == "FAIL")

    average_marks = (
        sum((Decimal(str(r.total_marks)) for r in results), Decimal("0"))
        / len(results)
        if results else Decimal("0")
    )

    average_percentage = (
        sum((Decimal(str(r.percentage)) for r in results), Decimal("0"))
        / len(results)
        if results else Decimal("0")
    )

    return {
        "exam_id": exam.id,
        "exam_name": exam.name,
        "maximum_marks": exam.total_marks,
        "total_attempts": total_attempts,
        "in_progress": in_progress,
        "submitted": submitted,
        "evaluated": evaluated,
        "results_available": len(results),
        "passed": pass_count,
        "failed": fail_count,
        "pass_percentage": round(
            pass_count / len(results) * 100, 2
        ) if results else 0,
        "average_marks": round(float(average_marks), 2),
        "average_percentage": round(float(average_percentage), 2),
    }


# --------------------------------------------------
# STUDENT PERFORMANCE FOR AN EXAM
# --------------------------------------------------

@router.get("/exams/{exam_id}/students")
def exam_student_performance(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    require_exam_view(current_user, exam, db)

    attempts = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.exam_id == exam_id)
        .order_by(ExamAttempt.user_id, ExamAttempt.attempt_no)
        .all()
    )

    output = []

    for attempt in attempts:
        student = db.query(User).filter(
            User.id == attempt.user_id
        ).first()

        result = db.query(ExamResult).filter(
            ExamResult.exam_attempt_id == attempt.id
        ).first()

        output.append({
            "attempt_id": attempt.id,
            "student_id": attempt.user_id,
            "student_name": student.name if student else None,
            "attempt_no": attempt.attempt_no,
            "status": attempt.status,
            "marks": result.total_marks if result else None,
            "percentage": result.percentage if result else None,
            "pass_fail": result.pass_fail if result else None,
        })

    return output


# --------------------------------------------------
# EXAM SCORE DISTRIBUTION
# --------------------------------------------------

@router.get("/exams/{exam_id}/score-distribution")
def score_distribution(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    require_exam_view(current_user, exam, db)

    results = (
        db.query(ExamResult)
        .join(
            ExamAttempt,
            ExamResult.exam_attempt_id == ExamAttempt.id,
        )
        .filter(ExamAttempt.exam_id == exam_id)
        .all()
    )

    maximum_marks = Decimal(str(exam.total_marks))

    ranges = [
        ("0-39%", Decimal("0"), Decimal("40")),
        ("40-59%", Decimal("40"), Decimal("60")),
        ("60-79%", Decimal("60"), Decimal("80")),
        ("80-100%", Decimal("80"), Decimal("100.01")),
    ]

    distribution = []

    for label, lower, upper in ranges:
        count = sum(
            1 for result in results
            if lower <= Decimal(str(result.percentage)) < upper
        )

        distribution.append({
            "range": label,
            "students": count,
        })

    return {
        "exam_id": exam.id,
        "exam_name": exam.name,
        "maximum_marks": maximum_marks,
        "total_results": len(results),
        "distribution": distribution,
    }
