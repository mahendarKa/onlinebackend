from pydantic import BaseModel, Field


class QuestionMatchItemCreate(BaseModel):
    sub_question: str
    sub_answer: str
    sort_order: int = 0


class QuestionMatchItemUpdate(BaseModel):
    sub_question: str | None = None
    sub_answer: str | None = None
    sort_order: int | None = None


class QuestionMatchResponse(BaseModel):
    id: int
    question_id: int
    sub_question: str
    sub_answer: str
    sort_order: int

    class Config:
        from_attributes = True


class QuestionMatchBulkCreate(BaseModel):
    items: list[QuestionMatchItemCreate] = Field(min_length=2)