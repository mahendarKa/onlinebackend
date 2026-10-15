from decimal import Decimal
from pydantic import BaseModel


class QuestionOptionCreate(BaseModel):
    option_text: str
    # Optional image for image-based options.
    image_url: str | None = None
    is_correct: bool = False
    fraction: Decimal = Decimal("0.00")
    sort_order: int = 0


class QuestionOptionUpdate(BaseModel):
    option_text: str | None = None
    image_url: str | None = None
    is_correct: bool | None = None
    fraction: Decimal | None = None
    sort_order: int | None = None


class QuestionOptionResponse(BaseModel):
    id: int
    question_id: int
    option_text: str
    image_url: str | None = None
    is_correct: bool
    fraction: Decimal
    sort_order: int

    class Config:
        from_attributes = True


class QuestionOptionBulkCreate(BaseModel):
    options: list[QuestionOptionCreate]