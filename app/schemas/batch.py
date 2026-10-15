from datetime import date

from pydantic import BaseModel


class BatchCreate(BaseModel):

    course_id: int
    name: str
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class BatchUpdate(BaseModel):

    course_id: int | None = None
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class BatchResponse(BaseModel):

    id: int
    course_id: int
    name: str
    start_date: date | None
    end_date: date | None
    description: str | None
    created_by: int
    creator_name: str | None = None

    class Config:
        from_attributes = True