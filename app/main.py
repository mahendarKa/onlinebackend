from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import users
from app.routers import auth
from app.routers import protected
from app.routers import courses
from app.routers import batches
from app.routers import batch_students
from app.routers import batch_teachers
from app.routers import question_categories
from app.routers import questions
from app.routers.question_options import router as question_options_router
from app.routers.question_truefalse import router as question_truefalse_router
from app.routers.question_shortanswer import router as question_shortanswer_router
from app.routers.question_numerical import router as question_numerical_router
from app.routers.question_essay import router as question_essay_router
from app.routers.question_match import router as question_match_router
from app.routers.question_calculated import router as question_calculated_router
from app.routers.question_description import router as question_description_router
from app.routers.question_multianswer import router as question_multianswer_router
from app.routers.question_image import router as question_image_router
from app.routers.paragraphs import router as paragraphs_router
from app.routers.question_gapselect import router as gapselect_router
from app.routers.question_ordering import router as ordering_router
from app.routers.question_random import router as question_random_router
from app.routers.coding_questions import router as coding_questions_router
from app.routers.exams import router as exams_router
from app.routers.exam_attempts import router as exam_attempts_router
from app.routers.results import router as results_router
from app.routers.student_dashboard import router as student_dashboard_router
from app.routers.exam_monitoring import router as exam_monitoring_router
from app.routers.exam_schedule import router as exam_schedule_router
from app.routers.notifications import router as notifications_router
from app.routers.exam_analytics import router as exam_analytics_router
from app.routers.audit_logs import router as audit_logs_router
from app.routers import result_export
from app.routers import result_pdf
from app.routers import attempt_history
from app.routers import exam_feedback
from app.routers import uploads
app = FastAPI(
    title="Online Exam Portal API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users.router)
app.include_router(auth.router)
app.include_router(protected.router)
app.include_router(courses.router)
app.include_router(batches.router)
app.include_router(batch_teachers.router)
app.include_router(batch_students.router)
app.include_router(question_categories.router)
app.include_router(questions.router)
app.include_router(question_options_router)
app.include_router(question_truefalse_router)
app.include_router(question_shortanswer_router)
app.include_router(question_numerical_router)
app.include_router(question_essay_router)
app.include_router(question_match_router)
app.include_router(question_calculated_router)
app.include_router(question_description_router)
app.include_router(question_multianswer_router)
app.include_router(gapselect_router)
app.include_router(ordering_router)
app.include_router(question_image_router)
app.include_router(paragraphs_router)
app.include_router(question_random_router)
app.include_router(coding_questions_router)
app.include_router(exams_router)
app.include_router(exam_attempts_router)
app.include_router(results_router)
app.include_router(student_dashboard_router)
app.include_router(exam_monitoring_router)
app.include_router(exam_schedule_router)
app.include_router(notifications_router)
app.include_router(exam_analytics_router)
app.include_router(audit_logs_router)
app.include_router(result_export.router)
app.include_router(result_pdf.router)
app.include_router(attempt_history.router)
app.include_router(exam_feedback.router)
app.include_router(uploads.router)
@app.get("/")
def root():
    return {
        "message": "Online Exam Portal API is running"
    }