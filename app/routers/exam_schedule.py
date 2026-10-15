
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam, ExamBatch
from app.utils.dependencies import require_role
from app.utils.permissions import require_exam_edit, require_exam_view

router = APIRouter(
    prefix="/api/exam-schedule",
    tags=["Exam Scheduling"],
)

teacher_admin = Depends(require_role("admin", "teacher"))


class ExamScheduleUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def validate_times(self):
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("End time must be after start time")
        return self


class ExamActivationUpdate(BaseModel):
    is_active: bool


class BatchScheduleUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def validate_times(self):
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("End time must be after start time")
        return self


@router.put("/exams/{exam_id}/time")
def update_exam_schedule(
    exam_id: int,
    data: ExamScheduleUpdate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    require_exam_edit(current_user, exam)

    updates = data.model_dump(exclude_unset=True)

    start_time = updates.get("start_time", exam.start_time)
    end_time = updates.get("end_time", exam.end_time)

    if start_time and end_time and end_time <= start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time",
        )

    for key, value in updates.items():
        setattr(exam, key, value)

    db.commit()
    db.refresh(exam)

    return {
        "message": "Exam schedule updated",
        "exam_id": exam.id,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
    }


@router.patch("/exams/{exam_id}/activation")
def update_exam_activation(
    exam_id: int,
    data: ExamActivationUpdate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    require_exam_edit(current_user, exam)

    exam.is_active = data.is_active
    db.commit()

    return {
        "message": "Exam activation updated",
        "exam_id": exam.id,
        "is_active": exam.is_active,
    }


@router.put("/exams/{exam_id}/batches/{batch_id}/time")
def update_batch_schedule(
    exam_id: int,
    batch_id: int,
    data: BatchScheduleUpdate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam:
        require_exam_edit(current_user, exam)

    assignment = db.query(ExamBatch).filter(
        ExamBatch.exam_id == exam_id,
        ExamBatch.batch_id == batch_id,
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="Exam batch assignment not found",
        )

    updates = data.model_dump(exclude_unset=True)

    start_time = updates.get("start_time", assignment.start_time)
    end_time = updates.get("end_time", assignment.end_time)

    if start_time and end_time and end_time <= start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time",
        )

    for key, value in updates.items():
        setattr(assignment, key, value)

    db.commit()
    db.refresh(assignment)

    return {
        "message": "Batch schedule updated",
        "exam_id": assignment.exam_id,
        "batch_id": assignment.batch_id,
        "start_time": assignment.start_time,
        "end_time": assignment.end_time,
    }


@router.get("/exams/{exam_id}")
def get_exam_schedule(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    require_exam_view(current_user, exam, db)

    assignments = db.query(ExamBatch).filter(
        ExamBatch.exam_id == exam_id
    ).all()

    return {
        "exam_id": exam.id,
        "exam_name": exam.name,
        "is_active": exam.is_active,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
        "batch_schedules": [
            {
                "batch_id": item.batch_id,
                "start_time": item.start_time,
                "end_time": item.end_time,
            }
            for item in assignments
        ],
    }
