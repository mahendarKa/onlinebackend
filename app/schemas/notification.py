
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class NotificationCreate(BaseModel):
    user_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    notification_type: str = Field(
        default="general", max_length=50
    )
    link: str | None = Field(default=None, max_length=500)


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    link: str | None = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
