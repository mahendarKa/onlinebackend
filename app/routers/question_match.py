from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_match import QuestionMatch
from app.schemas.question_match import (
    QuestionMatchItemCreate,
    QuestionMatchItemUpdate,
    QuestionMatchResponse,
    QuestionMatchBulkCreate
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Match"]
)


def get_match_question(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    if question.type != "match":
        raise HTTPException(
            status_code=400,
            detail="This question is not a match question"
        )

    return question


# CREATE ONE MATCH ITEM

@router.post(
    "/{question_id}/match",
    response_model=QuestionMatchResponse,
    status_code=status.HTTP_201_CREATED
)
def create_match_item(
    question_id: int,
    data: QuestionMatchItemCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_match_question(question_id, db)

    item = QuestionMatch(
        question_id=question_id,
        sub_question=data.sub_question,
        sub_answer=data.sub_answer,
        sort_order=data.sort_order
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# BULK CREATE MATCH ITEMS

@router.post(
    "/{question_id}/match/bulk",
    response_model=list[QuestionMatchResponse],
    status_code=status.HTTP_201_CREATED
)
def bulk_create_match_items(
    question_id: int,
    data: QuestionMatchBulkCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_match_question(question_id, db)

    items = [
        QuestionMatch(
            question_id=question_id,
            sub_question=item.sub_question,
            sub_answer=item.sub_answer,
            sort_order=item.sort_order
        )
        for item in data.items
    ]

    try:
        db.add_all(items)
        db.commit()

        for item in items:
            db.refresh(item)

        return items

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save match items"
        )


# GET ALL MATCH ITEMS

@router.get(
    "/{question_id}/match",
    response_model=list[QuestionMatchResponse]
)
def get_match_items(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):
    get_match_question(question_id, db)

    return (
        db.query(QuestionMatch)
        .filter(QuestionMatch.question_id == question_id)
        .order_by(QuestionMatch.sort_order, QuestionMatch.id)
        .all()
    )


# UPDATE MATCH ITEM

@router.put(
    "/{question_id}/match/{item_id}",
    response_model=QuestionMatchResponse
)
def update_match_item(
    question_id: int,
    item_id: int,
    data: QuestionMatchItemUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_match_question(question_id, db)

    item = db.query(QuestionMatch).filter(
        QuestionMatch.id == item_id,
        QuestionMatch.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Match item not found"
        )

    if data.sub_question is not None:
        item.sub_question = data.sub_question

    if data.sub_answer is not None:
        item.sub_answer = data.sub_answer

    if data.sort_order is not None:
        item.sort_order = data.sort_order

    db.commit()
    db.refresh(item)

    return item


# DELETE MATCH ITEM

@router.delete("/{question_id}/match/{item_id}")
def delete_match_item(
    question_id: int,
    item_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_match_question(question_id, db)

    item = db.query(QuestionMatch).filter(
        QuestionMatch.id == item_id,
        QuestionMatch.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Match item not found"
        )

    db.delete(item)
    db.commit()

    return {"message": "Match item deleted successfully"}