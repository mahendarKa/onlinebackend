from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt
from app.models.exam_feedback import ExamFeedback
from app.models.user import User
from app.schemas.exam_feedback import (
    ExamFeedbackCreate,
    ExamFeedbackResponse,
)
from app.utils.dependencies import get_current_user, require_role


router = APIRouter(
    prefix="/api/exam-feedback",
    tags=["Exam Feedback"],
)


@router.post("/", response_model=ExamFeedbackResponse, status_code=201)
def submit_exam_feedback(
    data: ExamFeedbackCreate,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == data.attempt_id,
        ExamAttempt.user_id == current_user.id,
    ).first()

    if not attempt:
        raise HTTPException(
            status_code=404,
            detail="Exam attempt not found",
        )

    if attempt.status not in ("submitted", "evaluated"):
        raise HTTPException(
            status_code=400,
            detail="Feedback is available only after exam submission",
        )

    existing = db.query(ExamFeedback).filter(
        ExamFeedback.attempt_id == attempt.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Feedback already submitted for this attempt",
        )

    feedback = ExamFeedback(
        exam_id=attempt.exam_id,
        attempt_id=attempt.id,
        student_id=current_user.id,
        rating=data.rating,
        comments=data.comments,
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return feedback


@router.get("/my", response_model=list[ExamFeedbackResponse])
def get_my_feedback(
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    return (
        db.query(ExamFeedback)
        .filter(ExamFeedback.student_id == current_user.id)
        .order_by(ExamFeedback.created_at.desc())
        .all()
    )


@router.get("/exams/{exam_id}", response_model=list[ExamFeedbackResponse])
def get_exam_feedback(
    exam_id: int,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found",
        )

    return (
        db.query(ExamFeedback)
        .filter(ExamFeedback.exam_id == exam_id)
        .order_by(ExamFeedback.created_at.desc())
        .all()
    )


@router.get("/summary/{exam_id}")
def get_feedback_summary(
    exam_id: int,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found",
        )

    feedback_rows = db.query(ExamFeedback).filter(
        ExamFeedback.exam_id == exam_id
    ).all()

    total = len(feedback_rows)
    average = (
        round(sum(item.rating for item in feedback_rows) / total, 2)
        if total else 0
    )

    distribution = {
        str(star): sum(
            1 for item in feedback_rows if item.rating == star
        )
        for star in range(1, 6)
    }

    return {
        "exam_id": exam_id,
        "total_feedback": total,
        "average_rating": average,
        "rating_distribution": distribution,
    }