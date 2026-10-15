from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from app.config.database import get_db

from app.models.batch_teacher import BatchTeacher
from app.models.batch import Batch
from app.models.user import User

from app.schemas.batch_teacher import (
    BatchTeacherCreate,
    BatchTeacherResponse
)

from app.utils.dependencies import (
    get_current_user,
    require_role
)
from app.services.activity_service import notify


router = APIRouter(
    prefix="/api/batch-teachers",
    tags=["Batch Teachers"]
)


# --------------------------------------------------
# ASSIGN TEACHER TO BATCH
# --------------------------------------------------

@router.post(
    "/",
    response_model=BatchTeacherResponse,
    status_code=status.HTTP_201_CREATED
)
def assign_teacher(
    assignment_data: BatchTeacherCreate,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    batch = (
        db.query(Batch)
        .filter(Batch.id == assignment_data.batch_id)
        .first()
    )

    if not batch:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    teacher = (
        db.query(User)
        .filter(User.id == assignment_data.user_id)
        .first()
    )

    if not teacher:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if teacher.role != "teacher":

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only teachers can be assigned to a batch"
        )

    existing = (
        db.query(BatchTeacher)
        .filter(
            BatchTeacher.batch_id == assignment_data.batch_id,
            BatchTeacher.user_id == assignment_data.user_id
        )
        .first()
    )

    if existing:

        if existing.is_active:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Teacher is already assigned to this batch"
            )

        existing.is_active = True

        notify(
            db, teacher.id,
            f"Assigned to batch: {batch.name}",
            f"You were re-assigned to batch \"{batch.name}\" "
            "as a teacher.",
            "batch.assigned",
        )
        db.commit()
        db.refresh(existing)

        return existing

    assignment = BatchTeacher(
        batch_id=assignment_data.batch_id,
        user_id=assignment_data.user_id,
        is_active=True
    )

    db.add(assignment)
    notify(
        db, teacher.id,
        f"Assigned to batch: {batch.name}",
        f"You were assigned to batch \"{batch.name}\" as a teacher.",
        "batch.assigned",
    )
    db.commit()
    db.refresh(assignment)

    return assignment


# --------------------------------------------------
# LIST TEACHERS IN BATCH
# --------------------------------------------------

@router.get(
    "/batch/{batch_id}",
    response_model=list[BatchTeacherResponse]
)
def get_batch_teachers(
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

    return (
        db.query(BatchTeacher)
        .filter(
            BatchTeacher.batch_id == batch_id,
            BatchTeacher.is_active == True
        )
        .all()
    )


# --------------------------------------------------
# GET TEACHER'S BATCHES
# --------------------------------------------------

@router.get(
    "/teacher/{teacher_id}",
    response_model=list[BatchTeacherResponse]
)
def get_teacher_batches(
    teacher_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    teacher = (
        db.query(User)
        .filter(User.id == teacher_id)
        .first()
    )

    if not teacher:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Teachers can only see their own batch assignments
    if (
        current_user.role == "teacher"
        and current_user.id != teacher_id
    ):

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another teacher's batches"
        )

    return (
        db.query(BatchTeacher)
        .filter(
            BatchTeacher.user_id == teacher_id,
            BatchTeacher.is_active == True
        )
        .all()
    )


# --------------------------------------------------
# DEACTIVATE ASSIGNMENT
# --------------------------------------------------

@router.put(
    "/{assignment_id}/deactivate",
    response_model=BatchTeacherResponse
)
def deactivate_assignment(
    assignment_id: int,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    assignment = (
        db.query(BatchTeacher)
        .filter(BatchTeacher.id == assignment_id)
        .first()
    )

    if not assignment:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    assignment.is_active = False

    db.commit()
    db.refresh(assignment)

    return assignment


# --------------------------------------------------
# ACTIVATE ASSIGNMENT
# --------------------------------------------------

@router.put(
    "/{assignment_id}/activate",
    response_model=BatchTeacherResponse
)
def activate_assignment(
    assignment_id: int,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    assignment = (
        db.query(BatchTeacher)
        .filter(BatchTeacher.id == assignment_id)
        .first()
    )

    if not assignment:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    assignment.is_active = True

    db.commit()
    db.refresh(assignment)

    return assignment


# --------------------------------------------------
# REMOVE ASSIGNMENT
# --------------------------------------------------

@router.delete(
    "/{assignment_id}"
)
def remove_assignment(
    assignment_id: int,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    assignment = (
        db.query(BatchTeacher)
        .filter(BatchTeacher.id == assignment_id)
        .first()
    )

    if not assignment:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    db.delete(assignment)
    db.commit()

    return {
        "message": "Teacher removed from batch successfully"
    }
