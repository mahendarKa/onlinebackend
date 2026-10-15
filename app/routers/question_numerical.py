from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_numerical import QuestionNumerical
from app.schemas.question_numerical import (
    QuestionNumericalCreate,
    QuestionNumericalUpdate,
    QuestionNumericalResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Numerical"]
)


def get_numerical_question(question_id: int, db: Session):

    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.type != "numerical":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question is not a numerical question"
        )

    return question


def validate_numerical_data(answer_value: Decimal, tolerance: Decimal):

    if tolerance < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tolerance cannot be negative"
        )


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------

@router.post(
    "/{question_id}/numerical",
    response_model=QuestionNumericalResponse,
    status_code=status.HTTP_201_CREATED
)
def create_numerical(
    question_id: int,
    data: QuestionNumericalCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_numerical_question(question_id, db)

    validate_numerical_data(
        data.answer_value,
        data.tolerance
    )

    existing = db.query(QuestionNumerical).filter(
        QuestionNumerical.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Numerical answer already exists for this question"
        )

    numerical = QuestionNumerical(
        question_id=question_id,
        answer_value=data.answer_value,
        tolerance=data.tolerance
    )

    db.add(numerical)
    db.commit()
    db.refresh(numerical)

    return numerical


# ---------------------------------------------------------
# GET
# ---------------------------------------------------------

@router.get(
    "/{question_id}/numerical",
    response_model=QuestionNumericalResponse
)
def get_numerical(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):

    get_numerical_question(question_id, db)

    numerical = db.query(QuestionNumerical).filter(
        QuestionNumerical.question_id == question_id
    ).first()

    if not numerical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Numerical answer is not configured"
        )

    return numerical


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------

@router.put(
    "/{question_id}/numerical",
    response_model=QuestionNumericalResponse
)
def update_numerical(
    question_id: int,
    data: QuestionNumericalUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_numerical_question(question_id, db)

    numerical = db.query(QuestionNumerical).filter(
        QuestionNumerical.question_id == question_id
    ).first()

    if not numerical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Numerical answer is not configured"
        )

    if data.answer_value is not None:
        numerical.answer_value = data.answer_value

    if data.tolerance is not None:

        if data.tolerance < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tolerance cannot be negative"
            )

        numerical.tolerance = data.tolerance

    db.commit()
    db.refresh(numerical)

    return numerical


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete(
    "/{question_id}/numerical"
)
def delete_numerical(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_numerical_question(question_id, db)

    numerical = db.query(QuestionNumerical).filter(
        QuestionNumerical.question_id == question_id
    ).first()

    if not numerical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Numerical answer is not configured"
        )

    db.delete(numerical)
    db.commit()

    return {
        "message": "Numerical answer deleted successfully"
    }