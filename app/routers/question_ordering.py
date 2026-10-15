from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_ordering import QuestionOrdering
from app.schemas.question_ordering import (
    OrderingItemCreate,
    OrderingItemUpdate,
    OrderingItemResponse,
    OrderingBulkCreate,
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Ordering"],
)


def get_ordering_question(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    if question.type != "ordering":
        raise HTTPException(
            status_code=400,
            detail="This question is not an ordering question"
        )

    return question


# CREATE ONE ITEM

@router.post(
    "/{question_id}/ordering",
    response_model=OrderingItemResponse,
    status_code=status.HTTP_201_CREATED
)
def create_ordering_item(
    question_id: int,
    data: OrderingItemCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_ordering_question(question_id, db)

    item = QuestionOrdering(
        question_id=question_id,
        item_text=data.item_text,
        position=data.position,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# BULK CREATE ALL ITEMS (positions must be unique)

@router.post(
    "/{question_id}/ordering/bulk",
    response_model=list[OrderingItemResponse],
    status_code=status.HTTP_201_CREATED
)
def bulk_create_ordering_items(
    question_id: int,
    data: OrderingBulkCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_ordering_question(question_id, db)

    positions = [item.position for item in data.items]
    if len(set(positions)) != len(positions):
        raise HTTPException(
            status_code=400,
            detail="Ordering positions must be unique"
        )

    rows = [
        QuestionOrdering(
            question_id=question_id,
            item_text=item.item_text,
            position=item.position,
        )
        for item in data.items
    ]

    try:
        db.add_all(rows)
        db.commit()

        for row in rows:
            db.refresh(row)

        return rows

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save ordering items"
        )


# GET ALL ITEMS (correct order — teachers; students get the
# shuffled version through the attempt questions endpoint)

@router.get(
    "/{question_id}/ordering",
    response_model=list[OrderingItemResponse]
)
def get_ordering_items(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):
    get_ordering_question(question_id, db)

    return (
        db.query(QuestionOrdering)
        .filter(QuestionOrdering.question_id == question_id)
        .order_by(QuestionOrdering.position, QuestionOrdering.id)
        .all()
    )


# UPDATE ITEM

@router.put(
    "/{question_id}/ordering/{item_id}",
    response_model=OrderingItemResponse
)
def update_ordering_item(
    question_id: int,
    item_id: int,
    data: OrderingItemUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_ordering_question(question_id, db)

    item = db.query(QuestionOrdering).filter(
        QuestionOrdering.id == item_id,
        QuestionOrdering.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Ordering item not found"
        )

    if data.item_text is not None:
        item.item_text = data.item_text
    if data.position is not None:
        item.position = data.position

    db.commit()
    db.refresh(item)

    return item


# DELETE ITEM

@router.delete("/{question_id}/ordering/{item_id}")
def delete_ordering_item(
    question_id: int,
    item_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_ordering_question(question_id, db)

    item = db.query(QuestionOrdering).filter(
        QuestionOrdering.id == item_id,
        QuestionOrdering.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Ordering item not found"
        )

    db.delete(item)
    db.commit()

    return {"message": "Ordering item deleted successfully"}
