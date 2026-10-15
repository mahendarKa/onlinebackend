from pydantic import BaseModel


class CourseCreate(BaseModel):

    name: str
    code: str
    description: str | None = None


class CourseUpdate(BaseModel):

    name: str | None = None
    code: str | None = None
    description: str | None = None


class CourseResponse(BaseModel):

    id: int
    name: str
    code: str
    description: str | None
    created_by: int
    creator_name: str | None = None

    class Config:
        from_attributes = True