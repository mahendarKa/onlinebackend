from pydantic import BaseModel, Field


class QuestionEssayCreate(BaseModel):
    response_format: str = "plain"
    max_words: int | None = Field(default=None, ge=1)


class QuestionEssayUpdate(BaseModel):
    response_format: str | None = None
    max_words: int | None = Field(default=None, ge=1)


class QuestionEssayResponse(BaseModel):
    id: int
    question_id: int
    response_format: str
    max_words: int | None

    class Config:
        from_attributes = True