from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.batch import Batch
from app.models.batch_student import BatchStudent
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt, ExamResult
from app.models.question import Question
from app.models.user import User
from app.utils.dependencies import require_role
from app.utils.permissions import (
    teacher_exam_ids,
    teacher_visible_batch_ids,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

admin_only = Depends(require_role("admin", "superadmin"))
teacher_only = Depends(require_role("teacher"))


def _status_counts(rows):
    out = {"in_progress": 0, "submitted": 0, "evaluated": 0}
    for status, count in rows:
        if status in out:
            out[status] = count
    return out


# --------------------------------------------------
# ADMIN: PORTAL-WIDE OVERVIEW
# --------------------------------------------------

@router.get("/admin")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = admin_only,
):
    users_by_role = {
        role: count
        for role, count in db.query(
            User.role, func.count()
        ).group_by(User.role).all()
    }

    attempts = _status_counts(
        db.query(ExamAttempt.status, func.count())
        .group_by(ExamAttempt.status)
        .all()
    )

    passed = db.query(ExamResult).filter(
        ExamResult.pass_fail == "PASS"
    ).count()
    failed = db.query(ExamResult).filter(
        ExamResult.pass_fail == "FAIL"
    ).count()

    # Attempts started per day over the last 7 days.
    today = utcnow().date()
    start = today - timedelta(days=6)
    rows = db.query(
        func.date(ExamAttempt.start_time), func.count()
    ).filter(
        ExamAttempt.start_time >= start
    ).group_by(func.date(ExamAttempt.start_time)).all()
    by_day = {str(day): count for day, count in rows}
    attempts_last_7d = [
        {
            "date": str(start + timedelta(days=i)),
            "count": by_day.get(str(start + timedelta(days=i)), 0),
        }
        for i in range(7)
    ]

    active = db.query(Exam).filter(Exam.is_active == True).count()  # noqa: E712

    return {
        "totals": {
            "users": db.query(User).count(),
            "batches": db.query(Batch).count(),
            "questions": db.query(Question).count(),
            "exams": db.query(Exam).count(),
        },
        "users_by_role": users_by_role,
        "exams": {"active": active, "inactive": db.query(Exam).count() - active},
        "attempts": attempts,
        "results": {"passed": passed, "failed": failed},
        "attempts_last_7d": attempts_last_7d,
    }


# --------------------------------------------------
# TEACHER: MY BATCHES / STUDENTS OVERVIEW
# --------------------------------------------------

@router.get("/teacher")
def teacher_dashboard(
    db: Session = Depends(get_db),
    current_user: User = teacher_only,
):
    batch_ids = teacher_visible_batch_ids(db, current_user.id)
    exam_ids = teacher_exam_ids(db, current_user.id)

    total_students = (
        db.query(func.count(func.distinct(BatchStudent.user_id))).filter(
            BatchStudent.batch_id.in_(batch_ids or {0}),
            BatchStudent.is_active == True,  # noqa: E712
        ).scalar()
    ) or 0

    attempts = _status_counts(
        db.query(ExamAttempt.status, func.count()).filter(
            ExamAttempt.exam_id.in_(exam_ids or {0})
        ).group_by(ExamAttempt.status).all()
    )

    students_attempted = (
        db.query(func.count(func.distinct(ExamAttempt.user_id))).filter(
            ExamAttempt.exam_id.in_(exam_ids or {0})
        ).scalar()
    ) or 0

    # Scored results, best first — only attempts on this teacher's exams.
    results = (
        db.query(ExamResult, ExamAttempt, Exam)
        .join(ExamAttempt, ExamResult.exam_attempt_id == ExamAttempt.id)
        .join(Exam, ExamAttempt.exam_id == Exam.id)
        .filter(ExamAttempt.exam_id.in_(exam_ids or {0}))
        .order_by(ExamResult.percentage.desc())
        .all()
    )

    def scorer(entry):
        result, attempt, exam = entry
        student = db.query(User).filter(User.id == attempt.user_id).first()
        return {
            "student_name": student.name if student else None,
            "exam_name": exam.name,
            "marks": float(result.total_marks),
            "percentage": float(result.percentage),
            "pass_fail": result.pass_fail,
        }

    passed = sum(1 for r, _, _ in results if r.pass_fail == "PASS")
    failed = len(results) - passed

    ranges = [("0-39%", 0, 40), ("40-59%", 40, 60),
              ("60-79%", 60, 80), ("80-100%", 80, 100.01)]
    distribution = [
        {
            "range": label,
            "students": sum(
                1 for r, _, _ in results
                if lo <= float(r.percentage) < hi
            ),
        }
        for label, lo, hi in ranges
    ]

    return {
        "totals": {
            "batches": len(batch_ids),
            "students": total_students,
            "exams": len(exam_ids),
            "students_attempted": students_attempted,
        },
        "attempts": attempts,
        "results": {"passed": passed, "failed": failed},
        "score_distribution": distribution,
        # Up to 10 best and 10 worst (ascending) scorers.
        "top_scorers": [scorer(entry) for entry in results[:10]],
        "lowest_scorers": (
            [scorer(entry) for entry in reversed(results[-10:])]
            if len(results) > 1 else []
        ),
    }
