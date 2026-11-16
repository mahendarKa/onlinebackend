
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.course import Course
from app.models.exam import Exam, ExamBatch
from app.models.batch_student import BatchStudent
from app.models.exam_attempt import ExamAttempt, ExamResult
from app.services.activity_service import notify_expired_exams
from app.services.attempt_service import expire_if_due
from app.services.question_change import exams_with_pending_questions
from app.utils.dependencies import require_role
from app.utils.time import utcnow

router = APIRouter(
    prefix="/api/student/dashboard",
    tags=["Student Dashboard"],
)

student_only = Depends(require_role("student"))


@router.get("/exams")
def get_student_exams(
    db: Session = Depends(get_db),
    current_user=student_only,
):
    now = utcnow()

    # Lazy pass: emit expiry notifications for exams whose end
    # time has passed since the last request.
    notify_expired_exams(db)

    # Find batches to which the current student belongs.
    student_batch_ids = [
        row.batch_id
        for row in db.query(BatchStudent.batch_id).filter(
            BatchStudent.user_id == current_user.id
        ).all()
    ]

    if not student_batch_ids:
        return []

    # Find exams assigned to those batches.
    assignments = db.query(ExamBatch).filter(
        ExamBatch.batch_id.in_(student_batch_ids)
    ).all()

    exam_ids = list({assignment.exam_id for assignment in assignments})

    if not exam_ids:
        return []

    exams = db.query(Exam).filter(
        Exam.id.in_(exam_ids),
        Exam.is_active == True,
    ).order_by(Exam.id.desc()).all()

    # Exams containing a question with a pending approval request are
    # blocked for students until an admin resolves it.
    pending_approval_ids = exams_with_pending_questions(db, exam_ids)

    output = []

    for exam in exams:
        exam_assignments = [
            a for a in assignments if a.exam_id == exam.id
        ]

        # Use the schedule assigned to this student's batch.
        applicable = [
            a for a in exam_assignments
            if a.batch_id in student_batch_ids
        ]

        batch_start_times = [
            a.start_time for a in applicable if a.start_time is not None
        ]
        batch_end_times = [
            a.end_time for a in applicable if a.end_time is not None
        ]

        start_time = max(
            [exam.start_time] if exam.start_time else []
            + batch_start_times
        ) if (exam.start_time or batch_start_times) else None

        end_time = min(
            [exam.end_time] if exam.end_time else []
            + batch_end_times
        ) if (exam.end_time or batch_end_times) else None

        attempts = db.query(ExamAttempt).filter(
            ExamAttempt.exam_id == exam.id,
            ExamAttempt.user_id == current_user.id,
        ).order_by(ExamAttempt.attempt_no.desc()).all()

        # Lazily auto-submit attempts whose deadline already passed so a
        # stale in_progress row can't keep the exam looking resumable
        # after the window closed — status then falls through to ended.
        for attempt in attempts:
            expire_if_due(db, attempt, exam)

        completed_attempts = [
            a for a in attempts
            if a.status in ("submitted", "evaluated")
        ]

        in_progress = next(
            (a for a in attempts if a.status == "in_progress"),
            None,
        )

        attempts_allowed = exam.attempts_allowed
        attempts_used = len(attempts)

        if in_progress:
            status = "in_progress"
        elif exam.id in pending_approval_ids:
            status = "pending_approval"
        elif start_time and now < start_time:
            status = "upcoming"
        elif end_time and now >= end_time:
            status = "ended"
        elif (
            attempts_allowed is not None
            and attempts_used >= attempts_allowed
        ):
            status = "attempt_limit_reached"
        else:
            status = "available"

        output.append({
            "exam_id": exam.id,
            "name": exam.name,
            "description": exam.description,
            "duration_minutes": exam.duration_minutes,
            "total_marks": exam.total_marks,
            "passing_marks": exam.passing_marks,
            "passing_percentage": exam.passing_percentage,
            "start_time": start_time,
            "end_time": end_time,
            "attempts_allowed": attempts_allowed,
            "attempts_used": attempts_used,
            "is_proctored": bool(exam.is_proctored),
            "max_violations": exam.max_violations,
            "completed_attempts": len(completed_attempts),
            "status": status,
        })

    return output


@router.get("/summary")
def student_dashboard_summary(
    db: Session = Depends(get_db),
    current_user=student_only,
):
    """Aggregates for the student's dashboard charts.

    Results come from ExamResult joined through the attempt so each row
    carries its exam + course for grouping. 'PENDING' results (awaiting
    manual grading) are reported but excluded from averages.
    """
    rows = (
        db.query(ExamResult, ExamAttempt, Exam)
        .join(ExamAttempt, ExamResult.exam_attempt_id == ExamAttempt.id)
        .join(Exam, ExamAttempt.exam_id == Exam.id)
        .filter(ExamAttempt.user_id == current_user.id)
        .order_by(ExamAttempt.start_time.asc())
        .all()
    )

    total_attempts = db.query(ExamAttempt).filter(
        ExamAttempt.user_id == current_user.id
    ).count()

    evaluated = [r for r, _, _ in rows if r.pass_fail in ("PASS", "FAIL")]
    pending = sum(1 for r, _, _ in rows if r.pass_fail == "PENDING")
    passed = sum(1 for r in evaluated if r.pass_fail == "PASS")

    pcts = [float(r.percentage) for r in evaluated]
    avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else None

    # Per-course average over evaluated results.
    course_ids = {e.course_id for _, _, e in rows}
    course_names = {
        c.id: c.name
        for c in db.query(Course).filter(Course.id.in_(course_ids or {0}))
    }
    buckets = {}
    for r, _, e in rows:
        if r.pass_fail not in ("PASS", "FAIL"):
            continue
        buckets.setdefault(e.course_id, []).append(float(r.percentage))
    course_avg = [
        {
            "course": course_names.get(cid, f"#{cid}"),
            "avg": round(sum(v) / len(v), 1),
        }
        for cid, v in buckets.items()
    ]
    course_avg.sort(key=lambda x: x["avg"], reverse=True)

    return {
        "totals": {
            "attempts": total_attempts,
            "evaluated": len(evaluated),
            "pending_results": pending,
            "passed": passed,
            "failed": len(evaluated) - passed,
            "avg_percentage": avg_pct,
            "best_percentage": max(pcts) if pcts else None,
        },
        # Last 10 evaluated results, oldest to newest.
        "trend": [
            {"exam": e.name, "percentage": float(r.percentage)}
            for r, _, e in [
                (rr, aa, ee) for rr, aa, ee in rows
                if rr.pass_fail in ("PASS", "FAIL")
            ][-10:]
        ],
        "course_avg": course_avg,
        # 5 most recent results of any status, newest first.
        "recent": [
            {
                "exam_id": e.id,
                "exam_name": e.name,
                "percentage": float(r.percentage),
                "total_marks": float(r.total_marks),
                "pass_fail": r.pass_fail,
                "end_time": a.end_time,
            }
            for r, a, e in list(reversed(rows))[:5]
        ],
    }
