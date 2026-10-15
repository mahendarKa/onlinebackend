import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.config.database import get_db
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt, ExamResult
from app.models.user import User
from app.utils.dependencies import require_role
from app.utils.permissions import require_exam_view

# Brand colours taken from the portal logo.
LOGO_BLUE = colors.HexColor("#1D4ED8")   # bg-blue-700
LOGO_YELLOW = colors.HexColor("#FBBF24")  # bg-amber-400
LIGHT_BLUE = colors.HexColor("#EFF6FF")   # blue-50

router = APIRouter(
    prefix="/api/result-pdf",
    tags=["Result PDF Export"]
)


@router.get("/exams/{exam_id}/pdf")
def export_exam_results_pdf(
    exam_id: int,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    require_exam_view(current_user, exam, db)

    results = (
        db.query(ExamResult, ExamAttempt, User)
        .join(
            ExamAttempt,
            ExamResult.exam_attempt_id == ExamAttempt.id
        )
        .join(
            User,
            ExamAttempt.user_id == User.id
        )
        .filter(ExamAttempt.exam_id == exam_id)
        .order_by(
            ExamAttempt.user_id,
            ExamAttempt.attempt_no
        )
        .all()
    )

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25,
    )

    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Title"],
        textColor=LOGO_BLUE,
    )
    meta_style = ParagraphStyle(
        "BrandMeta",
        parent=styles["Normal"],
        backColor=LOGO_YELLOW,
        borderPadding=(4, 6, 4, 6),
        spaceBefore=6,
    )

    elements.append(
        Paragraph("Exam Result Report", title_style)
    )
    elements.append(
        Paragraph(
            f"Exam: {exam.name} | Exam ID: {exam.id}",
            meta_style,
        )
    )
    elements.append(Spacer(1, 15))

    header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,  # center
    )

    data = [[
        Paragraph(label, header_style)
        for label in [
            "Student ID",
            "Student Name",
            "Attempt",
            "Questions",
            "Attempted",
            "Correct",
            "Wrong",
            "Skipped",
            "Marks",
            "Percentage",
            "Result",
        ]
    ]]

    for result, attempt, student in results:
        data.append([
            str(student.id),
            Paragraph(
                student.name or "",
                styles["BodyText"]
            ),
            str(attempt.attempt_no),
            str(result.total_questions),
            str(result.attempted),
            str(result.correct),
            str(result.wrong),
            str(result.skipped),
            str(result.total_marks),
            f"{result.percentage}%",
            str(result.pass_fail),
        ])

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            45, 120, 45, 55, 55, 45,
            45, 45, 55, 60, 55
        ],
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LOGO_BLUE),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, LOGO_YELLOW),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5,
         colors.HexColor("#BFDBFE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, LIGHT_BLUE]),
    ]))

    elements.append(table)
    document.build(elements)

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="exam_{exam_id}_results.pdf"'
        },
    )