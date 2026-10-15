import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_category import QuestionCategory
from app.schemas.question_random import (
    RandomQuestionRequest,
    RandomQuestionResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Random Questions"]
)


@router.post(
    "/random/select",
    response_model=RandomQuestionResponse
)
def select_random_questions(
    data: RandomQuestionRequest,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    category = db.query(QuestionCategory).filter(
        QuestionCategory.id == data.category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Question category not found"
        )

    questions = db.query(Question).filter(
        Question.category_id == data.category_id,
        Question.is_active == True,
        Question.type != "random",
        Question.type != "description"
    ).all()

    if len(questions) < data.count:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested {data.count} questions, "
                f"but only {len(questions)} are available"
            )
        )

    selected = random.sample(questions, data.count)

    return {
        "category_id": data.category_id,
        "requested_count": data.count,
        "selected_count": len(selected),
        "question_ids": [question.id for question in selected]
    }