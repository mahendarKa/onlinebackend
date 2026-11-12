"""Proctoring: students report violations during an attempt; teachers
review the log afterwards.

Events are short machine-typed rows (see PROCTOR_EVENT_TYPES). The
exam player posts them on browser-behaviour signals (tab hidden,
copy/paste, fullscreen exit) and on webcam AI flags (no face, multiple
faces, looking away). Flagged webcam events also upload the captured
frame so a human can verify the flag — AI detection is evidence,
not proof.
"""
import uuid
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt
from app.models.proctor_event import ProctorEvent
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.schemas.proctoring import ProctorEventCreate, PROCTOR_EVENT_TYPES
from app.utils.dependencies import require_role
from app.utils.permissions import require_exam_view

router = APIRouter(prefix="/api/proctoring", tags=["Proctoring"])

student_only = Depends(require_role("student"))
teacher_admin = Depends(require_role("admin", "teacher"))

SNAPSHOT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SNAPSHOT_MAX_BYTES = 3 * 1024 * 1024  # webcam jpegs are well under 1 MB


def _own_attempt(attempt_id: int, user: User, db: Session) -> ExamAttempt:
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == attempt_id
    ).first()
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(
            status_code=400,
            detail="Attempt is no longer in progress",
        )
    return attempt


def _event_dict(e: ProctorEvent) -> dict:
    return {
        "id": e.id,
        "attempt_id": e.attempt_id,
        "event_type": e.event_type,
        "detail": e.detail,
        "snapshot_url": e.snapshot_url,
        "created_at": e.created_at,
    }


# STUDENT: report a violation during an attempt
@router.post("/events", status_code=201)
def log_event(
    data: ProctorEventCreate,
    db: Session = Depends(get_db),
    current_user: User = student_only,
):
    _own_attempt(data.attempt_id, current_user, db)
    if data.event_type not in PROCTOR_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Unknown event type")

    event = ProctorEvent(
        attempt_id=data.attempt_id,
        event_type=data.event_type,
        detail=data.detail,
    )
    db.add(event)
    db.commit()
    return {"id": event.id}


# STUDENT: upload a webcam frame for a flagged event
@router.post("/snapshots", status_code=201)
async def upload_snapshot(
    attempt_id: int = Form(...),
    event_type: str = Form("no_face"),
    detail: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = student_only,
):
    _own_attempt(attempt_id, current_user, db)
    if event_type not in PROCTOR_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Unknown event type")

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    if ext not in SNAPSHOT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    content_type = file.content_type or ""
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > SNAPSHOT_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Snapshot too large")

    name = f"proc_{uuid.uuid4().hex}{ext}"
    db.add(UploadedFile(
        name=name,
        content_type=content_type or "image/jpeg",
        data=data,
    ))

    event = ProctorEvent(
        attempt_id=attempt_id,
        event_type=event_type,
        detail=detail,
        snapshot_url=f"/api/uploads/{name}",
    )
    db.add(event)
    db.commit()
    return {"id": event.id, "snapshot_url": event.snapshot_url}


# TEACHER/ADMIN: violation log for one attempt
@router.get("/attempts/{attempt_id}/events")
def attempt_events(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = teacher_admin,
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == attempt_id
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if exam:
        require_exam_view(current_user, exam, db)

    events = db.query(ProctorEvent).filter(
        ProctorEvent.attempt_id == attempt_id
    ).order_by(ProctorEvent.id).all()
    return [_event_dict(e) for e in events]


# TEACHER/ADMIN: per-attempt violation counts for one exam
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

    rows = (
        db.query(
            ProctorEvent.attempt_id,
            func.count(ProctorEvent.id),
            func.max(ProctorEvent.created_at),
        )
        .join(ExamAttempt, ProctorEvent.attempt_id == ExamAttempt.id)
        .filter(ExamAttempt.exam_id == exam_id)
        .group_by(ProctorEvent.attempt_id)
        .all()
    )
    return {
        str(attempt_id): {"count": count, "last_at": last_at}
        for attempt_id, count, last_at in rows
    }
