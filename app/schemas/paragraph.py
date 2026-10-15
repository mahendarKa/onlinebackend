from pydantic import BaseModel, Field


class ParagraphPassageCreate(BaseModel):
    content: str = Field(min_length=1)


class ParagraphPassageUpdate(BaseModel):
    content: str = Field(min_length=1)


class ParagraphPassageResponse(BaseModel):
    id: int
    content: str
    created_by: int

    class Config:
        from_attributes = True


class ParagraphQuestionLinkCreate(BaseModel):
    question_id: int
    sort_order: int = 0


class ParagraphQuestionLinkResponse(BaseModel):
    id: int
    passage_id: int
    question_id: int
    sort_order: int

    class Config:
        from_attributes = True


class QuestionParagraphLinkSet(BaseModel):
    """Child question ids shown under a paragraph-type question."""
    question_ids: list[int] = Field(min_length=1)