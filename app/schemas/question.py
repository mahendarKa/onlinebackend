from decimal import Decimal

from pydantic import BaseModel


class QuestionCreate(BaseModel):

    category_id: int
    type: str
    name: str
    question_text: str
    default_mark: Decimal
    general_feedback: str | None = None


class QuestionUpdate(BaseModel):

    category_id: int | None = None
    type: str | None = None
    name: str | None = None
    question_text: str | None = None
    default_mark: Decimal | None = None
    general_feedback: str | None = None
    is_active: bool | None = None


class QuestionResponse(BaseModel):

    id: int
    category_id: int
    type: str
    name: str
    question_text: str
    default_mark: Decimal
    general_feedback: str | None
    created_by: int
    creator_name: str | None = None
    is_active: bool

    class Config:
        from_attributes = True