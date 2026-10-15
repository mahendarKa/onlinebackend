
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam, ExamBatch
from app.models.batch_student import BatchStudent
from app.models.exam_attempt import ExamAttempt
from app.utils.dependencies import require_role

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
    now = datetime.now()

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
            "completed_attempts": len(completed_attempts),
            "status": status,
        })

    return output
