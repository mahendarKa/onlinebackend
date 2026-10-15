
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.coding_question import CodingQuestion, CodingTestCase
from app.schemas.coding_question import (
    CodingQuestionCreate,
    CodingQuestionUpdate,
    CodingQuestionResponse,
    CodingTestCaseCreate,
    CodingTestCaseUpdate,
    CodingTestCaseResponse,
)
from app.utils.dependencies import require_role

router = APIRouter(prefix="/api/questions", tags=["Coding Questions"])

teacher_admin = Depends(require_role("admin", "teacher"))


def get_coding_question_parent(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question.type != "coding":
        raise HTTPException(
            status_code=400,
            detail="This question is not a coding question",
        )

    return question


def get_coding_config(question_id: int, db: Session):
    get_coding_question_parent(question_id, db)

    config = db.query(CodingQuestion).filter(
        CodingQuestion.question_id == question_id
    ).first()

    if not config:
        raise HTTPException(
            status_code=404,
            detail="Coding configuration not found",
        )

    return config


# CREATE CODING CONFIGURATION
@router.post(
    "/{question_id}/coding-config",
    response_model=CodingQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_coding_config(
    question_id: int,
    data: CodingQuestionCreate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    get_coding_question_parent(question_id, db)

    existing = db.query(CodingQuestion).filter(
        CodingQuestion.question_id == question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Coding configuration already exists",
        )

    config = CodingQuestion(
        question_id=question_id,
        **data.model_dump(),
    )

    db.add(config)
    db.commit()
    db.refresh(config)
    return config


# GET CODING CONFIGURATION
@router.get(
    "/{question_id}/coding-config",
    response_model=CodingQuestionResponse,
)
def get_coding_config_api(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    return get_coding_config(question_id, db)


# UPDATE CODING CONFIGURATION
@router.put(
    "/{question_id}/coding-config",
    response_model=CodingQuestionResponse,
)
def update_coding_config(
    question_id: int,
    data: CodingQuestionUpdate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    config = get_coding_config(question_id, db)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config


# DELETE CODING CONFIGURATION
@router.delete("/{question_id}/coding-config")
def delete_coding_config(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    config = get_coding_config(question_id, db)

    db.delete(config)
    db.commit()

    return {"message": "Coding configuration deleted successfully"}


# CREATE A TEST CASE
@router.post(
    "/{question_id}/coding-config/test-cases",
    response_model=CodingTestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_test_case(
    question_id: int,
    data: CodingTestCaseCreate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    config = get_coding_config(question_id, db)

    test_case = CodingTestCase(
        coding_question_id=config.id,
        **data.model_dump(),
    )

    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


# GET ALL TEST CASES - ADMIN/TEACHER ONLY
@router.get(
    "/{question_id}/coding-config/test-cases",
    response_model=list[CodingTestCaseResponse],
)
def get_test_cases(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    config = get_coding_config(question_id, db)

    return (
        db.query(CodingTestCase)
        .filter(CodingTestCase.coding_question_id == config.id)
        .order_by(CodingTestCase.sort_order, CodingTestCase.id)
        .all()
    )


# UPDATE A TEST CASE
@router.put(
    "/{question_id}/coding-config/test-cases/{test_case_id}",
    response_model=CodingTestCaseResponse,
)
def update_test_case(
    question_id: int,
    test_case_id: int,
    data: CodingTestCaseUpdate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    config = get_coding_config(question_id, db)

    test_case = db.query(CodingTestCase).filter(
        CodingTestCase.id == test_case_id,
        CodingTestCase.coding_question_id == config.id,
    ).first()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(test_case, key, value)

    db.commit()
    db.refresh(test_case)
    return test_case


# DELETE A TEST CASE
@router.delete(
    "/{question_id}/coding-config/test-cases/{test_case_id}"
)
def delete_test_case(
    question_id: int,
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    config = get_coding_config(question_id, db)

    test_case = db.query(CodingTestCase).filter(
        CodingTestCase.id == test_case_id,
        CodingTestCase.coding_question_id == config.id,
    ).first()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    db.delete(test_case)
    db.commit()

    return {"message": "Test case deleted successfully"}
