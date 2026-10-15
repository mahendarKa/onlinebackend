from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_gapselect import QuestionGapSelect
from app.schemas.question_gapselect import (
    GapSelectOptionCreate,
    GapSelectOptionUpdate,
    GapSelectOptionResponse,
    GapSelectBulkCreate,
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Gap Select"],
)


def get_gapselect_question(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    if question.type != "selectmissing":
        raise HTTPException(
            status_code=400,
            detail="This question is not a select-missing-word question"
        )

    return question


def validate_blanks(items):
    """Every blank needs >=2 options and exactly one correct."""
    groups = {}
    for item in items:
        groups.setdefault(item.blank_no, []).append(item)

    for blank_no, group in groups.items():
        correct = sum(1 for g in group if g.is_correct)
        if len(group) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"Blank [[{blank_no}]] needs at least 2 options"
            )
        if correct != 1:
            raise HTTPException(
                status_code=400,
                detail=f"Blank [[{blank_no}]] must have exactly "
                       "one correct option"
            )


# CREATE ONE OPTION

@router.post(
    "/{question_id}/gapselect",
    response_model=GapSelectOptionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_gap_option(
    question_id: int,
    data: GapSelectOptionCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_gapselect_question(question_id, db)

    item = QuestionGapSelect(
        question_id=question_id,
        blank_no=data.blank_no,
        option_text=data.option_text,
        is_correct=data.is_correct,
        sort_order=data.sort_order,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# BULK CREATE ALL OPTIONS (validates blank groups)

@router.post(
    "/{question_id}/gapselect/bulk",
    response_model=list[GapSelectOptionResponse],
    status_code=status.HTTP_201_CREATED
)
def bulk_create_gap_options(
    question_id: int,
    data: GapSelectBulkCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_gapselect_question(question_id, db)
    validate_blanks(data.items)

    rows = [
        QuestionGapSelect(
            question_id=question_id,
            blank_no=item.blank_no,
            option_text=item.option_text,
            is_correct=item.is_correct,
            sort_order=item.sort_order,
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
            detail="Failed to save gap options"
        )


# GET ALL OPTIONS

@router.get(
    "/{question_id}/gapselect",
    response_model=list[GapSelectOptionResponse]
)
def get_gap_options(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):
    get_gapselect_question(question_id, db)

    return (
        db.query(QuestionGapSelect)
        .filter(QuestionGapSelect.question_id == question_id)
        .order_by(
            QuestionGapSelect.blank_no,
            QuestionGapSelect.sort_order,
            QuestionGapSelect.id,
        )
        .all()
    )


# UPDATE OPTION

@router.put(
    "/{question_id}/gapselect/{item_id}",
    response_model=GapSelectOptionResponse
)
def update_gap_option(
    question_id: int,
    item_id: int,
    data: GapSelectOptionUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_gapselect_question(question_id, db)

    item = db.query(QuestionGapSelect).filter(
        QuestionGapSelect.id == item_id,
        QuestionGapSelect.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Gap option not found"
        )

    if data.blank_no is not None:
        item.blank_no = data.blank_no
    if data.option_text is not None:
        item.option_text = data.option_text
    if data.is_correct is not None:
        item.is_correct = data.is_correct
    if data.sort_order is not None:
        item.sort_order = data.sort_order

    db.commit()
    db.refresh(item)

    return item


# DELETE OPTION

@router.delete("/{question_id}/gapselect/{item_id}")
def delete_gap_option(
    question_id: int,
    item_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_gapselect_question(question_id, db)

    item = db.query(QuestionGapSelect).filter(
        QuestionGapSelect.id == item_id,
        QuestionGapSelect.question_id == question_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Gap option not found"
        )

    db.delete(item)
    db.commit()

    return {"message": "Gap option deleted successfully"}
