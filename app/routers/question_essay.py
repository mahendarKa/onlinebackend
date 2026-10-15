from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_essay import QuestionEssay
from app.schemas.question_essay import (
    QuestionEssayCreate,
    QuestionEssayUpdate,
    QuestionEssayResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Essay"]
)


def get_essay_question(question_id: int, db: Session):

    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.type != "essay":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question is not an essay question"
        )

    return question


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------

@router.post(
    "/{question_id}/essay",
    response_model=QuestionEssayResponse,
    status_code=status.HTTP_201_CREATED
)
def create_essay(
    question_id: int,
    data: QuestionEssayCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_essay_question(question_id, db)

    existing = db.query(QuestionEssay).filter(
        QuestionEssay.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Essay configuration already exists for this question"
        )

    essay = QuestionEssay(
        question_id=question_id,
        response_format=data.response_format,
        max_words=data.max_words
    )

    db.add(essay)
    db.commit()
    db.refresh(essay)

    return essay


# ---------------------------------------------------------
# GET
# ---------------------------------------------------------

@router.get(
    "/{question_id}/essay",
    response_model=QuestionEssayResponse
)
def get_essay(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):

    get_essay_question(question_id, db)

    essay = db.query(QuestionEssay).filter(
        QuestionEssay.question_id == question_id
    ).first()

    if not essay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Essay configuration is not available"
        )

    return essay


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------

@router.put(
    "/{question_id}/essay",
    response_model=QuestionEssayResponse
)
def update_essay(
    question_id: int,
    data: QuestionEssayUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_essay_question(question_id, db)

    essay = db.query(QuestionEssay).filter(
        QuestionEssay.question_id == question_id
    ).first()

    if not essay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Essay configuration is not available"
        )

    if data.response_format is not None:
        essay.response_format = data.response_format

    if data.max_words is not None:
        essay.max_words = data.max_words

    db.commit()
    db.refresh(essay)

    return essay


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete(
    "/{question_id}/essay"
)
def delete_essay(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_essay_question(question_id, db)

    essay = db.query(QuestionEssay).filter(
        QuestionEssay.question_id == question_id
    ).first()

    if not essay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Essay configuration is not available"
        )

    db.delete(essay)
    db.commit()

    return {
        "message": "Essay configuration deleted successfully"
    }