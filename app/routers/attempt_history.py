from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt, ExamResult
from app.models.user import User
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/attempt-history",
    tags=["Attempt History"]
)


@router.get("/my-attempts")
def get_my_attempt_history(
    current_user: User = Depends(
        require_role("student")
    ),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(ExamAttempt, Exam)
        .join(Exam, ExamAttempt.exam_id == Exam.id)
        .filter(ExamAttempt.user_id == current_user.id)
        .order_by(ExamAttempt.start_time.desc())
        .all()
    )

    history = []

    for attempt, exam in attempts:
        result = db.query(ExamResult).filter(
            ExamResult.exam_attempt_id == attempt.id
        ).first()

        history.append({
            "attempt_id": attempt.id,
            "exam_id": exam.id,
            "exam_name": exam.name,
            "attempt_number": attempt.attempt_no,
            "start_time": attempt.start_time,
            "end_time": attempt.end_time,
            "status": attempt.status,
            "total_marks": (
                result.total_marks if result else None
            ),
            "percentage": (
                result.percentage if result else None
            ),
            "pass_fail": (
                result.pass_fail if result else None
            ),
        })

    return {
        "total_attempts": len(history),
        "attempts": history,
    }


@router.get("/exams/{exam_id}")
def get_my_exam_attempts(
    exam_id: int,
    current_user: User = Depends(
        require_role("student")
    ),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if not exam:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    attempts = (
        db.query(ExamAttempt)
        .filter(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.user_id == current_user.id,
        )
        .order_by(ExamAttempt.attempt_no.desc())
        .all()
    )

    history = []

    for attempt in attempts:
        result = db.query(ExamResult).filter(
            ExamResult.exam_attempt_id == attempt.id
        ).first()

        history.append({
            "attempt_id": attempt.id,
            "attempt_number": attempt.attempt_no,
            "start_time": attempt.start_time,
            "end_time": attempt.end_time,
            "status": attempt.status,
            "total_marks": (
                result.total_marks if result else None
            ),
            "percentage": (
                result.percentage if result else None
            ),
            "pass_fail": (
                result.pass_fail if result else None
            ),
        })

    return {
        "exam_id": exam.id,
        "exam_name": exam.name,
        "total_attempts": len(history),
        "attempts": history,
    }