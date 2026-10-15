from pydantic import BaseModel


class QuestionTrueFalseCreate(BaseModel):
    true_answer: bool


class QuestionTrueFalseUpdate(BaseModel):
    true_answer: bool


class QuestionTrueFalseResponse(BaseModel):
    id: int
    question_id: int
    true_answer: bool
    false_answer: bool

    class Config:
        from_attributes = True