import csv
import io
from typing import Optional

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, UploadFile, status
)
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    AdminUserCreate,
    UserUpdate,
    UserResponse
)
from app.utils.security import hash_password
from app.utils.dependencies import get_current_user, require_role
from sqlalchemy.exc import IntegrityError

from app.models.batch_student import BatchStudent
from app.models.batch_teacher import BatchTeacher
from app.models.exam_attempt import ExamAttempt, StudentAnswer
from app.models.exam_feedback import ExamFeedback
from app.models.notification import Notification
from app.services.activity_service import log_audit


ALLOWED_ROLES = ["superadmin", "admin", "teacher", "student"]


router = APIRouter(
    prefix="/api/users",
    tags=["Users"]
)


# --------------------------------------------------
# PUBLIC STUDENT REGISTRATION
# --------------------------------------------------

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    new_user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
        password=hash_password(user_data.password),
        role="student",
        mobile_number=user_data.mobile_number,
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# --------------------------------------------------
# ADMIN CREATE USER
# --------------------------------------------------

@router.post(
    "/admin/create",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def admin_create_user(
    user_data: AdminUserCreate,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    if user_data.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role"
        )

    if (
        user_data.role == "superadmin"
        and current_user.role != "superadmin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superadmin can create another superadmin"
        )

    new_user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
        password=hash_password(user_data.password),
        role=user_data.role,
        mobile_number=user_data.mobile_number,
        profile_pic=user_data.profile_pic,
        is_active=True
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    db.refresh(new_user)

    log_audit(
        db, current_user.id, "user.create", "user", new_user.id,
        details=f"{new_user.email} ({new_user.role})",
    )
    db.commit()

    return new_user


# --------------------------------------------------
# ADMIN BULK CREATE USERS FROM CSV
# --------------------------------------------------

# Expected CSV columns:
#   first_name,last_name,email,password[,role][,mobile_number]
# 'last_name' is optional; a legacy 'name' column is also accepted
# (split on the first space) when first_name is absent.
REQUIRED_CSV_COLS = {"email", "password"}


@router.post("/admin/bulk-upload")
def admin_bulk_upload_users(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are accepted",
        )

    raw = file.file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file too large (max 2 MB)",
        )

    # utf-8-sig strips a BOM if the file was exported from Excel.
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not valid UTF-8 text",
        )

    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    missing = REQUIRED_CSV_COLS - headers
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Missing required column(s): {', '.join(sorted(missing))}. "
                "Expected: first_name,last_name,email,password"
                "[,role][,mobile_number]"
            ),
        )

    if "first_name" not in headers and "name" not in headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provide 'first_name' (and optional 'last_name') "
                "or a 'name' column"
            ),
        )

    created = []
    skipped = []
    errors = []
    seen_emails = set()

    existing_emails = {
        u.email for u in db.query(User.email).all()
    }

    for row_no, row in enumerate(reader, start=2):  # row 1 = header
        row = {
            (k.strip().lower() if k else k): (v.strip() if v else "")
            for k, v in row.items()
        }

        first_name = row.get("first_name", "")
        last_name = row.get("last_name", "") or None
        if not first_name:
            # Legacy single 'name' column: split on the first space.
            legacy = row.get("name", "").strip()
            if legacy:
                first_name, _, rest = legacy.partition(" ")
                last_name = last_name or (rest.strip() or None)
        email = row.get("email", "").lower()
        password = row.get("password", "")
        role = (row.get("role") or "student").lower()
        mobile = row.get("mobile_number") or None

        # Skip completely empty lines silently.
        if not any([
            first_name, last_name, email, password,
            row.get("role"), mobile,
        ]):
            continue

        if not first_name or not email or not password:
            errors.append(
                {"row": row_no, "email": email or "-",
                 "reason": "first_name, email and password are required"}
            )
            continue

        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append(
                {"row": row_no, "email": email, "reason": "invalid email"}
            )
            continue

        if len(password) < 6:
            errors.append(
                {"row": row_no, "email": email,
                 "reason": "password must be at least 6 characters"}
            )
            continue

        if mobile and sum(c.isdigit() for c in mobile) < 10:
            errors.append(
                {"row": row_no, "email": email or "-",
                 "reason": "mobile_number must be at least 10 digits"}
            )
            continue

        if role not in ALLOWED_ROLES:
            errors.append(
                {"row": row_no, "email": email,
                 "reason": f"invalid role '{role}'"}
            )
            continue

        if role == "superadmin" and current_user.role != "superadmin":
            errors.append(
                {"row": row_no, "email": email,
                 "reason": "only a superadmin can create superadmin users"}
            )
            continue

        if email in existing_emails or email in seen_emails:
            skipped.append(
                {"row": row_no, "email": email,
                 "reason": "email already exists"}
            )
            continue

        seen_emails.add(email)
        db.add(User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=hash_password(password),
            role=role,
            mobile_number=mobile,
            is_active=True,
        ))
        created.append({"row": row_no, "email": email, "role": role})

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database rejected some rows; no users were created",
        )

    if created:
        log_audit(
            db, current_user.id, "user.bulk_create", "user", None,
            details=f"{len(created)} users from {file.filename}",
        )
        db.commit()

    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


# --------------------------------------------------
# GET ALL USERS
# --------------------------------------------------

@router.get(
    "/",
    response_model=list[UserResponse]
)
def get_users(
    role: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role("admin", "teacher")
    )
):

    query = db.query(User)

    if role:
        if role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role filter"
            )
        query = query.filter(User.role == role)

    return query.order_by(User.id).all()


# --------------------------------------------------
# CURRENT USER PROFILE
# --------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user


# --------------------------------------------------
# GET USER BY ID
# --------------------------------------------------

@router.get(
    "/{user_id}",
    response_model=UserResponse
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


# --------------------------------------------------
# ADMIN ACTIVATE / DEACTIVATE USER
# --------------------------------------------------

@router.put(
    "/admin/{user_id}/status",
    response_model=UserResponse
)
def change_user_status(
    user_id: int,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = not user.is_active

    log_audit(
        db, current_user.id, "user.status", "user", user.id,
        details=f"{user.email} -> "
                f"{'active' if user.is_active else 'inactive'}",
    )
    db.commit()
    db.refresh(user)

    return user


# --------------------------------------------------
# ADMIN UPDATE USER
# --------------------------------------------------

@router.put(
    "/{user_id}",
    response_model=UserResponse
)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if (
        user.role == "superadmin"
        and current_user.role != "superadmin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superadmin can edit a superadmin"
        )

    update_data = user_data.model_dump(exclude_unset=True)

    if (
        update_data.get("role") == "superadmin"
        and current_user.role != "superadmin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superadmin can grant the superadmin role"
        )

    if "email" in update_data:
        existing_user = (
            db.query(User)
            .filter(
                User.email == update_data["email"],
                User.id != user_id
            )
            .first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    if "role" in update_data:
        if update_data["role"] not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role"
            )

    if "password" in update_data:
        update_data["password"] = hash_password(
            update_data["password"]
        )

    for key, value in update_data.items():
        setattr(user, key, value)

    log_audit(
        db, current_user.id, "user.update", "user", user.id,
        details=f"{user.email} fields: "
                f"{', '.join(sorted(update_data.keys()))}",
    )
    db.commit()
    db.refresh(user)

    return user


# --------------------------------------------------
# ADMIN DELETE USER
# --------------------------------------------------

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )

    if (
        user.role == "superadmin"
        and current_user.role != "superadmin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superadmin can delete a superadmin"
        )

    # Remove dependent rows that do not cascade on users.id.
    db.query(BatchStudent).filter(
        BatchStudent.user_id == user_id
    ).delete(synchronize_session=False)
    db.query(BatchTeacher).filter(
        BatchTeacher.user_id == user_id
    ).delete(synchronize_session=False)
    db.query(Notification).filter(
        Notification.user_id == user_id
    ).delete(synchronize_session=False)
    db.query(ExamFeedback).filter(
        ExamFeedback.student_id == user_id
    ).delete(synchronize_session=False)
    db.query(StudentAnswer).filter(
        StudentAnswer.evaluated_by == user_id
    ).update({"evaluated_by": None}, synchronize_session=False)

    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.user_id == user_id
    ).all()
    for attempt in attempts:
        db.delete(attempt)  # answers/results cascade at DB level

    try:
        log_audit(
            db, current_user.id, "user.delete", "user", user.id,
            details=f"{user.email} ({user.role})",
        )
        db.delete(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "User owns related records (courses, exams, "
                "questions or batches). Deactivate the user "
                "or reassign the content first."
            ),
        )

    return {"message": "User deleted successfully"}