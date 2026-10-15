from decimal import Decimal
from pydantic import BaseModel, Field


class DatasetItem(BaseModel):
    """Range for one {name} wildcard used in formula/question text."""
    name: str = Field(min_length=1, max_length=20)
    min_value: Decimal
    max_value: Decimal
    decimals: int = Field(default=0, ge=0, le=6)


class QuestionCalculatedCreate(BaseModel):
    formula: str = Field(min_length=1)
    tolerance: Decimal = Field(default=Decimal("0"), ge=0)
    units: str | None = None
    datasets: list[DatasetItem] = []


class QuestionCalculatedUpdate(BaseModel):
    formula: str | None = Field(default=None, min_length=1)
    tolerance: Decimal | None = Field(default=None, ge=0)
    units: str | None = None
    datasets: list[DatasetItem] | None = None


class QuestionCalculatedResponse(BaseModel):
    id: int
    question_id: int
    formula: str
    tolerance: Decimal
    units: str | None
    datasets: list[DatasetItem] | None = None

    class Config:
        from_attributes = True