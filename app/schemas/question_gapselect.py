from pydantic import BaseModel, Field


class GapSelectOptionCreate(BaseModel):
    blank_no: int = Field(gt=0)
    option_text: str
    is_correct: bool = False
    sort_order: int = 0


class GapSelectOptionUpdate(BaseModel):
    blank_no: int | None = Field(default=None, gt=0)
    option_text: str | None = None
    is_correct: bool | None = None
    sort_order: int | None = None


class GapSelectOptionResponse(BaseModel):
    id: int
    question_id: int
    blank_no: int
    option_text: str
    is_correct: bool
    sort_order: int

    class Config:
        from_attributes = True


class GapSelectBulkCreate(BaseModel):
    items: list[GapSelectOptionCreate] = Field(min_length=2)
