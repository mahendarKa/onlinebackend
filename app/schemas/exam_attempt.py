
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class StartAttemptResponse(BaseModel):
    attempt_id: int
    exam_id: int
    attempt_no: int
    status: str
    start_time: datetime
    end_time: datetime
    remaining_seconds: int


class SaveAnswerRequest(BaseModel):
    question_id: int = Field(gt=0)
    selected_option_id: Optional[int] = Field(default=None, gt=0)
    selected_option_ids: Optional[list[int]] = None
    match_answers: Optional[dict] = None
    answer_text: Optional[str] = None
    code_text: Optional[str] = None
    answer_file: Optional[str] = Field(default=None, max_length=1000)


class StudentAnswerResponse(BaseModel):
    id: int
    exam_attempt_id: int
    question_id: int
    selected_option_id: Optional[int]
    selected_option_ids: Optional[list[int]] = None
    match_answers: Optional[dict] = None
    answer_text: Optional[str]
    answer_file: Optional[str]
    code_text: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ExamOptionForStudent(BaseModel):
    id: int
    option_text: str
    image_url: Optional[str] = None
    sort_order: Optional[int] = None


class ExamImageForStudent(BaseModel):
    id: int
    image_url: str
    alt_text: Optional[str] = None


class ExamMatchItemForStudent(BaseModel):
    id: int
    sub_question: str
    sort_order: Optional[int] = None


class ExamGapBlankForStudent(BaseModel):
    blank_no: int
    options: list[str]


class ExamOrderingItemForStudent(BaseModel):
    id: int
    item_text: str


class ExamCodingCaseForStudent(BaseModel):
    # Only non-hidden test cases are ever sent to the student.
    input_text: Optional[str] = None
    expected_output: str
    marks: float


class ExamQuestionForStudent(BaseModel):
    id: int
    type: str
    name: str
    question_text: str
    default_mark: float
    options: list[ExamOptionForStudent] = []
    images: list[ExamImageForStudent] = []
    match_items: list[ExamMatchItemForStudent] = []
    match_choices: list[str] = []
    # paragraph questions: ids of questions that belong under this passage
    linked_question_ids: list[int] = []
    # selectmissing: [[n]] blanks with their dropdown choices (shuffled)
    gap_blanks: list[ExamGapBlankForStudent] = []
    # ordering: items shown to the student, already shuffled
    ordering_items: list[ExamOrderingItemForStudent] = []
    # coding: language + starter code + visible sample test cases
    coding_language: Optional[str] = None
    starter_code: Optional[str] = None
    coding_test_cases: list[ExamCodingCaseForStudent] = []


class SubmitAttemptResponse(BaseModel):
    attempt_id: int
    status: str
    attempted: int
    total_questions: int
    message: str


class RunCodeRequest(BaseModel):
    question_id: int = Field(gt=0)
    code: str = Field(max_length=100_000)


class RunCodeCaseResult(BaseModel):
    input_text: Optional[str] = None
    expected_output: str
    actual_output: str
    passed: bool
    timed_out: bool = False
    error: Optional[str] = None
    marks: float = 0


class RunCodeResponse(BaseModel):
    results: list[RunCodeCaseResult]
    passed_count: int
    total: int
