from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.course import (
    CourseCreate,
    CourseUpdate,
    CourseResponse
)
from app.utils.dependencies import (
    get_current_user,
    require_role
)


router = APIRouter(
    prefix="/api/courses",
    tags=["Courses"]
)


# --------------------------------------------------
# CREATE COURSE
# --------------------------------------------------

@router.post(
    "/",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED
)
def create_course(
    course_data: CourseCreate,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):

    existing_course = (
        db.query(Course)
        .filter(Course.code == course_data.code)
        .first()
    )

    if existing_course:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course code already exists"
        )

    course = Course(
        name=course_data.name,
        code=course_data.code,
        description=course_data.description,
        created_by=current_user.id
    )

    db.add(course)
    db.commit()
    db.refresh(course)

    return course


# --------------------------------------------------
# GET ALL COURSES
# --------------------------------------------------

@router.get(
    "/",
    response_model=list[CourseResponse]
)
def get_courses(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    courses = db.query(Course).all()
    ids = {c.created_by for c in courses if c.created_by}
    names = {
        u.id: u.name
        for u in db.query(User.id, User.name).filter(User.id.in_(ids)).all()
    } if ids else {}
    for c in courses:
        c.creator_name = names.get(c.created_by)
    return courses


# --------------------------------------------------
# GET COURSE BY ID
# --------------------------------------------------

@router.get(
    "/{course_id}",
    response_model=CourseResponse
)
def get_course(
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

    return course


# --------------------------------------------------
# UPDATE COURSE
# --------------------------------------------------

@router.put(
    "/{course_id}",
    response_model=CourseResponse
)
def update_course(
    course_id: int,
    course_data: CourseUpdate,
    current_user: User = Depends(
        require_role("admin", "teacher")
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

    if course_data.name is not None:
        course.name = course_data.name

    if course_data.code is not None:

        existing_course = (
            db.query(Course)
            .filter(
                Course.code == course_data.code,
                Course.id != course_id
            )
            .first()
        )

        if existing_course:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course code already exists"
            )

        course.code = course_data.code

    if course_data.description is not None:
        course.description = course_data.description

    db.commit()
    db.refresh(course)

    return course


# --------------------------------------------------
# DELETE COURSE
# --------------------------------------------------

@router.delete(
    "/{course_id}"
)
def delete_course(
    course_id: int,
    current_user: User = Depends(
        require_role("admin")
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

    db.delete(course)
    db.commit()

    return {
        "message": "Course deleted successfully"
    }