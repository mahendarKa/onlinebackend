from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_description import QuestionDescription
from app.schemas.question_description import (
    QuestionDescriptionCreate,
    QuestionDescriptionUpdate,
    QuestionDescriptionResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Description"]
)


def get_description_question(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    if question.type != "description":
        raise HTTPException(
            status_code=400,
            detail="This question is not a description question"
        )

    return question


# CREATE

@router.post(
    "/{question_id}/description",
    response_model=QuestionDescriptionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_description(
    question_id: int,
    data: QuestionDescriptionCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_description_question(question_id, db)

    existing = db.query(QuestionDescription).filter(
        QuestionDescription.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Description already exists for this question"
        )

    description = QuestionDescription(
        question_id=question_id,
        content=data.content
    )

    db.add(description)
    db.commit()
    db.refresh(description)

    return description


# GET

@router.get(
    "/{question_id}/description",
    response_model=QuestionDescriptionResponse
)
def get_description(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):
    get_description_question(question_id, db)

    description = db.query(QuestionDescription).filter(
        QuestionDescription.question_id == question_id
    ).first()

    if not description:
        raise HTTPException(
            status_code=404,
            detail="Description not configured"
        )

    return description


# UPDATE

@router.put(
    "/{question_id}/description",
    response_model=QuestionDescriptionResponse
)
def update_description(
    question_id: int,
    data: QuestionDescriptionUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_description_question(question_id, db)

    description = db.query(QuestionDescription).filter(
        QuestionDescription.question_id == question_id
    ).first()

    if not description:
        raise HTTPException(
            status_code=404,
            detail="Description not configured"
        )

    if data.content is not None:
        description.content = data.content

    db.commit()
    db.refresh(description)

    return description


# DELETE

@router.delete("/{question_id}/description")
def delete_description(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_description_question(question_id, db)

    description = db.query(QuestionDescription).filter(
        QuestionDescription.question_id == question_id
    ).first()

    if not description:
        raise HTTPException(
            status_code=404,
            detail="Description not configured"
        )

    db.delete(description)
    db.commit()

    return {"message": "Description deleted successfully"}