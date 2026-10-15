from pydantic import BaseModel, Field


class RandomQuestionRequest(BaseModel):
    category_id: int
    count: int = Field(gt=0, le=100)


class RandomQuestionResponse(BaseModel):
    category_id: int
    requested_count: int
    selected_count: int
    question_ids: list[int]