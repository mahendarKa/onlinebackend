from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_shortanswer import QuestionShortAnswer
from app.schemas.question_shortanswer import (
    QuestionShortAnswerCreate,
    QuestionShortAnswerUpdate,
    QuestionShortAnswerResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Short Answer"]
)


def get_shortanswer_question(question_id: int, db: Session):

    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.type != "shortanswer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question is not a short answer question"
        )

    return question


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------

@router.post(
    "/{question_id}/shortanswer",
    response_model=QuestionShortAnswerResponse,
    status_code=status.HTTP_201_CREATED
)
def create_shortanswer(
    question_id: int,
    data: QuestionShortAnswerCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_shortanswer_question(question_id, db)

    existing = db.query(QuestionShortAnswer).filter(
        QuestionShortAnswer.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Short answer already exists for this question"
        )

    answer = QuestionShortAnswer(
        question_id=question_id,
        answer_text=data.answer_text,
        case_sensitive=data.case_sensitive
    )

    db.add(answer)
    db.commit()
    db.refresh(answer)

    return answer


# ---------------------------------------------------------
# GET
# ---------------------------------------------------------

@router.get(
    "/{question_id}/shortanswer",
    response_model=QuestionShortAnswerResponse
)
def get_shortanswer(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):

    get_shortanswer_question(question_id, db)

    answer = db.query(QuestionShortAnswer).filter(
        QuestionShortAnswer.question_id == question_id
    ).first()

    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short answer is not configured"
        )

    return answer


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------

@router.put(
    "/{question_id}/shortanswer",
    response_model=QuestionShortAnswerResponse
)
def update_shortanswer(
    question_id: int,
    data: QuestionShortAnswerUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_shortanswer_question(question_id, db)

    answer = db.query(QuestionShortAnswer).filter(
        QuestionShortAnswer.question_id == question_id
    ).first()

    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short answer is not configured"
        )

    if data.answer_text is not None:
        answer.answer_text = data.answer_text

    if data.case_sensitive is not None:
        answer.case_sensitive = data.case_sensitive

    db.commit()
    db.refresh(answer)

    return answer


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete(
    "/{question_id}/shortanswer"
)
def delete_shortanswer(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):

    get_shortanswer_question(question_id, db)

    answer = db.query(QuestionShortAnswer).filter(
        QuestionShortAnswer.question_id == question_id
    ).first()

    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short answer is not configured"
        )

    db.delete(answer)
    db.commit()

    return {
        "message": "Short answer deleted successfully"
    }