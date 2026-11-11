"""Audit-log and notification helpers.

Callers add rows inside the request's own transaction — these helpers
never commit, so a failed request never leaves a dangling log entry.
(notify_expired_exams is the exception: it runs as a standalone lazy
pass and commits itself.)
"""
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.user import User
from app.models.exam import Exam, ExamBatch, ExamGrader
from app.models.batch_student import BatchStudent
from app.models.batch_teacher import BatchTeacher
from app.utils.time import utcnow


def admin_ids(db: Session, exclude: int | None = None) -> list[int]:
    """IDs of active admin and superadmin users, minus `exclude`."""
    query = db.query(User.id).filter(
        User.role.in_(["admin", "superadmin"]),
        User.is_active.is_(True),
    )
    if exclude is not None:
        query = query.filter(User.id != exclude)
    return [row.id for row in query.all()]


def log_audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: str | None = None,
    ip_address: str | None = None,
):
    """Queue an audit-log row; committed with the caller's commit."""
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    ))


def notify(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "general",
    link: str = None,
):
    """Queue a notification row; committed with the caller's commit.

    `link` is an optional frontend route (e.g. "/exams/4") that the
    notifications page navigates to when the row is clicked.
    """
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
    ))


def notify_many(
    db: Session,
    user_ids: Iterable[int],
    title: str,
    message: str,
    notification_type: str = "general",
    link: str = None,
):
    for uid in set(user_ids):
        notify(db, uid, title, message, notification_type, link)


def notify_expired_exams(db: Session) -> int:
    """Notify everyone involved once an exam's availability ends.

    Runs lazily from exam-list endpoints. Recipients: enrolled
    students, assigned batch teachers, selected graders, the creator,
    and all admin/superadmin users. Each exam notifies only once —
    the "exam.expired" audit row it writes is the dedup marker.
    """
    now = utcnow()

    expired = db.query(Exam).filter(
        Exam.end_time.isnot(None),
        Exam.end_time < now,
    ).all()
    if not expired:
        return 0

    already_notified = {
        row.entity_id
        for row in db.query(AuditLog.entity_id).filter(
            AuditLog.action == "exam.expired",
            AuditLog.entity_type == "exam",
            AuditLog.entity_id.in_([e.id for e in expired]),
        ).all()
    }

    notified = 0

    for exam in expired:
        if exam.id in already_notified:
            continue

        assignments = db.query(ExamBatch).filter(
            ExamBatch.exam_id == exam.id
        ).all()
        batch_ids = [a.batch_id for a in assignments]
        assignment_ids = [a.id for a in assignments]

        student_ids = {
            r.user_id for r in db.query(BatchStudent.user_id).filter(
                BatchStudent.batch_id.in_(batch_ids or {0}),
                BatchStudent.is_active.is_(True),
            ).all()
        }
        teacher_ids = {
            r.user_id for r in db.query(BatchTeacher.user_id).filter(
                BatchTeacher.batch_id.in_(batch_ids or {0}),
                BatchTeacher.is_active.is_(True),
            ).all()
        }
        grader_ids = {
            r.user_id for r in db.query(ExamGrader.user_id).filter(
                ExamGrader.exam_batch_id.in_(assignment_ids or {0}),
            ).all()
        }

        # Students land on their attempt history; staff land on the
        # monitoring page — one broadcast, role-appropriate links.
        staff_ids = teacher_ids | grader_ids | set(admin_ids(db))
        if exam.created_by:
            staff_ids.add(exam.created_by)
        staff_ids -= student_ids
        recipients = student_ids | staff_ids

        when = exam.end_time.strftime("%d %b %Y %I:%M %p")
        title = f"Exam ended: {exam.name}"
        body = f"\"{exam.name}\" availability ended at {when}."
        notify_many(
            db, student_ids, title, body, "exam.expired",
            link="/attempts",
        )
        notify_many(
            db, staff_ids, title, body, "exam.expired",
            link="/monitoring",
        )
        log_audit(
            db, None, "exam.expired", "exam", exam.id,
            details=f"'{exam.name}' ended at {when}; "
                    f"{len(recipients)} users notified",
        )
        notified += 1

    if notified:
        db.commit()

    return notified
