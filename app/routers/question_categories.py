from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question_category import QuestionCategory
from app.models.user import User

from app.schemas.question_category import (
    QuestionCategoryCreate,
    QuestionCategoryUpdate,
    QuestionCategoryResponse
)

from app.utils.dependencies import (
    get_current_user,
    require_role
)


router = APIRouter(
    prefix="/api/question-categories",
    tags=["Question Categories"]
)


# --------------------------------------------------
# CREATE CATEGORY
# --------------------------------------------------

@router.post(
    "/",
    response_model=QuestionCategoryResponse,
    status_code=status.HTTP_201_CREATED
)
def create_category(
    category_data: QuestionCategoryCreate,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):

    # Check parent category
    if category_data.parent_id is not None:

        parent = (
            db.query(QuestionCategory)
            .filter(
                QuestionCategory.id ==
                category_data.parent_id
            )
            .first()
        )

        if not parent:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found"
            )

    category = QuestionCategory(
        name=category_data.name,
        parent_id=category_data.parent_id,
        description=category_data.description,
        created_by=current_user.id
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


# --------------------------------------------------
# GET ALL CATEGORIES
# --------------------------------------------------

@router.get(
    "/",
    response_model=list[QuestionCategoryResponse]
)
def get_categories(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    return db.query(QuestionCategory).all()


# --------------------------------------------------
# GET CATEGORY
# --------------------------------------------------

@router.get(
    "/{category_id}",
    response_model=QuestionCategoryResponse
)
def get_category(
    category_id: int,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db)
):

    category = (
        db.query(QuestionCategory)
        .filter(
            QuestionCategory.id == category_id
        )
        .first()
    )

    if not category:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    return category


# --------------------------------------------------
# UPDATE CATEGORY
# --------------------------------------------------

@router.put(
    "/{category_id}",
    response_model=QuestionCategoryResponse
)
def update_category(
    category_id: int,
    category_data: QuestionCategoryUpdate,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):

    category = (
        db.query(QuestionCategory)
        .filter(
            QuestionCategory.id == category_id
        )
        .first()
    )

    if not category:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    if category_data.name is not None:
        category.name = category_data.name

    if category_data.description is not None:
        category.description = category_data.description

    if category_data.parent_id is not None:

        parent = (
            db.query(QuestionCategory)
            .filter(
                QuestionCategory.id ==
                category_data.parent_id
            )
            .first()
        )

        if not parent:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found"
            )

        if parent.id == category_id:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category cannot be its own parent"
            )

        category.parent_id = category_data.parent_id

    db.commit()
    db.refresh(category)

    return category


# --------------------------------------------------
# DELETE CATEGORY
# --------------------------------------------------

@router.delete(
    "/{category_id}"
)
def delete_category(
    category_id: int,
    current_user: User = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db)
):

    category = (
        db.query(QuestionCategory)
        .filter(
            QuestionCategory.id == category_id
        )
        .first()
    )

    if not category:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    db.delete(category)
    db.commit()

    return {
        "message": "Question category deleted successfully"
    }