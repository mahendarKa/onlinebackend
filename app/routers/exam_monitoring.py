
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt, ExamResult
from app.models.user import User
from app.utils.dependencies import require_role
from app.utils.permissions import (
    is_admin,
    require_exam_view,
    teacher_exam_ids,
)

router = APIRouter(
    prefix="/api/exam-monitoring",
    tags=["Exam Monitoring"],
)

teacher_admin = Depends(require_role("admin", "teacher"))


# LIST ALL EXAMS WITH ATTEMPT COUNTS
@router.get("/exams")
def list_exams(
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    query = db.query(Exam)
    if not is_admin(current_user):
        query = query.filter(
            Exam.id.in_(teacher_exam_ids(db, current_user.id) or {0})
        )
    exams = query.order_by(Exam.id.desc()).all()
    output = []

    for exam in exams:
        attempts = db.query(ExamAttempt).filter(
            ExamAttempt.exam_id == exam.id
        ).all()

        output.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "is_active": exam.is_active,
            "total_attempts": len(attempts),
            "in_progress": sum(
                1 for a in attempts if a.status == "in_progress"
            ),
            "submitted": sum(
                1 for a in attempts if a.status == "submitted"
            ),
            "evaluated": sum(
                1 for a in attempts if a.status == "evaluated"
            ),
        })

    return output


# VIEW STUDENT ATTEMPTS FOR ONE EXAM
@router.get("/exams/{exam_id}/attempts")
def exam_attempts(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    require_exam_view(current_user, exam, db)

    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam_id
    ).order_by(ExamAttempt.id.desc()).all()

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
            "start_time": attempt.start_time,
            "end_time": attempt.end_time,
            "status": attempt.status,
            "marks_obtained": (
                result.total_marks if result else attempt.total_marks
            ),
            "percentage": result.percentage if result else None,
            "pass_fail": result.pass_fail if result else None,
        })

    return output


# VIEW ONE ATTEMPT'S SUMMARY
@router.get("/attempts/{attempt_id}")
def attempt_detail(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == attempt_id
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    exam = db.query(Exam).filter(
        Exam.id == attempt.exam_id
    ).first()

    if exam:
        require_exam_view(current_user, exam, db)

    student = db.query(User).filter(
        User.id == attempt.user_id
    ).first()

    result = db.query(ExamResult).filter(
        ExamResult.exam_attempt_id == attempt.id
    ).first()

    return {
        "attempt_id": attempt.id,
        "exam_id": attempt.exam_id,
        "exam_name": exam.name if exam else None,
        "student_id": attempt.user_id,
        "student_name": student.name if student else None,
        "attempt_no": attempt.attempt_no,
        "start_time": attempt.start_time,
        "end_time": attempt.end_time,
        "status": attempt.status,
        "marks_obtained": result.total_marks if result else attempt.total_marks,
        "total_questions": result.total_questions if result else None,
        "attempted": result.attempted if result else None,
        "correct": result.correct if result else None,
        "wrong": result.wrong if result else None,
        "skipped": result.skipped if result else None,
        "percentage": result.percentage if result else None,
        "pass_fail": result.pass_fail if result else None,
    }
