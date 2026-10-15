from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.schemas.question_option import (
    QuestionOptionCreate,
    QuestionOptionUpdate,
    QuestionOptionResponse,
    QuestionOptionBulkCreate
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Options"]
)


ALLOWED_OPTION_TYPES = ["multichoice", "multiselect", "image"]


def get_question_or_404(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.type not in ALLOWED_OPTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Options are only supported for multichoice, multiselect and image questions"
        )

    return question


# ---------------------------------------------------------
# CREATE SINGLE OPTION
# ---------------------------------------------------------

@router.post(
    "/{question_id}/options",
    response_model=QuestionOptionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_option(
    question_id: int,
    option_data: QuestionOptionCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_question_or_404(question_id, db)

    if option_data.fraction < 0 or option_data.fraction > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fraction must be between 0 and 100"
        )

    option = QuestionOption(
        question_id=question_id,
        option_text=option_data.option_text,
        image_url=option_data.image_url,
        is_correct=option_data.is_correct,
        fraction=option_data.fraction,
        sort_order=option_data.sort_order
    )

    db.add(option)
    db.commit()
    db.refresh(option)

    return option


# ---------------------------------------------------------
# GET ALL OPTIONS
# ---------------------------------------------------------

@router.get(
    "/{question_id}/options",
    response_model=list[QuestionOptionResponse]
)
def get_options(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher", "student")),
    db: Session = Depends(get_db)
):
    get_question_or_404(question_id, db)

    return (
        db.query(QuestionOption)
        .filter(QuestionOption.question_id == question_id)
        .order_by(QuestionOption.sort_order, QuestionOption.id)
        .all()
    )


# ---------------------------------------------------------
# UPDATE OPTION
# ---------------------------------------------------------

@router.put(
    "/{question_id}/options/{option_id}",
    response_model=QuestionOptionResponse
)
def update_option(
    question_id: int,
    option_id: int,
    option_data: QuestionOptionUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_question_or_404(question_id, db)

    option = db.query(QuestionOption).filter(
        QuestionOption.id == option_id,
        QuestionOption.question_id == question_id
    ).first()

    if not option:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Option not found"
        )

    if option_data.fraction is not None:
        if option_data.fraction < 0 or option_data.fraction > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fraction must be between 0 and 100"
            )
        option.fraction = option_data.fraction

    if option_data.option_text is not None:
        option.option_text = option_data.option_text

    if option_data.image_url is not None:
        option.image_url = option_data.image_url

    if option_data.is_correct is not None:
        option.is_correct = option_data.is_correct

    if option_data.sort_order is not None:
        option.sort_order = option_data.sort_order

    db.commit()
    db.refresh(option)

    return option


# ---------------------------------------------------------
# DELETE OPTION
# ---------------------------------------------------------

@router.delete(
    "/{question_id}/options/{option_id}"
)
def delete_option(
    question_id: int,
    option_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_question_or_404(question_id, db)

    option = db.query(QuestionOption).filter(
        QuestionOption.id == option_id,
        QuestionOption.question_id == question_id
    ).first()

    if not option:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Option not found"
        )

    db.delete(option)
    db.commit()

    return {
        "message": "Option deleted successfully"
    }


# ---------------------------------------------------------
# BULK CREATE OPTIONS
# ---------------------------------------------------------

@router.post(
    "/{question_id}/options/bulk",
    response_model=list[QuestionOptionResponse],
    status_code=status.HTTP_201_CREATED
)
def bulk_create_options(
    question_id: int,
    data: QuestionOptionBulkCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    question = get_question_or_404(question_id, db)

    if not data.options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one option is required"
        )

    correct_count = sum(
        1 for option in data.options
        if option.is_correct
    )

    # MCQ / image → exactly one correct answer
    if question.type in ("multichoice", "image") and correct_count != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Single-choice question must have exactly one correct option"
        )

    # Image questions allow image-only options, but each option must
    # carry either text or an image.
    if question.type == "image":
        for option_data in data.options:
            if not option_data.option_text.strip() and not option_data.image_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each option needs text or an image URL"
                )

    # Multiselect → at least one correct answer
    if question.type == "multiselect" and correct_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiselect question must have at least one correct option"
        )

    for option_data in data.options:

        if option_data.fraction < 0 or option_data.fraction > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fraction must be between 0 and 100"
            )

        option = QuestionOption(
            question_id=question_id,
            option_text=option_data.option_text,
            image_url=option_data.image_url,
            is_correct=option_data.is_correct,
            fraction=option_data.fraction,
            sort_order=option_data.sort_order
        )

        db.add(option)

    db.commit()

    return (
        db.query(QuestionOption)
        .filter(QuestionOption.question_id == question_id)
        .order_by(QuestionOption.sort_order, QuestionOption.id)
        .all()
    )