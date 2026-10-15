import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt, ExamResult
from app.models.user import User
from app.utils.dependencies import require_role
from app.utils.permissions import require_exam_view


router = APIRouter(
    prefix="/api/result-export",
    tags=["Result Export"]
)


@router.get("/exams/{exam_id}/csv")
def export_exam_results_csv(
    exam_id: int,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):
    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    require_exam_view(current_user, exam, db)

    results = (
        db.query(ExamResult, ExamAttempt, User)
        .join(
            ExamAttempt,
            ExamResult.exam_attempt_id == ExamAttempt.id
        )
        .join(User, ExamAttempt.user_id == User.id)
        .filter(ExamAttempt.exam_id == exam_id)
        .order_by(ExamAttempt.user_id, ExamAttempt.attempt_no)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Exam ID",
        "Exam Name",
        "Student ID",
        "Student Name",
        "Student Email",
        "Attempt Number",
        "Total Questions",
        "Attempted",
        "Correct",
        "Wrong",
        "Skipped",
        "Total Marks",
        "Percentage",
        "Pass/Fail"
    ])

    for result, attempt, student in results:
        writer.writerow([
            exam.id,
            exam.name,
            student.id,
            student.name,
            student.email,
            attempt.attempt_no,
            result.total_questions,
            result.attempted,
            result.correct,
            result.wrong,
            result.skipped,
            result.total_marks,
            result.percentage,
            result.pass_fail
        ])

    output.seek(0)

    filename = f"exam_{exam_id}_results.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        }
    )