
from decimal import Decimal, InvalidOperation

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import csv
import io

from fastapi.responses import StreamingResponse

from app.config.database import get_db
from app.models.question import Question
from app.models.question_category import QuestionCategory
from app.models.question_option import QuestionOption
from app.models.question_truefalse import QuestionTrueFalse
from app.models.question_shortanswer import QuestionShortAnswer
from app.models.question_numerical import QuestionNumerical
from app.models.question_multianswer import QuestionMultiAnswer
from app.models.question_match import QuestionMatch
from app.models.question_gapselect import QuestionGapSelect
from app.models.question_ordering import QuestionOrdering
from app.models.question_essay import QuestionEssay
from app.models.question_description import QuestionDescription
from app.models.question_calculated import QuestionCalculated
from app.models.question_image import QuestionImage
from app.models.question_paragraph import QuestionParagraph
from app.models.paragraph_question import ParagraphQuestion
from app.models.exam import Exam, ExamQuestion
from app.models.exam_attempt import (
    ExamAttempt,
    ExamResult,
    StudentAnswer,
)
from app.models.coding_question import CodingQuestion, CodingTestCase
from app.models.user import User
from app.services.activity_service import log_audit

from app.schemas.question import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
)

from app.utils.dependencies import (
    get_current_user,
    require_role,
)

from app.utils.question_types import QUESTION_TYPES

from app.schemas.question_import import (
    BulkQuestionImportRequest,
    BulkQuestionImportResponse,
)


router = APIRouter(
    prefix="/api/questions",
    tags=["Questions"],
)


# --------------------------------------------------
# CREATE QUESTION
# --------------------------------------------------

@router.post(
    "/",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_question(
    question_data: QuestionCreate,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db),
):
    category = (
        db.query(QuestionCategory)
        .filter(QuestionCategory.id == question_data.category_id)
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question category not found",
        )

    if question_data.type not in QUESTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid question type: {question_data.type}",
        )

    # Description/paragraph items are informational and may carry 0 marks.
    if question_data.default_mark <= 0 and question_data.type not in (
        "description",
        "paragraph",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question mark must be greater than zero",
        )

    question = Question(
        category_id=question_data.category_id,
        type=question_data.type,
        name=question_data.name,
        question_text=question_data.question_text,
        default_mark=question_data.default_mark,
        general_feedback=question_data.general_feedback,
        created_by=current_user.id,
        is_active=True,
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    return question


# --------------------------------------------------
# GET ALL ACTIVE QUESTIONS
# --------------------------------------------------

@router.get(
    "/",
    response_model=list[QuestionResponse],
)
def get_questions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    questions = (
        db.query(Question)
        .filter(Question.is_active == True)
        .order_by(Question.id.desc())
        .all()
    )
    ids = {q.created_by for q in questions if q.created_by}
    names = {
        u.id: u.name
        for u in db.query(User.id, User.name).filter(User.id.in_(ids)).all()
    } if ids else {}
    for q in questions:
        q.creator_name = names.get(q.created_by)
    return questions


# --------------------------------------------------
# GET QUESTIONS BY CATEGORY
# --------------------------------------------------

@router.get(
    "/category/{category_id}",
    response_model=list[QuestionResponse],
)
def get_category_questions(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    category = (
        db.query(QuestionCategory)
        .filter(QuestionCategory.id == category_id)
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    return (
        db.query(Question)
        .filter(
            Question.category_id == category_id,
            Question.is_active == True,
        )
        .order_by(Question.id.desc())
        .all()
    )


# --------------------------------------------------
# GET QUESTIONS BY TYPE
# --------------------------------------------------

@router.get(
    "/type/{question_type}",
    response_model=list[QuestionResponse],
)
def get_questions_by_type(
    question_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if question_type not in QUESTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question type",
        )

    return (
        db.query(Question)
        .filter(
            Question.type == question_type,
            Question.is_active == True,
        )
        .order_by(Question.id.desc())
        .all()
    )


# --------------------------------------------------
# SEARCH, FILTER AND PAGINATE QUESTIONS
# IMPORTANT: Keep this before GET /{question_id}
# --------------------------------------------------

@router.get("/search")
def search_questions(
    keyword: str | None = Query(default=None, min_length=1),
    category_id: int | None = Query(default=None, gt=0),
    question_type: str | None = None,
    min_marks: float | None = Query(default=None, ge=0),
    max_marks: float | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db),
):
    query = db.query(Question).filter(
        Question.is_active == True
    )

    # Validate the marks range
    if (
        min_marks is not None
        and max_marks is not None
        and min_marks > max_marks
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_marks cannot exceed max_marks",
        )

    # Search question name and question text
    if keyword:
        search_keyword = f"%{keyword.strip()}%"

        query = query.filter(
            or_(
                Question.name.ilike(search_keyword),
                Question.question_text.ilike(search_keyword),
            )
        )

    # Filter by category
    if category_id is not None:
        query = query.filter(
            Question.category_id == category_id
        )

    # Filter by question type
    if question_type:
        if question_type not in QUESTION_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid question type: {question_type}",
            )

        query = query.filter(
            Question.type == question_type
        )

    # Filter by minimum marks
    if min_marks is not None:
        query = query.filter(
            Question.default_mark >= min_marks
        )

    # Filter by maximum marks
    if max_marks is not None:
        query = query.filter(
            Question.default_mark <= max_marks
        )

    # Count matching questions before pagination
    total_items = query.count()

    # Fetch only the requested page
    questions = (
        query
        .order_by(Question.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "id": question.id,
                "category_id": question.category_id,
                "type": question.type,
                "name": question.name,
                "question_text": question.question_text,
                "default_mark": question.default_mark,
                "is_active": question.is_active,
            }
            for question in questions
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": (
                total_items + page_size - 1
            ) // page_size,
        },
    }


# --------------------------------------------------
# GET QUESTION BY ID
# --------------------------------------------------

@router.get(
    "/{question_id}",
    response_model=QuestionResponse,
)
def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    return question


# --------------------------------------------------
# UPDATE QUESTION
# --------------------------------------------------

@router.put(
    "/{question_id}",
    response_model=QuestionResponse,
)
def update_question(
    question_id: int,
    question_data: QuestionUpdate,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db),
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if question_data.category_id is not None:
        category = (
            db.query(QuestionCategory)
            .filter(
                QuestionCategory.id == question_data.category_id
            )
            .first()
        )

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question category not found",
            )

        question.category_id = question_data.category_id

    if question_data.type is not None:
        if question_data.type not in QUESTION_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid question type",
            )

        question.type = question_data.type

    if question_data.name is not None:
        question.name = question_data.name

    if question_data.question_text is not None:
        question.question_text = question_data.question_text

    if question_data.default_mark is not None:
        if question_data.default_mark <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question mark must be greater than zero",
            )

        question.default_mark = question_data.default_mark

    if question_data.general_feedback is not None:
        question.general_feedback = question_data.general_feedback

    if question_data.is_active is not None:
        question.is_active = question_data.is_active

    db.commit()
    db.refresh(question)

    return question


# --------------------------------------------------
# DELETE QUESTION (SOFT DELETE)
# --------------------------------------------------

@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db),
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    question.is_active = False

    # ---------- cascade the delete ----------

    # 1) Remove the question from every exam that uses it.
    exam_ids = {
        row.exam_id
        for row in db.query(ExamQuestion.exam_id).filter(
            ExamQuestion.question_id == question_id
        ).all()
    }
    db.query(ExamQuestion).filter(
        ExamQuestion.question_id == question_id
    ).delete(synchronize_session=False)

    # 2) Paragraph linkage: unlink from passages, drop it from any
    #    paragraph question's children, and remove its own config.
    db.query(ParagraphQuestion).filter(
        ParagraphQuestion.question_id == question_id
    ).delete(synchronize_session=False)
    for cfg in db.query(QuestionParagraph).all():
        ids = cfg.child_question_ids or []
        if question_id in ids:
            cfg.child_question_ids = [
                qid for qid in ids if qid != question_id
            ]
    db.query(QuestionParagraph).filter(
        QuestionParagraph.question_id == question_id
    ).delete(synchronize_session=False)

    # 3) Drop recorded student answers to this question.
    db.query(StudentAnswer).filter(
        StudentAnswer.question_id == question_id
    ).delete(synchronize_session=False)

    db.flush()

    # 4) Fix each affected exam's total marks.
    for eid in exam_ids:
        exam = db.query(Exam).filter(Exam.id == eid).first()
        if exam:
            exam.total_marks = (
                db.query(
                    func.coalesce(func.sum(ExamQuestion.marks), 0)
                )
                .filter(ExamQuestion.exam_id == eid)
                .scalar()
            )

    db.commit()

    # 5) Recount results of finished attempts in those exams — the
    #    removed question no longer counts toward totals.
    from app.routers.results import recalculate_result

    finished = (
        db.query(ExamAttempt)
        .join(
            ExamResult,
            ExamResult.exam_attempt_id == ExamAttempt.id,
        )
        .filter(ExamAttempt.exam_id.in_(exam_ids))
        .all()
    )
    for attempt in finished:
        recalculate_result(attempt, db)

    return {
        "message": "Question deleted successfully",
        "removed_from_exams": len(exam_ids),
        "results_recalculated": len(finished),
    }



# --------------------------------------------------
# BULK UPLOAD QUESTIONS FROM CSV
# --------------------------------------------------
#
# Columns (required *):
#   name*, type*, question_text*, category* (NAME; created if missing),
#   default_mark, general_feedback
#   category_id       numeric id, only needed if the category name is
#                     ambiguous; 'category' takes precedence when both
#                     are present
#   options            "A|B|C"            multichoice, multiselect, image
#   correct_options    "1"  or  "1|3"     option indexes (1-based)
#   answer_text                           shortanswer, multianswer
#   case_sensitive     true|false         shortanswer
#   true_false         true|false         truefalse
#   numerical_answer                      numerical
#   tolerance                             numerical, calculated*
#   match_pairs        "left=right|l=r"   match
#   ordering_items     "first|second"     ordering (correct order)
#   gaps               "1:*c|w;2:w|*c"    selectmissing (* = correct)
#   content                             description (defaults to
#                                       question_text when empty)
#   max_words                           essay
#   formula                             calculated* ({a} placeholders)
#   units                               calculated*
#   datasets             "a=1-10@2|b=5-20"  calculated* (name=min-max@dec)
#   language             python|c|cpp|java  coding (required)
#   starter_code                        coding
#   time_limit           seconds        coding
#   test_cases           "in=>out@marks|!in=>out"  coding (! = hidden)
#   children             "name1|name2"    paragraph — optional; names
#                                       must appear earlier in the CSV
#                                       or already exist; blank = link
#                                       later from the UI
#   image_url, alt_text                 image (main image)
#
# 'random' is the only shell type — it is resolved when the exam is
# taken, so no answer data exists to import.

CSV_QCOLS_REQUIRED = {"name", "type", "question_text"}

OPTION_TYPES_CSV = {"multichoice", "multiselect", "image"}
CALC_TYPES_CSV = {"calculated", "calculatedsimple", "calculatedmulti"}
SHELL_TYPES_CSV = {"random"}


def _csv_truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "y")


def _csv_decimal(value: str, field: str, row_no: int):
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError):
        raise ValueError(
            f"row {row_no}: '{value}' is not a valid number for {field}"
        )


def _build_question_type_data(
    qtype: str, row: dict, row_no: int,
    db: Session, name_map: dict,
) -> list:
    """Build the type-specific child objects for one CSV row.

    Returns a list of (unsaved) ORM objects; the caller assigns
    question_id once the question row is flushed. CodingTestCase
    objects carry a `_cq` link to their parent CodingQuestion — the
    caller resolves it after that parent is flushed. Raises
    ValueError with a human-readable reason on bad input — nothing
    touches the session on failure.
    """
    t = qtype
    children = []

    if t in OPTION_TYPES_CSV:
        options = [
            o.strip()
            for o in row.get("options", "").split("|")
            if o.strip()
        ]
        if len(options) < 2:
            raise ValueError("needs at least 2 options in 'options' (| separated)")

        correct_raw = [
            c.strip()
            for c in row.get("correct_options", "").split("|")
            if c.strip()
        ]
        try:
            correct = {int(c) for c in correct_raw}
        except ValueError:
            raise ValueError(
                "'correct_options' must be option numbers like 1 or 1|3"
            )

        if not correct or min(correct) < 1 or max(correct) > len(options):
            raise ValueError(
                f"'correct_options' indexes must be between 1 and {len(options)}"
            )
        if t in ("multichoice", "image") and len(correct) != 1:
            raise ValueError("this type needs exactly one correct option")
        if t == "multiselect" and len(correct) < 1:
            raise ValueError("multiselect needs at least one correct option")

        for i, text in enumerate(options, start=1):
            is_correct = i in correct
            children.append(QuestionOption(
                option_text=text,
                is_correct=is_correct,
                fraction=100 if is_correct else 0,
                sort_order=i,
            ))

        # Image questions can also carry a main image URL.
        if t == "image" and row.get("image_url", "").strip():
            children.append(QuestionImage(
                image_url=row["image_url"].strip(),
                alt_text=row.get("alt_text", "").strip() or None,
                position=0,
            ))

    elif t == "truefalse":
        raw = row.get("true_false", "").strip().lower()
        if raw not in ("true", "false"):
            raise ValueError("'true_false' must be 'true' or 'false'")
        children.append(QuestionTrueFalse(
            true_answer=(raw == "true"),
            false_answer=(raw != "true"),
        ))

    elif t == "shortanswer":
        answer = row.get("answer_text", "").strip()
        if not answer:
            raise ValueError("'answer_text' is required")
        children.append(QuestionShortAnswer(
            answer_text=answer,
            case_sensitive=_csv_truthy(row.get("case_sensitive", "")),
        ))

    elif t == "numerical":
        answer = row.get("numerical_answer", "").strip()
        if not answer:
            raise ValueError("'numerical_answer' is required")
        tol_raw = row.get("tolerance", "").strip()
        tolerance = (
            _csv_decimal(tol_raw, "tolerance", row_no)
            if tol_raw else Decimal("0")
        )
        if tolerance < 0:
            raise ValueError("'tolerance' cannot be negative")
        children.append(QuestionNumerical(
            answer_value=_csv_decimal(answer, "numerical_answer", row_no),
            tolerance=tolerance,
        ))

    elif t == "multianswer":
        answer = row.get("answer_text", "").strip()
        if not answer:
            raise ValueError("'answer_text' is required")
        children.append(QuestionMultiAnswer(answer_text=answer))

    elif t == "match":
        pairs = [
            p.strip()
            for p in row.get("match_pairs", "").split("|")
            if p.strip()
        ]
        if not pairs:
            raise ValueError(
                "'match_pairs' is required, e.g. left=right|l2=r2"
            )
        for i, pair in enumerate(pairs, start=1):
            if "=" not in pair:
                raise ValueError(f"match pair '{pair}' is missing '='")
            left, right = pair.split("=", 1)
            if not left.strip() or not right.strip():
                raise ValueError(f"match pair '{pair}' has an empty side")
            children.append(QuestionMatch(
                sub_question=left.strip(),
                sub_answer=right.strip(),
                sort_order=i,
            ))

    elif t == "ordering":
        items = [
            s.strip()
            for s in row.get("ordering_items", "").split("|")
            if s.strip()
        ]
        if len(items) < 2:
            raise ValueError(
                "needs at least 2 'ordering_items' in correct order (| separated)"
            )
        for i, text in enumerate(items, start=1):
            children.append(QuestionOrdering(item_text=text, position=i))

    elif t == "selectmissing":
        gaps_raw = row.get("gaps", "").strip()
        if not gaps_raw:
            raise ValueError(
                "'gaps' is required, e.g. 1:*sun|moon;2:cat|*dog"
            )
        for chunk in gaps_raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ":" not in chunk:
                raise ValueError(f"gap '{chunk}' must look like blank:opt1|opt2")
            blank_raw, opts_raw = chunk.split(":", 1)
            try:
                blank_no = int(blank_raw)
            except ValueError:
                raise ValueError(f"gap '{chunk}' has a non-numeric blank number")
            opts = [o for o in opts_raw.split("|") if o.strip()]
            if len(opts) < 2:
                raise ValueError(f"blank {blank_no} needs at least 2 options")
            correct_seen = 0
            for i, opt in enumerate(opts, start=1):
                opt = opt.strip()
                is_correct = opt.startswith("*")
                if is_correct:
                    correct_seen += 1
                    opt = opt[1:].strip()
                children.append(QuestionGapSelect(
                    blank_no=blank_no,
                    option_text=opt,
                    is_correct=is_correct,
                    sort_order=i,
                ))
            if correct_seen != 1:
                raise ValueError(
                    f"blank {blank_no} must mark exactly one correct option with '*'"
                )

    elif t == "essay":
        mw_raw = row.get("max_words", "").strip()
        max_words = None
        if mw_raw:
            try:
                max_words = int(mw_raw)
            except ValueError:
                raise ValueError("'max_words' must be a whole number")
            if max_words <= 0:
                raise ValueError("'max_words' must be greater than zero")
        children.append(QuestionEssay(
            response_format="plain",
            max_words=max_words,
        ))

    elif t == "description":
        children.append(QuestionDescription(
            content=row.get("content", "").strip()
            or row.get("question_text", "").strip()
        ))

    elif t in CALC_TYPES_CSV:
        formula = row.get("formula", "").strip()
        if not formula:
            raise ValueError("'formula' is required, e.g. {a}+{b}")
        tol_raw = row.get("tolerance", "").strip()
        tolerance = (
            _csv_decimal(tol_raw, "tolerance", row_no)
            if tol_raw else Decimal("0")
        )
        if tolerance < 0:
            raise ValueError("'tolerance' cannot be negative")

        datasets = []
        ds_raw = row.get("datasets", "").strip()
        for chunk in [c for c in ds_raw.split("|") if c.strip()]:
            # name=min-max@decimals   (@decimals optional)
            body, _, dec = chunk.partition("@")
            if "=" not in body or "-" not in body:
                raise ValueError(
                    f"dataset '{chunk}' must look like name=min-max@decimals"
                )
            dname, rng = body.split("=", 1)
            lo, _, hi = rng.partition("-")
            try:
                datasets.append({
                    "name": dname.strip(),
                    "min": float(lo),
                    "max": float(hi),
                    "decimals": int(dec) if dec.strip() else 0,
                })
            except ValueError:
                raise ValueError(
                    f"dataset '{chunk}' has a non-numeric min/max/decimals"
                )
            if datasets[-1]["min"] > datasets[-1]["max"]:
                raise ValueError(
                    f"dataset '{dname.strip()}': min exceeds max"
                )

        children.append(QuestionCalculated(
            formula=formula,
            tolerance=tolerance,
            units=row.get("units", "").strip() or None,
            datasets=datasets or None,
        ))

    elif t == "coding":
        language = row.get("language", "").strip().lower()
        if not language:
            raise ValueError("'language' is required, e.g. python")
        tl_raw = row.get("time_limit", "").strip()
        try:
            time_limit = int(tl_raw) if tl_raw else 5
        except ValueError:
            raise ValueError("'time_limit' must be a whole number")
        cq = CodingQuestion(
            language=language,
            starter_code=row.get("starter_code", "").strip() or None,
            time_limit=time_limit,
        )
        children.append(cq)

        cases_raw = row.get("test_cases", "").strip()
        for i, chunk in enumerate(
            [c for c in cases_raw.split("|") if c.strip()], start=1
        ):
            hidden = chunk.strip().startswith("!")
            if hidden:
                chunk = chunk.strip()[1:]
            if "=>" not in chunk:
                raise ValueError(
                    f"test case '{chunk}' must look like input=>expected@marks"
                )
            left, right = chunk.split("=>", 1)
            expected, _, marks_raw = right.rpartition("@")
            try:
                marks = (
                    _csv_decimal(marks_raw, "test case marks", row_no)
                    if marks_raw else Decimal("1")
                )
            except ValueError:
                # no @marks suffix — the 'right' side *is* the output
                expected, marks = right, Decimal("1")
            tc = CodingTestCase(
                input_text=left.strip() or None,
                expected_output=expected.strip(),
                is_hidden=hidden,
                marks=marks,
                sort_order=i,
            )
            tc._cq = cq  # resolved to coding_question_id after flush
            children.append(tc)

    elif t == "paragraph":
        names = [
            c.strip()
            for c in row.get("children", "").split("|")
            if c.strip()
        ]
        # 'children' may be left blank — the paragraph is imported as
        # an unlinked shell and questions are linked later from the
        # paragraph settings in the UI.
        child_ids = []
        for cname in names:
            cid = None
            if cname.isdigit():
                cid = int(cname)
                exists = db.query(Question.id).filter(
                    Question.id == cid,
                    Question.is_active.is_(True),
                ).first()
                if not exists:
                    raise ValueError(f"child question id {cid} not found")
            else:
                # try questions created earlier in this same CSV first
                cid = name_map.get(cname.lower())
                if cid is None:
                    match = db.query(Question).filter(
                        Question.name.ilike(cname),
                        Question.is_active.is_(True),
                    ).first()
                    if not match:
                        raise ValueError(
                            f"child question '{cname}' not found "
                            "(name must match an existing question)"
                        )
                    cid = match.id
                child = db.query(Question).get(cid)
                if child and child.type in ("paragraph", "description"):
                    raise ValueError(
                        f"'{cname}' ({child.type}) cannot be a paragraph child"
                    )
            if cid in child_ids:
                continue
            child_ids.append(cid)
        # Empty children list is fine — the paragraph can be linked
        # later from the question's paragraph settings in the UI.
        children.append(QuestionParagraph(
            child_question_ids=child_ids or None
        ))

    elif t in SHELL_TYPES_CSV:
        pass  # 'random' is resolved at exam time — nothing to import

    else:
        raise ValueError(f"unsupported question type '{t}'")

    return children


@router.post("/bulk-upload")
def bulk_upload_questions(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are accepted",
        )

    raw = file.file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file too large (max 2 MB)",
        )

    try:
        text = raw.decode("utf-8-sig")  # strips Excel BOM
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not valid UTF-8 text",
        )

    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    missing = CSV_QCOLS_REQUIRED - headers
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Missing required column(s): {', '.join(sorted(missing))}. "
                "Expected at least: name,type,category,question_text"
            ),
        )
    if "category" not in headers and "category_id" not in headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provide a 'category' column with the category name "
                "(it is created automatically if it does not exist)."
            ),
        )

    cat_by_name = {}
    cat_ids = set()
    for c in db.query(QuestionCategory).all():
        cat_ids.add(c.id)
        cat_by_name.setdefault(c.name.strip().lower(), c.id)

    created_categories = []

    # question name -> id, for rows that reference earlier CSV rows
    # (e.g. paragraph 'children' column)
    name_map = {}

    created = []
    errors = []

    for row_no, raw_row in enumerate(reader, start=2):  # row 1 = header
        row = {
            (k.strip().lower() if k else k): (v.strip() if v else "")
            for k, v in raw_row.items()
        }

        name = row.get("name", "")
        qtype = row.get("type", "").lower()
        qtext = row.get("question_text", "")

        # Skip completely empty lines silently.
        if not any(v for v in row.values()):
            continue

        try:
            # Paragraph: 'content' is the passage students read — the
            # question itself is ungraded. It overrides question_text
            # when both are present (same precedence as 'description').
            if qtype == "paragraph":
                qtext = row.get("content", "").strip() or qtext

            if not name or not qtype or not qtext:
                raise ValueError("name, type and question_text are required")

            if qtype not in QUESTION_TYPES:
                raise ValueError(f"invalid type '{qtype}'")

            cat_name = row.get("category", "")
            if cat_name:
                key = cat_name.strip().lower()
                category_id = cat_by_name.get(key)
                if category_id is None:
                    # Teacher-friendly: create the category on the fly.
                    cat = QuestionCategory(
                        name=cat_name.strip(),
                        created_by=current_user.id,
                    )
                    db.add(cat)
                    db.flush()
                    category_id = cat.id
                    cat_by_name[key] = category_id
                    cat_ids.add(category_id)
                    created_categories.append(cat_name.strip())
            else:
                try:
                    category_id = int(row.get("category_id", ""))
                except ValueError:
                    raise ValueError(
                        "'category' (name) is required, or a numeric 'category_id'"
                    )
                if category_id not in cat_ids:
                    raise ValueError(f"category {category_id} not found")

            mark_raw = row.get("default_mark", "").strip()
            if mark_raw:
                mark = _csv_decimal(mark_raw, "default_mark", row_no)
            else:
                mark = Decimal("0") if qtype in (
                    "description", "paragraph"
                ) else Decimal("1")

            if mark <= 0 and qtype not in ("description", "paragraph"):
                raise ValueError("'default_mark' must be greater than zero")

            # Validates and builds children before touching the session.
            children = _build_question_type_data(
                qtype, row, row_no, db, name_map
            )

            question = Question(
                category_id=category_id,
                type=qtype,
                name=name,
                question_text=qtext,
                default_mark=mark,
                general_feedback=row.get("general_feedback") or None,
                created_by=current_user.id,
                is_active=True,
            )
            db.add(question)
            db.flush()  # assign question.id for the type-specific rows
            name_map[name.lower()] = question.id

            deferred = []
            for child in children:
                if isinstance(child, CodingTestCase):
                    deferred.append(child)
                else:
                    child.question_id = question.id
                    db.add(child)
            if deferred:
                db.flush()  # CodingQuestion gets its PK
                for tc in deferred:
                    tc.coding_question_id = tc._cq.id
                    del tc._cq
                    db.add(tc)

            created.append({"row": row_no, "name": name, "type": qtype})

        except ValueError as e:
            errors.append(
                {"row": row_no, "name": name or "-", "reason": str(e)}
            )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database rejected some rows; no questions were created",
        )

    if created:
        log_audit(
            db, current_user.id, "question.bulk_create", "question", None,
            details=(
                f"{len(created)} questions from {file.filename}; "
                f"new categories: {', '.join(created_categories) or 'none'}"
            ),
        )
        db.commit()

    return {
        "created_count": len(created),
        "error_count": len(errors),
        "created": created,
        "errors": errors,
        "created_categories": created_categories,
    }


@router.post(
    "/bulk-import",
    response_model=BulkQuestionImportResponse
)
def bulk_import_questions(
    data: BulkQuestionImportRequest,
    current_user: User = Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    imported_ids = []
    errors = []
    valid_questions = []

    # Validate all questions first
    for index, item in enumerate(data.questions, start=1):

        if item.type not in QUESTION_TYPES:
            errors.append({
                "row": index,
                "error": f"Invalid question type: {item.type}"
            })
            continue

        category = db.query(QuestionCategory).filter(
            QuestionCategory.id == item.category_id
        ).first()

        if not category:
            errors.append({
                "row": index,
                "error": f"Category {item.category_id} not found"
            })
            continue

        valid_questions.append(item)

    # Insert valid questions
    try:
        created_questions = []

        for item in valid_questions:
            question = Question(
                category_id=item.category_id,
                type=item.type,
                name=item.name,
                question_text=item.question_text,
                default_mark=item.default_mark,
                general_feedback=item.general_feedback,
                created_by=current_user.id,
                is_active=True
            )

            db.add(question)
            created_questions.append(question)

        db.flush()

        # Get IDs from the inserted objects
        imported_ids = [
            question.id for question in created_questions
        ]

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Bulk import failed. No questions were imported."
        )

    return {
        "imported_count": len(imported_ids),
        "failed_count": len(errors),
        "errors": errors,
        "imported_question_ids": imported_ids
    }


# EXPORT QUESTIONS TO CSV
@router.get("/export/csv")
def export_questions_csv(
    category_id: int | None = None,
    question_type: str | None = None,
    current_user: User = Depends(
        require_role("admin", "teacher")
    ),
    db: Session = Depends(get_db)
):
    query = db.query(Question).filter(
        Question.is_active == True
    )

    if category_id is not None:
        query = query.filter(
            Question.category_id == category_id
        )

    if question_type is not None:
        if question_type not in QUESTION_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Invalid question type"
            )

        query = query.filter(
            Question.type == question_type
        )

    questions = query.order_by(Question.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id",
        "category_id",
        "type",
        "name",
        "question_text",
        "default_mark",
        "general_feedback"
    ])

    for question in questions:
        writer.writerow([
            question.id,
            question.category_id,
            question.type,
            question.name,
            question.question_text,
            question.default_mark,
            question.general_feedback or ""
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                'attachment; filename="question_bank.csv"'
        }
    )