import json

"""Exam change-approval helpers.

A teacher's exam delete or grader change becomes an ExamChangeRequest
(status ``pending``) and is applied only after an admin approves it —
mirroring the question change-request flow in ``question_change.py``.
"""

from fastapi import HTTPException

from app.models.batch import Batch  # noqa: F401  (used for batch lookup clarity)
from app.models.batch_teacher import BatchTeacher
from app.models.exam import Exam, ExamBatch, ExamGrader, ExamQuestion
from app.models.exam_attempt import ExamAttempt, ExamResult, StudentAnswer
from app.models.exam_change_request import ExamChangeRequest
from app.models.exam_feedback import ExamFeedback
from app.models.proctor_event import ProctorEvent
from app.services.activity_service import admin_ids, notify, notify_many
from app.utils.time import utcnow

EXAM_PENDING_MSG = (
    "This exam already has a change request pending admin approval."
)


def pending_request_for(db, exam_id: int, action: str | None = None,
                        assignment_id: int | None = None):
    """First pending request for the exam, optionally narrowed by
    action and (for graders) the assignment id inside the payload."""
    query = db.query(ExamChangeRequest).filter(
        ExamChangeRequest.exam_id == exam_id,
        ExamChangeRequest.status == "pending",
    )
    if action:
        query = query.filter(ExamChangeRequest.action == action)
    for request in query.all():
        if assignment_id is None or (
            (request.payload or {}).get("assignment_id") == assignment_id
        ):
            return request
    return None


def create_exam_change_request(db, exam: Exam, action: str,
                               payload: dict | None, user
                               ) -> ExamChangeRequest:
    """Queue a delete/grader change for admin approval, notify admins."""
    safe_payload = (
        json.loads(json.dumps(payload, default=str))
        if payload is not None else None
    )
    request = ExamChangeRequest(
        exam_id=exam.id,
        action=action,
        payload=safe_payload,
        status="pending",
        requested_by=user.id,
    )
    db.add(request)
    db.flush()

    verb = "deletion" if action == "delete" else "grader change"
    notify_many(
        db,
        admin_ids(db),
        f"Exam {verb} requested",
        f"{user.name} requested a {verb} for exam \"{exam.name}\".",
        "exam.change_request",
        link="/admin/approvals",
    )
    return request


def delete_exam_tree(db, exam: Exam):
    """Delete every row that references the exam, then the exam.

    Model FKs declare ON DELETE CASCADE but deployed schemas may predate
    it — removing dependents explicitly keeps deletes working either way.
    """
    attempt_ids = [
        r[0] for r in db.query(ExamAttempt.id).filter(
            ExamAttempt.exam_id == exam.id
        ).all()
    ]
    if attempt_ids:
        for model in (StudentAnswer, ExamResult, ProctorEvent,
                      ExamFeedback):
            col = getattr(model, 'exam_attempt_id', None) or \
                getattr(model, 'attempt_id')
            db.query(model).filter(
                col.in_(attempt_ids)
            ).delete(synchronize_session=False)
        db.query(ExamAttempt).filter(
            ExamAttempt.id.in_(attempt_ids)
        ).delete(synchronize_session=False)

    assignment_ids = [
        r[0] for r in db.query(ExamBatch.id).filter(
            ExamBatch.exam_id == exam.id
        ).all()
    ]
    if assignment_ids:
        db.query(ExamGrader).filter(
            ExamGrader.exam_batch_id.in_(assignment_ids)
        ).delete(synchronize_session=False)
        db.query(ExamBatch).filter(
            ExamBatch.id.in_(assignment_ids)
        ).delete(synchronize_session=False)

    db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id
    ).delete(synchronize_session=False)
    db.query(ExamFeedback).filter(
        ExamFeedback.exam_id == exam.id
    ).delete(synchronize_session=False)
    db.query(ExamChangeRequest).filter(
        ExamChangeRequest.exam_id == exam.id
    ).delete(synchronize_session=False)
    db.delete(exam)


def apply_exam_request(db, request: ExamChangeRequest):
    """Apply the queued change. Caller sets status/reviewer afterwards."""
    exam = db.query(Exam).filter(Exam.id == request.exam_id).first()
    if not exam:
        return

    if request.action == "delete":
        delete_exam_tree(db, exam)
        return

    if request.action == "graders":
        payload = request.payload or {}
        assignment = db.query(ExamBatch).filter(
            ExamBatch.id == payload.get("assignment_id")
        ).first()
        if not assignment:
            raise HTTPException(
                status_code=400,
                detail="The batch assignment no longer exists — "
                       "reject the request instead.",
            )

        grader_set = set(payload.get("grader_ids") or [])
        batch_teachers = {
            row.user_id
            for row in db.query(BatchTeacher).filter(
                BatchTeacher.batch_id == assignment.batch_id,
                BatchTeacher.is_active == True,  # noqa: E712
            ).all()
        }
        if grader_set - batch_teachers:
            raise HTTPException(
                status_code=400,
                detail="Some requested graders are no longer teachers "
                       "of this batch — reject the request instead.",
            )

        db.query(ExamGrader).filter(
            ExamGrader.exam_batch_id == assignment.id
        ).delete(synchronize_session=False)
        for gid in grader_set:
            db.add(ExamGrader(
                exam_batch_id=assignment.id, user_id=gid
            ))
            notify(
                db, gid,
                f"You can grade: {exam.name}",
                f"You were added as a grader for \"{exam.name}\".",
                "exam.grader_assigned",
                link="/grading",
            )


def resolve_exam_request(db, request: ExamChangeRequest,
                         status_value: str, reviewer,
                         note: str | None = None):
    request.status = status_value
    request.reviewed_by = reviewer.id
    request.reviewed_at = utcnow()
    request.review_note = note

    exam = db.query(Exam).filter(Exam.id == request.exam_id).first()
    ename = (
        exam.name if exam
        else (request.payload or {}).get("exam_name")
        or f"#{request.exam_id}"
    )
    approved = status_value == "approved"
    what = "deletion" if request.action == "delete" else "grader change"
    notify(
        db,
        request.requested_by,
        f"Exam {what} {'approved' if approved else 'rejected'}",
        f"Your {what} request for exam \"{ename}\" was {status_value}"
        f"{f': {note}' if note else ''}.",
        "exam.change_resolved",
        link="/exams",
    )
