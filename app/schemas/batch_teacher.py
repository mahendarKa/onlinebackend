from datetime import datetime

from pydantic import BaseModel


class BatchTeacherCreate(BaseModel):

    batch_id: int
    user_id: int


class BatchTeacherResponse(BaseModel):

    id: int
    batch_id: int
    user_id: int
    assigned_at: datetime
    is_active: bool

    class Config:
        from_attributes = True
