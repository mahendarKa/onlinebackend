from datetime import datetime

from pydantic import BaseModel, Field


class ExamFeedbackCreate(BaseModel):
    attempt_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comments: str | None = Field(default=None, max_length=5000)


class ExamFeedbackResponse(BaseModel):
    id: int
    exam_id: int
    attempt_id: int
    student_id: int
    rating: int
    comments: str | None
    created_at: datetime

    model_config = {"from_attributes": True}