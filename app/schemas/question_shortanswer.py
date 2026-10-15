from pydantic import BaseModel


class QuestionShortAnswerCreate(BaseModel):
    answer_text: str
    case_sensitive: bool = False


class QuestionShortAnswerUpdate(BaseModel):
    answer_text: str | None = None
    case_sensitive: bool | None = None


class QuestionShortAnswerResponse(BaseModel):
    id: int
    question_id: int
    answer_text: str
    case_sensitive: bool

    class Config:
        from_attributes = True