from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.question import Question
from app.models.question_image import QuestionImage
from app.schemas.question_image import (
    QuestionImageCreate,
    QuestionImageUpdate,
    QuestionImageResponse
)
from app.utils.dependencies import require_role


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Images"]
)


def get_image_question(question_id: int, db: Session):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    if question.type != "image":
        raise HTTPException(
            status_code=400,
            detail="This question is not an image question"
        )

    return question


# CREATE IMAGE

@router.post(
    "/{question_id}/images",
    response_model=QuestionImageResponse,
    status_code=status.HTTP_201_CREATED
)
def create_image(
    question_id: int,
    data: QuestionImageCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_image_question(question_id, db)

    image = QuestionImage(
        question_id=question_id,
        image_url=str(data.image_url),
        alt_text=data.alt_text,
        position=data.position
    )

    db.add(image)
    db.commit()
    db.refresh(image)

    return image


# GET ALL IMAGES

@router.get(
    "/{question_id}/images",
    response_model=list[QuestionImageResponse]
)
def get_images(
    question_id: int,
    current_user=Depends(
        require_role("admin", "teacher", "student")
    ),
    db: Session = Depends(get_db)
):
    get_image_question(question_id, db)

    return (
        db.query(QuestionImage)
        .filter(QuestionImage.question_id == question_id)
        .order_by(QuestionImage.position, QuestionImage.id)
        .all()
    )


# UPDATE IMAGE

@router.put(
    "/{question_id}/images/{image_id}",
    response_model=QuestionImageResponse
)
def update_image(
    question_id: int,
    image_id: int,
    data: QuestionImageUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_image_question(question_id, db)

    image = db.query(QuestionImage).filter(
        QuestionImage.id == image_id,
        QuestionImage.question_id == question_id
    ).first()

    if not image:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    if data.image_url is not None:
        image.image_url = str(data.image_url)

    if data.alt_text is not None:
        image.alt_text = data.alt_text

    if data.position is not None:
        image.position = data.position

    db.commit()
    db.refresh(image)

    return image


# DELETE IMAGE

@router.delete("/{question_id}/images/{image_id}")
def delete_image(
    question_id: int,
    image_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    get_image_question(question_id, db)

    image = db.query(QuestionImage).filter(
        QuestionImage.id == image_id,
        QuestionImage.question_id == question_id
    ).first()

    if not image:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    db.delete(image)
    db.commit()

    return {"message": "Question image deleted successfully"}