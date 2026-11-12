from typing import Optional

from pydantic import BaseModel, Field


class ProctorEventCreate(BaseModel):
    attempt_id: int = Field(gt=0)
    event_type: str = Field(min_length=1, max_length=50)
    detail: Optional[str] = Field(default=None, max_length=2000)


# Event types the exam player can report. Snapshot evidence uploads
# also create a row — flagged types get a photo attached server-side.
PROCTOR_EVENT_TYPES = {
    # Browser-behaviour signals
    "tab_hidden", "window_blur", "copy", "cut", "paste",
    "context_menu", "fullscreen_exit",
    # Camera / AI signals
    "no_face", "multiple_faces", "looking_away",
    "camera_denied", "ai_unavailable",
}
