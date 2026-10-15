
from decimal import Decimal
from pydantic import BaseModel, Field


class ImportedQuestion(BaseModel):
    category_id: int = Field(gt=0)
    type: str
    name: str = Field(min_length=1, max_length=255)
    question_text: str = Field(min_length=1)
    default_mark: Decimal = Field(gt=0)
    general_feedback: str | None = None


class BulkQuestionImportRequest(BaseModel):
    questions: list[ImportedQuestion] = Field(min_length=1, max_length=500)


class BulkQuestionImportResponse(BaseModel):
    imported_count: int
    failed_count: int
    errors: list[dict]
    imported_question_ids: list[int]
