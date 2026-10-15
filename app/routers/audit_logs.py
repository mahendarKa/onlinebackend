
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.utils.dependencies import require_role

router = APIRouter(
    prefix="/api/audit-logs",
    tags=["Audit Logs"],
)

admin_only = Depends(require_role("admin"))


@router.get("/")
def list_audit_logs(
    user_id: int | None = Query(default=None, gt=0),
    action: str | None = None,
    entity_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = admin_only,
):
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)

    if action:
        query = query.filter(AuditLog.action == action)

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="end_date cannot be earlier than start_date",
        )

    total = query.count()

    logs = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Attach actor name/email so the UI doesn't need per-row lookups.
    actor_ids = {log.user_id for log in logs if log.user_id}
    actors = {
        u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()
    } if actor_ids else {}
    items = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "user_name": actors[log.user_id].name
                if log.user_id in actors else None,
            "user_email": actors[log.user_id].email
                if log.user_id in actors else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at,
        }
        for log in logs
    ]

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{log_id}")
def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = admin_only,
):
    log = db.query(AuditLog).filter(
        AuditLog.id == log_id
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return log
