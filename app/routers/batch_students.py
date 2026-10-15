from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from app.config.database import get_db

from app.models.batch_student import BatchStudent
from app.models.batch import Batch
from app.models.user import User

from app.schemas.batch_student import (
    BatchStudentCreate,
    BatchStudentResponse
)

from app.utils.dependencies import (
    get_current_user,
    require_role
)
from app.utils.permissions import require_batch_access
from app.services.activity_service import notify


def _require_enrollment_access(db, current_user, batch_id):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    require_batch_access(current_user, batch, db)
    return batch


router = APIRouter(
    prefix="/api/batch-students",
    tags=["Batch Students"]
)


# --------------------------------------------------
# ENROLL STUDENT
# --------------------------------------------------

@router.post(
    "/",
    response_model=BatchStudentResponse,
    status_code=status.HTTP_201_CREATED
)
def enroll_student(
    enrollment_data: BatchStudentCreate,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):

    # Check batch (and this teacher's access to it)
    batch = _require_enrollment_access(
        db, current_user, enrollment_data.batch_id
    )

    # Check user
    student = (
        db.query(User)
        .filter(
            User.id == enrollment_data.user_id
        )
        .first()
    )

    if not student:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Only students can be enrolled
    if student.role != "student":

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only students can be enrolled into a batch"
        )

    # Check duplicate enrollment
    existing = (
        db.query(BatchStudent)
        .filter(
            BatchStudent.batch_id ==
            enrollment_data.batch_id,
            BatchStudent.user_id ==
            enrollment_data.user_id
        )
        .first()
    )

    if existing:

        if existing.is_active:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student is already enrolled in this batch"
            )

        # Reactivate previous enrollment
        existing.is_active = True

        notify(
            db, student.id,
            f"Enrolled in batch: {batch.name}",
            f"You were re-enrolled in batch \"{batch.name}\".",
            "batch.enrolled",
        )
        db.commit()
        db.refresh(existing)

        return existing

    enrollment = BatchStudent(
        batch_id=enrollment_data.batch_id,
        user_id=enrollment_data.user_id,
        is_active=True
    )

    db.add(enrollment)
    notify(
        db, student.id,
        f"Enrolled in batch: {batch.name}",
        f"You were enrolled in batch \"{batch.name}\".",
        "batch.enrolled",
    )
    db.commit()
    db.refresh(enrollment)

    return enrollment


# --------------------------------------------------
# LIST STUDENTS IN BATCH
# --------------------------------------------------

@router.get(
    "/batch/{batch_id}",
    response_model=list[BatchStudentResponse]
)
def get_batch_students(
    batch_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    batch = (
        db.query(Batch)
        .filter(Batch.id == batch_id)
        .first()
    )

    if not batch:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    if current_user.role == "teacher":
        require_batch_access(current_user, batch, db)
    elif current_user.role == "student":
        enrolled = db.query(BatchStudent).filter(
            BatchStudent.batch_id == batch_id,
            BatchStudent.user_id == current_user.id,
            BatchStudent.is_active == True,  # noqa: E712
        ).first()
        if not enrolled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this batch"
            )

    return (
        db.query(BatchStudent)
        .filter(
            BatchStudent.batch_id == batch_id,
            BatchStudent.is_active == True
        )
        .all()
    )


# --------------------------------------------------
# GET STUDENT'S BATCHES
# --------------------------------------------------

@router.get(
    "/student/{student_id}",
    response_model=list[BatchStudentResponse]
)
def get_student_batches(
    student_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    student = (
        db.query(User)
        .filter(User.id == student_id)
        .first()
    )

    if not student:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Students can only see their own batches
    if (
        current_user.role == "student"
        and current_user.id != student_id
    ):

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another student's batches"
        )

    return (
        db.query(BatchStudent)
        .filter(
            BatchStudent.user_id == student_id,
            BatchStudent.is_active == True
        )
        .all()
    )


# --------------------------------------------------
# DEACTIVATE ENROLLMENT
# --------------------------------------------------

@router.put(
    "/{enrollment_id}/deactivate",
    response_model=BatchStudentResponse
)
def deactivate_enrollment(
    enrollment_id: int,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):

    enrollment = (
        db.query(BatchStudent)
        .filter(
            BatchStudent.id == enrollment_id
        )
        .first()
    )

    if not enrollment:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )

    _require_enrollment_access(db, current_user, enrollment.batch_id)

    enrollment.is_active = False

    db.commit()
    db.refresh(enrollment)

    return enrollment


# --------------------------------------------------
# ACTIVATE ENROLLMENT
# --------------------------------------------------

@router.put(
    "/{enrollment_id}/activate",
    response_model=BatchStudentResponse
)
def activate_enrollment(
    enrollment_id: int,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):

    enrollment = (
        db.query(BatchStudent)
        .filter(
            BatchStudent.id == enrollment_id
        )
        .first()
    )

    if not enrollment:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )

    _require_enrollment_access(db, current_user, enrollment.batch_id)

    enrollment.is_active = True

    db.commit()
    db.refresh(enrollment)

    return enrollment


# --------------------------------------------------
# REMOVE ENROLLMENT
# --------------------------------------------------

@router.delete(
    "/{enrollment_id}"
)
def remove_enrollment(
    enrollment_id: int,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    enrollment = (
        db.query(BatchStudent)
        .filter(
            BatchStudent.id == enrollment_id
        )
        .first()
    )

    if not enrollment:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )

    db.delete(enrollment)
    db.commit()

    return {
        "message": "Student removed from batch successfully"
    }