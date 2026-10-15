from pydantic import BaseModel, Field


class QuestionDescriptionCreate(BaseModel):
    content: str = Field(min_length=1)


class QuestionDescriptionUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)


class QuestionDescriptionResponse(BaseModel):
    id: int
    question_id: int
    content: str

    class Config:
        from_attributes = True