from pydantic import BaseModel


class QuestionCategoryCreate(BaseModel):

    name: str
    parent_id: int | None = None
    description: str | None = None


class QuestionCategoryUpdate(BaseModel):

    name: str | None = None
    parent_id: int | None = None
    description: str | None = None


class QuestionCategoryResponse(BaseModel):

    id: int
    name: str
    parent_id: int | None
    description: str | None
    created_by: int

    class Config:
        from_attributes = True