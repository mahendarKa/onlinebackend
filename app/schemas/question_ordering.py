from pydantic import BaseModel, Field


class OrderingItemCreate(BaseModel):
    item_text: str
    position: int = Field(gt=0)


class OrderingItemUpdate(BaseModel):
    item_text: str | None = None
    position: int | None = Field(default=None, gt=0)


class OrderingItemResponse(BaseModel):
    id: int
    question_id: int
    item_text: str
    position: int

    class Config:
        from_attributes = True


class OrderingBulkCreate(BaseModel):
    items: list[OrderingItemCreate] = Field(min_length=2)
