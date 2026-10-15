
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
)
from app.utils.dependencies import get_current_user, require_role
from app.services.activity_service import log_audit

router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
)

# Every signed-in user can read/clear their own notifications.
any_user = Depends(get_current_user)
teacher_admin = Depends(require_role("admin", "teacher"))


# ADMIN/TEACHER: SEND NOTIFICATION TO A USER
@router.post("/", response_model=NotificationResponse, status_code=201)
def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    user = db.query(User).filter(
        User.id == data.user_id,
        User.is_active == True,
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Active user not found")

    notification = Notification(**data.model_dump())
    db.add(notification)
    db.flush()
    log_audit(
        db, current_user.id, "notification.send", "user", user.id,
        details=f"{notification.title} -> {user.email}",
    )
    db.commit()
    db.refresh(notification)

    return notification


# VIEW OWN NOTIFICATIONS (ALL ROLES)
@router.get("/my", response_model=list[NotificationResponse])
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user=any_user,
):
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


# MARK NOTIFICATION AS READ
@router.patch("/{notification_id}/read")
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user=any_user,
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    notification.is_read = True
    db.commit()

    return {"message": "Notification marked as read"}


# MARK ALL NOTIFICATIONS AS READ
@router.patch("/my/read-all")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user=any_user,
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update(
        {Notification.is_read: True},
        synchronize_session=False,
    )

    db.commit()

    return {"message": "All notifications marked as read"}


# UNREAD COUNT
@router.get("/my/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user=any_user,
):
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).count()

    return {"unread_count": count}
