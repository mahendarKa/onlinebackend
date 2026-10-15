from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.batch import Batch
from app.models.course import Course
from app.models.user import User

from app.schemas.batch import (
    BatchCreate,
    BatchUpdate,
    BatchResponse
)

from app.utils.dependencies import (
    get_current_user,
    require_role
)
from app.utils.permissions import (
    require_batch_access,
    teacher_visible_batch_ids,
)


router = APIRouter(
    prefix="/api/batches",
    tags=["Batches"]
)


# --------------------------------------------------
# CREATE BATCH
# --------------------------------------------------

@router.post(
    "/",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED
)
def create_batch(
    batch_data: BatchCreate,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):

    # Check course exists
    course = (
        db.query(Course)
        .filter(Course.id == batch_data.course_id)
        .first()
    )

    if not course:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    # Validate dates
    if (
        batch_data.start_date
        and batch_data.end_date
        and batch_data.end_date < batch_data.start_date
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be before start date"
        )

    batch = Batch(
        course_id=batch_data.course_id,
        name=batch_data.name,
        start_date=batch_data.start_date,
        end_date=batch_data.end_date,
        description=batch_data.description,
        created_by=current_user.id
    )

    db.add(batch)
    db.commit()
    db.refresh(batch)
    attach_creator_name(batch, db)

    return batch


def attach_creator_name(batch, db: Session):
    """Expose .creator_name on the ORM row for the response schema."""
    creator = db.query(User).filter(User.id == batch.created_by).first()
    batch.creator_name = creator.name if creator else None
    return batch


# --------------------------------------------------
# GET ALL BATCHES
# --------------------------------------------------

@router.get(
    "/",
    response_model=list[BatchResponse]
)
def get_batches(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    query = db.query(Batch)
    if current_user.role == "teacher":
        visible = teacher_visible_batch_ids(db, current_user.id)
        query = query.filter(Batch.id.in_(visible or {0}))
    elif current_user.role == "student":
        # Students only need their own batches.
        from app.models.batch_student import BatchStudent
        ids = {
            r[0] for r in db.query(BatchStudent.batch_id).filter(
                BatchStudent.user_id == current_user.id,
                BatchStudent.is_active == True,  # noqa: E712
            ).all()
        }
        query = query.filter(Batch.id.in_(ids or {0}))

    batches = query.all()
    for b in batches:
        attach_creator_name(b, db)
    return batches


# --------------------------------------------------
# GET BATCH BY ID
# --------------------------------------------------

@router.get(
    "/{batch_id}",
    response_model=BatchResponse
)
def get_batch(
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

    if current_user.role in ("teacher", "student"):
        require_batch_access(current_user, batch, db)

    return attach_creator_name(batch, db)


# --------------------------------------------------
# GET BATCHES BY COURSE
# --------------------------------------------------

@router.get(
    "/course/{course_id}",
    response_model=list[BatchResponse]
)
def get_course_batches(
    course_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    course = (
        db.query(Course)
        .filter(Course.id == course_id)
        .first()
    )

    if not course:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    query = db.query(Batch).filter(Batch.course_id == course_id)
    if current_user.role == "teacher":
        visible = teacher_visible_batch_ids(db, current_user.id)
        query = query.filter(Batch.id.in_(visible or {0}))

    batches = query.all()
    for b in batches:
        attach_creator_name(b, db)
    return batches


# --------------------------------------------------
# UPDATE BATCH
# --------------------------------------------------

@router.put(
    "/{batch_id}",
    response_model=BatchResponse
)
def update_batch(
    batch_id: int,
    batch_data: BatchUpdate,
    current_user: User = Depends(
        require_role("admin", "teacher")
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

    require_batch_access(current_user, batch, db)

    # Course change
    if batch_data.course_id is not None:

        course = (
            db.query(Course)
            .filter(Course.id == batch_data.course_id)
            .first()
        )

        if not course:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        batch.course_id = batch_data.course_id

    if batch_data.name is not None:
        batch.name = batch_data.name

    if batch_data.start_date is not None:
        batch.start_date = batch_data.start_date

    if batch_data.end_date is not None:
        batch.end_date = batch_data.end_date

    if batch_data.description is not None:
        batch.description = batch_data.description

    # Validate final dates
    if (
        batch.start_date
        and batch.end_date
        and batch.end_date < batch.start_date
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be before start date"
        )

    db.commit()
    db.refresh(batch)

    return attach_creator_name(batch, db)


# --------------------------------------------------
# DELETE BATCH
# --------------------------------------------------

@router.delete(
    "/{batch_id}"
)
def delete_batch(
    batch_id: int,
    current_user: User = Depends(
        require_role("admin")
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

    db.delete(batch)
    db.commit()

    return {
        "message": "Batch deleted successfully"
    }