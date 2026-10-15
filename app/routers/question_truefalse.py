from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_truefalse import QuestionTrueFalse
from app.schemas.question_truefalse import (
    QuestionTrueFalseCreate,
    QuestionTrueFalseUpdate,
    QuestionTrueFalseResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question True/False"]
)


def get_truefalse_question(question_id: int, db: Session):

    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.type != "truefalse":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question is not a true/false question"
        )

    return question


# ---------------------------------------------------------
# CREATE TRUE/FALSE ANSWER
# ---------------------------------------------------------

@router.post(
    "/{question_id}/truefalse",
    response_model=QuestionTrueFalseResponse,
    status_code=status.HTTP_201_CREATED
)
def create_truefalse(
    question_id: int,
    data: QuestionTrueFalseCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_truefalse_question(question_id, db)

    existing = db.query(QuestionTrueFalse).filter(
        QuestionTrueFalse.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="True/False answer already exists for this question"
        )

    true_answer = data.true_answer
    false_answer = not true_answer

    truefalse = QuestionTrueFalse(
        question_id=question_id,
        true_answer=true_answer,
        false_answer=false_answer
    )

    db.add(truefalse)
    db.commit()
    db.refresh(truefalse)

    return truefalse


# ---------------------------------------------------------
# GET TRUE/FALSE ANSWER
# ---------------------------------------------------------

@router.get(
    "/{question_id}/truefalse",
    response_model=QuestionTrueFalseResponse
)
def get_truefalse(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):

    get_truefalse_question(question_id, db)

    truefalse = db.query(QuestionTrueFalse).filter(
        QuestionTrueFalse.question_id == question_id
    ).first()

    if not truefalse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="True/False answer not configured"
        )

    return truefalse


# ---------------------------------------------------------
# UPDATE TRUE/FALSE ANSWER
# ---------------------------------------------------------

@router.put(
    "/{question_id}/truefalse",
    response_model=QuestionTrueFalseResponse
)
def update_truefalse(
    question_id: int,
    data: QuestionTrueFalseUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_truefalse_question(question_id, db)

    truefalse = db.query(QuestionTrueFalse).filter(
        QuestionTrueFalse.question_id == question_id
    ).first()

    if not truefalse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="True/False answer not configured"
        )

    truefalse.true_answer = data.true_answer
    truefalse.false_answer = not data.true_answer

    db.commit()
    db.refresh(truefalse)

    return truefalse


# ---------------------------------------------------------
# DELETE TRUE/FALSE ANSWER
# ---------------------------------------------------------

@router.delete(
    "/{question_id}/truefalse"
)
def delete_truefalse(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_truefalse_question(question_id, db)

    truefalse = db.query(QuestionTrueFalse).filter(
        QuestionTrueFalse.question_id == question_id
    ).first()

    if not truefalse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="True/False answer not configured"
        )

    db.delete(truefalse)
    db.commit()

    return {
        "message": "True/False answer deleted successfully"
    }