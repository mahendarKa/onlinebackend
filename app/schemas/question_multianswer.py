from pydantic import BaseModel, Field


class QuestionMultiAnswerCreate(BaseModel):
    answer_text: str = Field(min_length=1)
    answer_format: str = "text"


class QuestionMultiAnswerUpdate(BaseModel):
    answer_text: str | None = Field(default=None, min_length=1)
    answer_format: str | None = None


class QuestionMultiAnswerResponse(BaseModel):
    id: int
    question_id: int
    answer_text: str
    answer_format: str

    class Config:
        from_attributes = True