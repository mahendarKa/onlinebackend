
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ManualEvaluationRequest(BaseModel):
    marks_obtained: Decimal = Field(ge=0)
    is_correct: Optional[bool] = None


class EvaluationResponse(BaseModel):
    answer_id: int
    question_id: int
    marks_obtained: Decimal
    is_correct: Optional[bool]


class ExamResultResponse(BaseModel):
    id: int
    exam_attempt_id: int
    total_questions: int
    attempted: int
    correct: int
    wrong: int
    skipped: int
    total_marks: Decimal
    percentage: Decimal
    pass_fail: str

    model_config = ConfigDict(from_attributes=True)
