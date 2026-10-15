
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class CodingQuestionCreate(BaseModel):
    language: str = Field(min_length=1, max_length=50)
    starter_code: Optional[str] = None
    time_limit: int = Field(default=2, ge=1, le=60)
    memory_limit: int = Field(default=256, ge=16, le=4096)
    execution_limit: int = Field(default=10, ge=1, le=300)
    compiler_version: Optional[str] = Field(default=None, max_length=100)


class CodingQuestionUpdate(BaseModel):
    language: Optional[str] = Field(default=None, min_length=1, max_length=50)
    starter_code: Optional[str] = None
    time_limit: Optional[int] = Field(default=None, ge=1, le=60)
    memory_limit: Optional[int] = Field(default=None, ge=16, le=4096)
    execution_limit: Optional[int] = Field(default=None, ge=1, le=300)
    compiler_version: Optional[str] = Field(default=None, max_length=100)


class CodingQuestionResponse(BaseModel):
    id: int
    question_id: int
    language: str
    starter_code: Optional[str]
    time_limit: int
    memory_limit: int
    execution_limit: int
    compiler_version: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CodingTestCaseCreate(BaseModel):
    input_text: Optional[str] = None
    expected_output: str
    is_hidden: bool = False
    marks: float = Field(default=1, gt=0, le=1000)
    sort_order: int = Field(default=0, ge=0)


class CodingTestCaseUpdate(BaseModel):
    input_text: Optional[str] = None
    expected_output: Optional[str] = None
    is_hidden: Optional[bool] = None
    marks: Optional[float] = Field(default=None, gt=0, le=1000)
    sort_order: Optional[int] = Field(default=None, ge=0)


class CodingTestCaseResponse(BaseModel):
    id: int
    coding_question_id: int
    input_text: Optional[str]
    expected_output: str
    is_hidden: bool
    marks: float
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
