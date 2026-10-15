"""Teacher scoping rules shared by routers.

- admin / superadmin: unrestricted.
- teacher: sees exams they created plus exams assigned to batches they
  teach (BatchTeacher). Only the exam's creator may edit/delete it —
  co-teachers get read + grading access through the batch.
- teacher sees batches they created plus batches they are assigned to.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.batch_teacher import BatchTeacher
from app.models.exam import Exam, ExamBatch, ExamGrader


ADMIN_ROLES = ("admin", "superadmin")


def is_admin(user) -> bool:
    return user.role in ADMIN_ROLES


def teacher_batch_ids(db: Session, teacher_id: int) -> set[int]:
    """Batches where this user is an active assigned teacher."""
    rows = db.query(BatchTeacher.batch_id).filter(
        BatchTeacher.user_id == teacher_id,
        BatchTeacher.is_active == True,  # noqa: E712
    ).all()
    return {r[0] for r in rows}


def teacher_exam_ids(db: Session, teacher_id: int) -> set[int]:
    """Exams a teacher may view/grade: own exams + exams assigned to
    batches they teach."""
    batch_ids = teacher_batch_ids(db, teacher_id)
    exam_ids = {
        r[0] for r in db.query(Exam.id).filter(
            Exam.created_by == teacher_id
        ).all()
    }
    if batch_ids:
        exam_ids |= {
            r[0] for r in db.query(ExamBatch.exam_id).filter(
                ExamBatch.batch_id.in_(batch_ids)
            ).all()
        }
    return exam_ids


def can_view_exam(user, exam: Exam, db: Session) -> bool:
    if is_admin(user) or exam.created_by == user.id:
        return True
    if user.role != "teacher":
        return False
    return exam.id in teacher_exam_ids(db, user.id)


def require_exam_view(user, exam: Exam, db: Session) -> None:
    if not can_view_exam(user, exam, db):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this exam",
        )


def require_exam_edit(user, exam: Exam) -> None:
    """Only the creator (or admin/superadmin) may modify an exam."""
    if is_admin(user) or exam.created_by == user.id:
        return
    raise HTTPException(
        status_code=403,
        detail="Only the exam creator can modify this exam",
    )


# --------------------------------------------------
# GRADING
# --------------------------------------------------

def batch_teacher_ids(db: Session, batch_id: int) -> set[int]:
    """Active teachers assigned to a batch."""
    rows = db.query(BatchTeacher.user_id).filter(
        BatchTeacher.batch_id == batch_id,
        BatchTeacher.is_active == True,  # noqa: E712
    ).all()
    return {r[0] for r in rows}


def _assignments(db: Session, exam_id: int):
    return db.query(ExamBatch).filter(
        ExamBatch.exam_id == exam_id
    ).all()


def can_grade_exam(user, exam: Exam, db: Session) -> bool:
    """Creator/admins always grade. A batch teacher may grade via an
    assignment unless that assignment restricted grading to selected
    teachers (ExamGrader rows) and the teacher is not among them."""
    if is_admin(user) or exam.created_by == user.id:
        return True
    if user.role != "teacher":
        return False
    for eb in _assignments(db, exam.id):
        graders = {
            r[0] for r in db.query(ExamGrader.user_id).filter(
                ExamGrader.exam_batch_id == eb.id
            ).all()
        }
        if graders:
            if user.id in graders:
                return True
            continue  # restricted and this teacher is not selected
        if user.id in batch_teacher_ids(db, eb.batch_id):
            return True
    return False


def require_exam_grade(user, exam: Exam, db: Session) -> None:
    if not can_grade_exam(user, exam, db):
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to grade this exam",
        )


def teacher_gradeable_exam_ids(db: Session, teacher_id: int) -> set[int]:
    """Exams the teacher may grade: exams they created plus exams
    with at least one assignment that lets them grade."""
    own = {
        r[0] for r in db.query(Exam.id).filter(
            Exam.created_by == teacher_id
        ).all()
    }
    # Candidate exams = assigned to batches this teacher belongs to.
    candidates = teacher_exam_ids(db, teacher_id) - own
    graders = db.query(ExamGrader).join(
        ExamBatch, ExamGrader.exam_batch_id == ExamBatch.id
    ).filter(
        ExamBatch.exam_id.in_(candidates or {0})
    ).all()
    # Restricted assignments and which teachers they allow.
    restricted_eb = set()
    allowed_user_ids = set()
    for g in graders:
        restricted_eb.add(g.exam_batch_id)
        if g.user_id == teacher_id:
            allowed_user_ids.add(g.exam_batch_id)
    restricted_exam_ids = {
        r.exam_id for r in db.query(ExamBatch).filter(
            ExamBatch.id.in_(restricted_eb or {0})
        ).all()
    }
    allowed_exam_ids = {
        r.exam_id for r in db.query(ExamBatch).filter(
            ExamBatch.id.in_(allowed_user_ids or {0})
        ).all()
    }
    # Keep unrestricted candidates; add exams where a restriction
    # explicitly names this teacher.
    result = (candidates - restricted_exam_ids) | allowed_exam_ids
    return own | result


def teacher_visible_batch_ids(db: Session, teacher_id: int) -> set[int]:
    """Batches a teacher may view/manage: created by them or assigned."""
    ids = teacher_batch_ids(db, teacher_id)
    ids |= {
        r[0] for r in db.query(Batch.id).filter(
            Batch.created_by == teacher_id
        ).all()
    }
    return ids


def require_batch_access(user, batch: Batch, db: Session) -> None:
    if is_admin(user):
        return
    if batch.created_by == user.id:
        return
    if (
        user.role == "teacher"
        and batch.id in teacher_batch_ids(db, user.id)
    ):
        return
    raise HTTPException(
        status_code=403,
        detail="You do not have access to this batch",
    )
