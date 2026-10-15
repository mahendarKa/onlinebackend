
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam, ExamQuestion, ExamBatch, ExamGrader
from app.models.course import Course
from app.models.batch import Batch
from app.models.question import Question
from app.models.question_paragraph import QuestionParagraph
from app.schemas.exam import (
    ExamCreate, ExamUpdate, ExamResponse,
    ExamQuestionCreate, ExamQuestionResponse,
    ExamBatchCreate, ExamBatchResponse,
)
from app.utils.dependencies import require_role
from app.services.activity_service import log_audit, notify, notify_many
from app.models.batch_student import BatchStudent
from app.models.batch_teacher import BatchTeacher
from app.models.user import User
from app.utils.permissions import (
    is_admin,
    require_exam_edit,
    require_exam_view,
    teacher_exam_ids,
)

router = APIRouter(prefix="/api/exams", tags=["Exams"])
teacher_admin = Depends(require_role("admin", "teacher"))


def get_exam(exam_id: int, db: Session):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def attach_creator_names(exams, db: Session):
    """Add .creator_name to each exam row (serialized via from_attributes)."""
    ids = {e.created_by for e in exams if e.created_by}
    names = {
        u.id: u.name
        for u in db.query(User.id, User.name).filter(User.id.in_(ids)).all()
    } if ids else {}
    for e in exams:
        e.creator_name = names.get(e.created_by)
    return exams


def recalc_total_marks(exam_id: int, db: Session):
    """Derive exam.total_marks from the sum of assigned question marks."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    total = (
        db.query(func.coalesce(func.sum(ExamQuestion.marks), 0))
        .filter(ExamQuestion.exam_id == exam_id)
        .scalar()
    )
    exam.total_marks = total or Decimal("0")


# CREATE EXAM
@router.post("/", response_model=ExamResponse, status_code=201)
def create_exam(
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    course = db.query(Course).filter(
        Course.id == data.course_id
    ).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if (
        data.start_time and data.end_time
        and data.end_time <= data.start_time
    ):
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time",
        )

    if data.start_time and data.end_time:
        window_min = (
            data.end_time - data.start_time
        ).total_seconds() / 60
        if data.duration_minutes and data.duration_minutes > window_min:
            raise HTTPException(
                status_code=400,
                detail=f"Duration ({data.duration_minutes} min) cannot exceed "
                       f"the start-to-end window ({int(window_min)} min)",
            )

    exam = Exam(
        **data.model_dump(),
        created_by=current_user.id,
    )
    db.add(exam)
    db.flush()
    log_audit(
        db, current_user.id, "exam.create", "exam", exam.id,
        details=f"'{exam.name}' in course {exam.course_id}",
    )
    db.commit()
    db.refresh(exam)
    return attach_creator_names([exam], db)[0]


# LIST EXAMS
@router.get("/", response_model=list[ExamResponse])
def list_exams(
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    query = db.query(Exam)
    if not is_admin(current_user):
        # Teachers see exams they created plus exams assigned to
        # batches they teach (those are gradeable by them).
        visible = teacher_exam_ids(db, current_user.id)
        query = query.filter(Exam.id.in_(visible or {0}))
    exams = query.order_by(Exam.id.desc()).all()
    return attach_creator_names(exams, db)


# GET ONE EXAM
@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam_api(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_view(current_user, exam, db)
    return attach_creator_names([exam], db)[0]


# UPDATE EXAM
@router.put("/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: int,
    data: ExamUpdate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_edit(current_user, exam)
    updates = data.model_dump(exclude_unset=True)

    if "course_id" in updates:
        course = db.query(Course).filter(
            Course.id == updates["course_id"]
        ).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

    for key, value in updates.items():
        setattr(exam, key, value)

    # total_marks is 0 until questions are added — only enforce the
    # passing-marks rule once the exam actually has questions.
    if (
        ("passing_marks" in updates or "total_marks" in updates)
        and exam.total_marks
        and exam.passing_marks > exam.total_marks
    ):
        raise HTTPException(
            status_code=400,
            detail="Passing marks cannot exceed total marks",
        )

    if (
        exam.start_time and exam.end_time
        and exam.end_time <= exam.start_time
    ):
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time",
        )

    if (
        {"duration_minutes", "start_time", "end_time"} & updates.keys()
        and exam.start_time and exam.end_time
    ):
        window_min = (
            exam.end_time - exam.start_time
        ).total_seconds() / 60
        if exam.duration_minutes and exam.duration_minutes > window_min:
            raise HTTPException(
                status_code=400,
                detail=f"Duration ({exam.duration_minutes} min) cannot exceed "
                       f"the start-to-end window ({int(window_min)} min)",
            )

    log_audit(
        db, current_user.id, "exam.update", "exam", exam.id,
        details=f"'{exam.name}' fields: "
                f"{', '.join(sorted(updates.keys()))}",
    )
    db.commit()
    db.refresh(exam)
    return attach_creator_names([exam], db)[0]


# DELETE EXAM
@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_edit(current_user, exam)
    log_audit(
        db, current_user.id, "exam.delete", "exam", exam.id,
        details=f"'{exam.name}'",
    )
    db.delete(exam)
    db.commit()
    return {"message": "Exam deleted successfully"}


# ADD QUESTION TO EXAM
@router.post(
    "/{exam_id}/questions",
    response_model=ExamQuestionResponse,
    status_code=201,
)
def add_question(
    exam_id: int,
    data: ExamQuestionCreate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_edit(current_user, exam)

    question = db.query(Question).filter(
        Question.id == data.question_id,
        Question.is_active == True,
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Active question not found",
        )

    existing = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam_id,
        ExamQuestion.question_id == data.question_id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Question already added to this exam",
        )

    payload = data.model_dump()
    # Description/paragraph items are informational text; they carry no marks.
    if question.type in ("description", "paragraph"):
        payload["marks"] = 0

    exam_question = ExamQuestion(
        exam_id=exam_id,
        **payload,
    )
    db.add(exam_question)
    db.flush()

    # Paragraph passages bring their linked questions along, so the
    # passage always lands in the same exam as its children.
    if question.type == "paragraph":
        config = db.query(QuestionParagraph).filter(
            QuestionParagraph.question_id == question.id
        ).first()
        if config and config.child_question_ids:
            in_exam = {
                row.question_id
                for row in db.query(ExamQuestion.question_id).filter(
                    ExamQuestion.exam_id == exam_id
                ).all()
            }
            next_sort = (db.query(func.max(ExamQuestion.sort_order)).filter(
                ExamQuestion.exam_id == exam_id
            ).scalar() or 0) + 1
            for child_id in config.child_question_ids:
                if child_id in in_exam:
                    continue
                child = db.query(Question).filter(
                    Question.id == child_id,
                    Question.is_active == True,
                ).first()
                if not child:
                    continue
                db.add(ExamQuestion(
                    exam_id=exam_id,
                    question_id=child_id,
                    marks=child.default_mark,
                    sort_order=next_sort,
                ))
                next_sort += 1

    # total_marks is derived from the assigned questions.
    recalc_total_marks(exam_id, db)

    db.commit()
    db.refresh(exam_question)
    return exam_question


# LIST EXAM QUESTIONS
@router.get("/{exam_id}/questions", response_model=list[ExamQuestionResponse])
def list_exam_questions(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_view(current_user, exam, db)
    return db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam_id
    ).order_by(ExamQuestion.sort_order, ExamQuestion.id).all()


# REMOVE QUESTION FROM EXAM
@router.delete("/{exam_id}/questions/{exam_question_id}")
def remove_question(
    exam_id: int,
    exam_question_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_edit(current_user, exam)

    item = db.query(ExamQuestion).filter(
        ExamQuestion.id == exam_question_id,
        ExamQuestion.exam_id == exam_id,
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Exam question not found")

    db.delete(item)
    db.flush()
    recalc_total_marks(exam_id, db)
    db.commit()
    return {"message": "Question removed from exam"}


# ASSIGN BATCH
@router.post(
    "/{exam_id}/batches",
    response_model=ExamBatchResponse,
    status_code=201,
)
def assign_batch(
    exam_id: int,
    data: ExamBatchCreate,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_edit(current_user, exam)

    batch = db.query(Batch).filter(
        Batch.id == data.batch_id
    ).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if data.start_time and data.start_time < datetime.now():
        raise HTTPException(
            status_code=400,
            detail="Start time cannot be in the past",
        )

    if (
        data.start_time and data.end_time
        and data.end_time <= data.start_time
    ):
        raise HTTPException(
            status_code=400,
            detail="Batch end time must be after start time",
        )

    # Batch window must sit inside the exam's availability window.
    if exam.start_time:
        if data.start_time and data.start_time < exam.start_time:
            raise HTTPException(
                status_code=400,
                detail="Batch start cannot be before the exam opens",
            )
        if data.end_time and data.end_time <= exam.start_time:
            raise HTTPException(
                status_code=400,
                detail="Batch end must be after the exam opens",
            )
    if exam.end_time:
        if data.start_time and data.start_time >= exam.end_time:
            raise HTTPException(
                status_code=400,
                detail="Batch start cannot be after the exam closes",
            )
        if data.end_time and data.end_time > exam.end_time:
            raise HTTPException(
                status_code=400,
                detail="Batch end cannot be after the exam closes",
            )

    existing = db.query(ExamBatch).filter(
        ExamBatch.exam_id == exam_id,
        ExamBatch.batch_id == data.batch_id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Batch already assigned to this exam",
        )

    # Grading can be restricted to selected teachers of this batch.
    grader_ids = data.grader_ids or []
    batch_teachers = {
        row.user_id
        for row in db.query(BatchTeacher).filter(
            BatchTeacher.batch_id == data.batch_id,
            BatchTeacher.is_active == True,  # noqa: E712
        ).all()
    }
    if grader_ids:
        invalid = set(grader_ids) - batch_teachers
        if invalid:
            raise HTTPException(
                status_code=400,
                detail="Graders must be teachers assigned to this batch",
            )

    assignment = ExamBatch(
        exam_id=exam.id,
        batch_id=data.batch_id,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    db.add(assignment)
    db.flush()

    for gid in set(grader_ids):
        db.add(ExamGrader(exam_batch_id=assignment.id, user_id=gid))
    assignment.grader_ids = sorted(set(grader_ids))

    # Notify every student in the batch about the new exam.
    student_ids = [
        row.user_id
        for row in db.query(BatchStudent).filter(
            BatchStudent.batch_id == data.batch_id,
            BatchStudent.is_active == True,  # noqa: E712
        ).all()
    ]
    window = ""
    if data.start_time and data.end_time:
        window = (
            f" Available {data.start_time:%d %b %Y %I:%M %p}"
            f" – {data.end_time:%d %b %I:%M %p}."
        )
    notify_many(
        db, student_ids,
        f"New exam assigned: {exam.name}",
        f"\"{exam.name}\" was assigned to your batch. "
        f"Duration: {exam.duration_minutes} min.{window}",
        "exam.assigned",
    )

    # Notify the batch's other teachers that the batch was assigned
    # (the assigning user already knows). Selected graders hear that
    # they can grade; the rest hear about the assignment only.
    grader_set = set(grader_ids)
    for tid in batch_teachers - {current_user.id}:
        if grader_set and tid in grader_set:
            msg = (
                f"\"{exam.name}\" was assigned to batch "
                f"\"{batch.name}\" and you were selected as a grader."
            )
        elif grader_set:
            msg = (
                f"\"{exam.name}\" was assigned to batch "
                f"\"{batch.name}\". Grading was assigned to selected "
                "teachers."
            )
        else:
            msg = (
                f"\"{exam.name}\" was assigned to batch "
                f"\"{batch.name}\". You can grade it."
            )
        notify(
            db, tid,
            f"Exam assigned to your batch: {exam.name}",
            msg + window,
            "exam.batch_assigned",
        )

    log_audit(
        db, current_user.id, "exam.assign_batch", "exam_batch", None,
        details=f"exam {exam.id} '{exam.name}' -> batch {data.batch_id} "
                f"({len(student_ids)} students notified"
                f"{', graders: ' + ','.join(map(str, sorted(grader_set))) if grader_set else ''})",
    )
    db.commit()
    db.refresh(assignment)
    return assignment


# LIST ASSIGNED BATCHES
@router.get("/{exam_id}/batches", response_model=list[ExamBatchResponse])
def list_exam_batches(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_view(current_user, exam, db)
    rows = db.query(ExamBatch).filter(
        ExamBatch.exam_id == exam_id
    ).all()
    graders = {r.id: [] for r in rows}
    if rows:
        for g in db.query(ExamGrader).filter(
            ExamGrader.exam_batch_id.in_([r.id for r in rows])
        ).all():
            graders.setdefault(g.exam_batch_id, []).append(g.user_id)
    for r in rows:
        r.grader_ids = sorted(graders.get(r.id, []))
    return rows


# UPDATE GRADERS FOR AN ASSIGNMENT
@router.put(
    "/{exam_id}/batches/{assignment_id}/graders",
    response_model=ExamBatchResponse,
)
def update_assignment_graders(
    exam_id: int,
    assignment_id: int,
    grader_ids: list[int],
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    """Replace the selected graders. Empty list = all batch teachers."""
    exam = get_exam(exam_id, db)
    require_exam_edit(current_user, exam)

    assignment = db.query(ExamBatch).filter(
        ExamBatch.id == assignment_id,
        ExamBatch.exam_id == exam_id,
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="Batch assignment not found",
        )

    batch_teachers = {
        row.user_id
        for row in db.query(BatchTeacher).filter(
            BatchTeacher.batch_id == assignment.batch_id,
            BatchTeacher.is_active == True,  # noqa: E712
        ).all()
    }
    grader_set = set(grader_ids or [])
    invalid = grader_set - batch_teachers
    if invalid:
        raise HTTPException(
            status_code=400,
            detail="Graders must be teachers assigned to this batch",
        )

    existing = {
        r.user_id
        for r in db.query(ExamGrader).filter(
            ExamGrader.exam_batch_id == assignment.id
        ).all()
    }
    db.query(ExamGrader).filter(
        ExamGrader.exam_batch_id == assignment.id
    ).delete(synchronize_session=False)
    for gid in grader_set:
        db.add(ExamGrader(exam_batch_id=assignment.id, user_id=gid))

    batch = db.query(Batch).filter(Batch.id == assignment.batch_id).first()
    for tid in grader_set - existing - {current_user.id}:
        notify(
            db, tid,
            f"You can grade: {exam.name}",
            f"You were added as a grader for \"{exam.name}\" "
            f"(batch \"{batch.name if batch else assignment.batch_id}\").",
            "exam.grader_assigned",
        )

    log_audit(
        db, current_user.id, "exam.set_graders", "exam_batch",
        assignment.id,
        details=f"exam {exam.id} graders: "
                f"{sorted(grader_set) if grader_set else 'all batch teachers'}",
    )
    db.commit()
    db.refresh(assignment)
    assignment.grader_ids = sorted(grader_set)
    return assignment


# REMOVE BATCH ASSIGNMENT
@router.delete("/{exam_id}/batches/{assignment_id}")
def remove_batch(
    exam_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    exam = get_exam(exam_id, db)
    require_exam_edit(current_user, exam)

    assignment = db.query(ExamBatch).filter(
        ExamBatch.id == assignment_id,
        ExamBatch.exam_id == exam_id,
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="Batch assignment not found",
        )

    db.query(ExamGrader).filter(
        ExamGrader.exam_batch_id == assignment.id
    ).delete(synchronize_session=False)
    db.delete(assignment)
    db.commit()
    return {"message": "Batch assignment removed"}
