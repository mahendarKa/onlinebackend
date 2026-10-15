from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_calculated import QuestionCalculated
from app.schemas.question_calculated import (
    QuestionCalculatedCreate,
    QuestionCalculatedUpdate,
    QuestionCalculatedResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Calculated"]
)


def get_calculated_question(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    allowed_types = [
        "calculated",
        "calculatedsimple",
        "calculatedmulti"
    ]

    if question.type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="This is not a calculated question"
        )

    return question


# CREATE

@router.post(
    "/{question_id}/calculated-config",
    response_model=QuestionCalculatedResponse,
    status_code=status.HTTP_201_CREATED
)
def create_calculated(
    question_id: int,
    data: QuestionCalculatedCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_calculated_question(question_id, db)

    existing = db.query(QuestionCalculated).filter(
        QuestionCalculated.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Calculated configuration already exists"
        )

    names = [d.name for d in data.datasets]
    if len(names) != len(set(names)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate wildcard name in datasets"
        )
    for d in data.datasets:
        if d.min_value > d.max_value:
            raise HTTPException(
                status_code=400,
                detail=f"Wildcard '{d.name}': min exceeds max"
            )

    calculated = QuestionCalculated(
        question_id=question_id,
        formula=data.formula,
        tolerance=data.tolerance,
        units=data.units,
        datasets=[d.model_dump(mode="json") for d in data.datasets]
        or None,
    )

    db.add(calculated)
    db.commit()
    db.refresh(calculated)

    return calculated


# GET

@router.get(
    "/{question_id}/calculated-config",
    response_model=QuestionCalculatedResponse
)
def get_calculated(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_calculated_question(question_id, db)

    calculated = db.query(QuestionCalculated).filter(
        QuestionCalculated.question_id == question_id
    ).first()

    if not calculated:
        raise HTTPException(
            status_code=404,
            detail="Calculated configuration not found"
        )

    return calculated


# UPDATE

@router.put(
    "/{question_id}/calculated-config",
    response_model=QuestionCalculatedResponse
)
def update_calculated(
    question_id: int,
    data: QuestionCalculatedUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_calculated_question(question_id, db)

    calculated = db.query(QuestionCalculated).filter(
        QuestionCalculated.question_id == question_id
    ).first()

    if not calculated:
        raise HTTPException(
            status_code=404,
            detail="Calculated configuration not found"
        )

    if data.formula is not None:
        calculated.formula = data.formula

    if data.tolerance is not None:
        calculated.tolerance = data.tolerance

    if data.units is not None:
        calculated.units = data.units

    if data.datasets is not None:
        names = [d.name for d in data.datasets]
        if len(names) != len(set(names)):
            raise HTTPException(
                status_code=400,
                detail="Duplicate wildcard name in datasets"
            )
        for d in data.datasets:
            if d.min_value > d.max_value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Wildcard '{d.name}': min exceeds max"
                )
        calculated.datasets = [
            d.model_dump(mode="json") for d in data.datasets
        ] or None

    db.commit()
    db.refresh(calculated)

    return calculated


# DELETE

@router.delete("/{question_id}/calculated-config")
def delete_calculated(
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_calculated_question(question_id, db)

    calculated = db.query(QuestionCalculated).filter(
        QuestionCalculated.question_id == question_id
    ).first()

    if not calculated:
        raise HTTPException(
            status_code=404,
            detail="Calculated configuration not found"
        )

    db.delete(calculated)
    db.commit()

    return {"message": "Calculated configuration deleted successfully"}