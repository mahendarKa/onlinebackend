from pydantic import BaseModel, Field


class QuestionImageCreate(BaseModel):
    # /api/uploads/<file> or an absolute URL
    image_url: str = Field(min_length=1, max_length=1000)
    alt_text: str | None = None
    position: int = Field(default=0, ge=0)


class QuestionImageUpdate(BaseModel):
    image_url: str | None = Field(default=None, max_length=1000)
    alt_text: str | None = None
    position: int | None = Field(default=None, ge=0)


class QuestionImageResponse(BaseModel):
    id: int
    question_id: int
    image_url: str
    alt_text: str | None
    position: int

    class Config:
        from_attributes = True