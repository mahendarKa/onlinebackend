from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_multianswer import QuestionMultiAnswer
from app.schemas.question_multianswer import (
    QuestionMultiAnswerCreate,
    QuestionMultiAnswerUpdate,
    QuestionMultiAnswerResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Multi-answer"]
)


def get_multianswer_question(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    if question.type != "multianswer":
        raise HTTPException(
            status_code=400,
            detail="This question is not a multi-answer question"
        )

    return question


# CREATE

@router.post(
    "/{question_id}/multianswer",
    response_model=QuestionMultiAnswerResponse,
    status_code=status.HTTP_201_CREATED
)
def create_multianswer(
    question_id: int,
    data: QuestionMultiAnswerCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_multianswer_question(question_id, db)

    existing = db.query(QuestionMultiAnswer).filter(
        QuestionMultiAnswer.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Multi-answer configuration already exists"
        )

    item = QuestionMultiAnswer(
        question_id=question_id,
        answer_text=data.answer_text,
        answer_format=data.answer_format
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# GET

@router.get(
    "/{question_id}/multianswer",
    response_model=QuestionMultiAnswerResponse
)
def get_multianswer(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_multianswer_question(question_id, db)

    item = db.query(QuestionMultiAnswer).filter(
        QuestionMultiAnswer.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Multi-answer configuration not found"
        )

    return item


# UPDATE

@router.put(
    "/{question_id}/multianswer",
    response_model=QuestionMultiAnswerResponse
)
def update_multianswer(
    question_id: int,
    data: QuestionMultiAnswerUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_multianswer_question(question_id, db)

    item = db.query(QuestionMultiAnswer).filter(
        QuestionMultiAnswer.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Multi-answer configuration not found"
        )

    if data.answer_text is not None:
        item.answer_text = data.answer_text

    if data.answer_format is not None:
        item.answer_format = data.answer_format

    db.commit()
    db.refresh(item)

    return item


# DELETE

@router.delete("/{question_id}/multianswer")
def delete_multianswer(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_multianswer_question(question_id, db)

    item = db.query(QuestionMultiAnswer).filter(
        QuestionMultiAnswer.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Multi-answer configuration not found"
        )

    db.delete(item)
    db.commit()

    return {"message": "Multi-answer configuration deleted successfully"}