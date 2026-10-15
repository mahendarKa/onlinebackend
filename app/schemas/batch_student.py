from datetime import datetime

from pydantic import BaseModel


class BatchStudentCreate(BaseModel):

    batch_id: int
    user_id: int


class BatchStudentResponse(BaseModel):

    id: int
    batch_id: int
    user_id: int
    enrolled_at: datetime
    is_active: bool

    class Config:
        from_attributes = True