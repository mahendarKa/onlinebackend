from decimal import Decimal
from pydantic import BaseModel, Field


class QuestionNumericalCreate(BaseModel):
    answer_value: Decimal
    tolerance: Decimal = Field(default=Decimal("0"))


class QuestionNumericalUpdate(BaseModel):
    answer_value: Decimal | None = None
    tolerance: Decimal | None = None


class QuestionNumericalResponse(BaseModel):
    id: int
    question_id: int
    answer_value: Decimal
    tolerance: Decimal

    class Config:
        from_attributes = True