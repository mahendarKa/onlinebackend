"""Audit-log and notification helpers.

Callers add rows inside the request's own transaction — these helpers
never commit, so a failed request never leaves a dangling log entry.
"""
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.notification import Notification


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
):
    """Queue a notification row; committed with the caller's commit."""
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
    ))


def notify_many(
    db: Session,
    user_ids: Iterable[int],
    title: str,
    message: str,
    notification_type: str = "general",
):
    for uid in set(user_ids):
        notify(db, uid, title, message, notification_type)
