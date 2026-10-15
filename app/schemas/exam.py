
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class ExamCreate(BaseModel):
    course_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: int = Field(gt=0)
    # Derived from the sum of assigned question marks; 0 until questions are added.
    total_marks: Optional[Decimal] = Field(default=0, ge=0)
    passing_marks: Decimal = Field(default=0, ge=0)
    # Pass threshold as % of total_marks — teachers set this before
    # total marks are known, so absolute passing_marks stays optional.
    passing_percentage: Optional[Decimal] = Field(default=None, ge=0, le=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attempts_allowed: Optional[int] = Field(default=1, ge=1)
    shuffle_questions: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_exam(self):
        if (
            self.total_marks
            and self.passing_percentage is None
            and self.passing_marks > self.total_marks
        ):
            raise ValueError("Passing marks cannot exceed total marks")
        if (
            self.start_time and self.end_time
            and self.end_time <= self.start_time
        ):
            raise ValueError("End time must be after start time")
        return self


class ExamUpdate(BaseModel):
    course_id: Optional[int] = Field(default=None, gt=0)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    total_marks: Optional[Decimal] = Field(default=None, gt=0)
    passing_marks: Optional[Decimal] = Field(default=None, ge=0)
    passing_percentage: Optional[Decimal] = Field(default=None, ge=0, le=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attempts_allowed: Optional[int] = Field(default=None, ge=1)
    shuffle_questions: Optional[bool] = None
    is_active: Optional[bool] = None


class ExamResponse(BaseModel):
    id: int
    course_id: int
    created_by: int
    name: str
    description: Optional[str]
    duration_minutes: int
    total_marks: Decimal
    passing_marks: Decimal
    passing_percentage: Optional[Decimal] = None
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    attempts_allowed: Optional[int]
    shuffle_questions: Optional[bool]
    is_active: Optional[bool]
    created_at: Optional[datetime]
    creator_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExamQuestionCreate(BaseModel):
    question_id: int = Field(gt=0)
    # ge=0 because description-type items are informational and carry no marks.
    marks: Decimal = Field(ge=0)
    sort_order: int = Field(default=0, ge=0)


class ExamQuestionResponse(BaseModel):
    id: int
    exam_id: int
    question_id: int
    marks: Decimal
    sort_order: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class ExamBatchCreate(BaseModel):
    batch_id: int = Field(gt=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    # Restrict grading to these teachers (must be teachers of the
    # batch). Empty/None = every teacher of the batch may grade.
    grader_ids: Optional[list[int]] = None

    @model_validator(mode="after")
    def validate_times(self):
        if (
            self.start_time and self.end_time
            and self.end_time <= self.start_time
        ):
            raise ValueError("End time must be after start time")
        return self


class ExamBatchResponse(BaseModel):
    id: int
    exam_id: int
    batch_id: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    grader_ids: Optional[list[int]] = None

    model_config = ConfigDict(from_attributes=True)
