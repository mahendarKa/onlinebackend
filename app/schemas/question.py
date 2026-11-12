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
    # Computed flags set by the list/detail endpoints.
    has_pending_change: bool = False
    in_attempted_exam: bool = False
    # Set when a teacher's PUT was converted into an approval request
    # instead of being applied immediately.
    pending_request: bool = False

    class Config:
        from_attributes = True


class QuestionChangeRequestCreate(BaseModel):
    """A teacher-submitted edit or delete queued for admin approval."""

    action: str  # update | delete
    payload: dict | None = None