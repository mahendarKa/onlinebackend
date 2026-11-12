import json
from decimal import Decimal

"""Question change-approval helpers.

Rules enforced here (mirroring the product requirements):

* A question used in an exam that already has attempts is locked — it
  cannot be modified or deleted by anyone.
* Any other edit/delete made by a non-admin becomes a
  QuestionChangeRequest (status ``pending``) and is applied only after
  an admin approves it.
* While a question has a pending request it is frozen, and every exam
  containing it is blocked for students until the request is resolved.
"""

from fastapi import HTTPException

from app.models.exam import Exam, ExamQuestion
from app.models.exam_attempt import ExamAttempt
from app.models.question import Question
from app.models.question_change_request import QuestionChangeRequest
from app.models.question_option import QuestionOption
from app.models.question_truefalse import QuestionTrueFalse
from app.models.question_shortanswer import QuestionShortAnswer
from app.models.question_numerical import QuestionNumerical
from app.models.question_essay import QuestionEssay
from app.models.question_multianswer import QuestionMultiAnswer
from app.models.question_match import QuestionMatch
from app.models.question_gapselect import QuestionGapSelect
from app.models.question_ordering import QuestionOrdering
from app.models.question_calculated import QuestionCalculated
from app.models.question_description import QuestionDescription
from app.models.question_image import QuestionImage
from app.models.question_paragraph import QuestionParagraph
from app.models.paragraph_question import ParagraphQuestion
from app.models.coding_question import CodingQuestion, CodingTestCase
from app.services.activity_service import admin_ids, notify, notify_many
from app.utils.time import utcnow

ATTEMPTED_EXAM_MSG = (
    "This question is part of an exam that students have already "
    "attempted, so it cannot be modified or deleted."
)

PENDING_MSG = (
    "This question already has a change request pending admin approval."
)

EXAM_PENDING_MSG = (
    "This exam is under pending status. "
    "Please wait for admin approval."
)


def attempted_exam_ids_for_question(db, question_id: int) -> set[int]:
    """Ids of exams containing the question that have ≥1 attempt."""
    rows = (
        db.query(ExamQuestion.exam_id)
        .join(ExamAttempt, ExamAttempt.exam_id == ExamQuestion.exam_id)
        .filter(ExamQuestion.question_id == question_id)
        .distinct()
        .all()
    )
    return {r.exam_id for r in rows}


def pending_request_for(db, question_id: int):
    return (
        db.query(QuestionChangeRequest)
        .filter(
            QuestionChangeRequest.question_id == question_id,
            QuestionChangeRequest.status == "pending",
        )
        .first()
    )


def exams_with_pending_questions(db, exam_ids: list[int]) -> set[int]:
    """Exam ids (from ``exam_ids``) containing a question that has a
    pending change request."""
    if not exam_ids:
        return set()
    rows = (
        db.query(ExamQuestion.exam_id)
        .join(
            QuestionChangeRequest,
            QuestionChangeRequest.question_id == ExamQuestion.question_id,
        )
        .filter(
            ExamQuestion.exam_id.in_(exam_ids),
            QuestionChangeRequest.status == "pending",
        )
        .distinct()
        .all()
    )
    return {r.exam_id for r in rows}


def ensure_question_editable(db, question_id: int, user=None):
    """Raise when the question cannot be modified right now.

    Used by the subtype routers' write endpoints: attempted exams lock a
    question for everyone and a pending request freezes it for everyone
    until resolved.
    """
    if attempted_exam_ids_for_question(db, question_id):
        raise HTTPException(status_code=400, detail=ATTEMPTED_EXAM_MSG)
    if pending_request_for(db, question_id):
        raise HTTPException(status_code=400, detail=PENDING_MSG)


def create_change_request(db, question: Question, action: str,
                          payload: dict | None, user) -> QuestionChangeRequest:
    """Queue an edit/delete for admin approval and notify admins."""
    # JSON columns can't store Decimals/datetimes — coerce via a
    # json round-trip so payload stores plain primitives.
    safe_payload = (
        json.loads(json.dumps(payload, default=str))
        if payload is not None else None
    )
    request = QuestionChangeRequest(
        question_id=question.id,
        action=action,
        payload=safe_payload,
        status="pending",
        requested_by=user.id,
    )
    db.add(request)
    db.flush()

    verb = "deletion" if action == "delete" else "update"
    notify_many(
        db,
        admin_ids(db),
        f"Question {verb} requested",
        f"{user.name} requested {verb} of question "
        f"{question.id} ({question.name}).",
        "question.change_request",
        link="/admin/approvals",
    )
    return request


# --------------------------------------------------
# Applying an approved update payload
# --------------------------------------------------
#
# ``full_state`` payloads (sent by the question editor) describe the
# complete desired state: every subtype table is wiped for the question
# and rebuilt from the payload. Partial payloads only touch the keys
# they carry — subtype keys present replace that subtype's rows; keys
# absent are left untouched.

def _wipe_subtypes(db, question_id: int):
    for model in (
        QuestionOption, QuestionTrueFalse, QuestionShortAnswer,
        QuestionNumerical, QuestionEssay, QuestionMultiAnswer,
        QuestionMatch, QuestionGapSelect, QuestionOrdering,
        QuestionCalculated, QuestionDescription, QuestionImage,
        QuestionParagraph,
    ):
        db.query(model).filter(
            model.question_id == question_id
        ).delete(synchronize_session=False)

    coding = db.query(CodingQuestion).filter(
        CodingQuestion.question_id == question_id
    ).first()
    if coding:
        db.query(CodingTestCase).filter(
            CodingTestCase.coding_question_id == coding.id
        ).delete(synchronize_session=False)
        db.delete(coding)


def _apply_subtypes(db, question_id: int, payload: dict):
    if "options" in payload:
        db.query(QuestionOption).filter(
            QuestionOption.question_id == question_id
        ).delete(synchronize_session=False)
        for i, o in enumerate(payload["options"]):
            db.add(QuestionOption(
                question_id=question_id,
                option_text=o.get("option_text") or "",
                image_url=o.get("image_url"),
                is_correct=bool(o.get("is_correct")),
                fraction=o.get("fraction") or 0,
                sort_order=o.get("sort_order", i),
            ))

    if "truefalse" in payload:
        d = payload["truefalse"] or {}
        db.query(QuestionTrueFalse).filter(
            QuestionTrueFalse.question_id == question_id
        ).delete(synchronize_session=False)
        db.add(QuestionTrueFalse(
            question_id=question_id,
            true_answer=bool(d.get("true_answer")),
            false_answer=not bool(d.get("true_answer")),
        ))

    if "shortanswer" in payload:
        d = payload["shortanswer"] or {}
        db.query(QuestionShortAnswer).filter(
            QuestionShortAnswer.question_id == question_id
        ).delete(synchronize_session=False)
        db.add(QuestionShortAnswer(
            question_id=question_id,
            answer_text=d.get("answer_text") or "",
            case_sensitive=bool(d.get("case_sensitive")),
        ))

    if "numerical" in payload:
        d = payload["numerical"] or {}
        db.query(QuestionNumerical).filter(
            QuestionNumerical.question_id == question_id
        ).delete(synchronize_session=False)
        db.add(QuestionNumerical(
            question_id=question_id,
            answer_value=d.get("answer_value") or 0,
            tolerance=d.get("tolerance") or 0,
        ))

    if "essay" in payload:
        d = payload["essay"] or {}
        db.query(QuestionEssay).filter(
            QuestionEssay.question_id == question_id
        ).delete(synchronize_session=False)
        db.add(QuestionEssay(
            question_id=question_id,
            max_words=d.get("max_words"),
        ))

    if "multianswer" in payload:
        d = payload["multianswer"] or {}
        db.query(QuestionMultiAnswer).filter(
            QuestionMultiAnswer.question_id == question_id
        ).delete(synchronize_session=False)
        db.add(QuestionMultiAnswer(
            question_id=question_id,
            answer_text=d.get("answer_text") or "",
            answer_format=d.get("answer_format") or "text",
        ))

    if "match" in payload:
        db.query(QuestionMatch).filter(
            QuestionMatch.question_id == question_id
        ).delete(synchronize_session=False)
        for i, m in enumerate(payload["match"]):
            db.add(QuestionMatch(
                question_id=question_id,
                sub_question=m.get("sub_question") or "",
                sub_answer=m.get("sub_answer") or "",
                sort_order=m.get("sort_order", i),
            ))

    if "gapselect" in payload:
        db.query(QuestionGapSelect).filter(
            QuestionGapSelect.question_id == question_id
        ).delete(synchronize_session=False)
        for i, o in enumerate(payload["gapselect"]):
            db.add(QuestionGapSelect(
                question_id=question_id,
                blank_no=o.get("blank_no") or 1,
                option_text=o.get("option_text") or "",
                is_correct=bool(o.get("is_correct")),
                sort_order=o.get("sort_order", i),
            ))

    if "ordering" in payload:
        db.query(QuestionOrdering).filter(
            QuestionOrdering.question_id == question_id
        ).delete(synchronize_session=False)
        for i, o in enumerate(payload["ordering"]):
            db.add(QuestionOrdering(
                question_id=question_id,
                item_text=o.get("item_text") or "",
                position=o.get("position", i + 1),
            ))

    if "calculated" in payload:
        d = payload["calculated"] or {}
        db.query(QuestionCalculated).filter(
            QuestionCalculated.question_id == question_id
        ).delete(synchronize_session=False)
        db.add(QuestionCalculated(
            question_id=question_id,
            formula=d.get("formula") or "",
            tolerance=d.get("tolerance") or 0,
            units=d.get("units"),
            datasets=d.get("datasets"),
        ))

    if "description" in payload:
        d = payload["description"] or {}
        db.query(QuestionDescription).filter(
            QuestionDescription.question_id == question_id
        ).delete(synchronize_session=False)
        db.add(QuestionDescription(
            question_id=question_id,
            content=d.get("content") or "",
        ))

    if "images" in payload:
        db.query(QuestionImage).filter(
            QuestionImage.question_id == question_id
        ).delete(synchronize_session=False)
        for i, img in enumerate(payload["images"]):
            if not img.get("image_url"):
                continue
            db.add(QuestionImage(
                question_id=question_id,
                image_url=img["image_url"],
                alt_text=img.get("alt_text"),
                position=img.get("position", i),
            ))

    if "paragraph" in payload:
        d = payload["paragraph"] or {}
        db.query(QuestionParagraph).filter(
            QuestionParagraph.question_id == question_id
        ).delete(synchronize_session=False)
        ids = list(dict.fromkeys(d.get("question_ids") or []))
        if ids:
            cfg = db.query(QuestionParagraph).filter(
                QuestionParagraph.question_id == question_id
            ).first()
            if not cfg:
                cfg = QuestionParagraph(question_id=question_id)
                db.add(cfg)
            cfg.child_question_ids = ids

    if "coding" in payload:
        d = payload["coding"] or {}
        coding = db.query(CodingQuestion).filter(
            CodingQuestion.question_id == question_id
        ).first()
        if coding:
            db.query(CodingTestCase).filter(
                CodingTestCase.coding_question_id == coding.id
            ).delete(synchronize_session=False)
            coding.language = d.get("language") or coding.language
            coding.starter_code = d.get("starter_code")
            coding.time_limit = d.get("time_limit") or coding.time_limit
        else:
            coding = CodingQuestion(
                question_id=question_id,
                language=d.get("language") or "python",
                starter_code=d.get("starter_code"),
                time_limit=d.get("time_limit") or 5,
            )
            db.add(coding)
            db.flush()
        for i, tc in enumerate(d.get("test_cases") or []):
            if not tc.get("expected_output"):
                continue
            db.add(CodingTestCase(
                coding_question_id=coding.id,
                input_text=tc.get("input_text"),
                expected_output=tc["expected_output"],
                is_hidden=bool(tc.get("is_hidden")),
                marks=tc.get("marks") or 1,
                sort_order=tc.get("sort_order", i),
            ))


def apply_change_request(db, request: QuestionChangeRequest):
    """Apply the queued change. Caller sets status/reviewer afterwards."""
    question = db.query(Question).filter(
        Question.id == request.question_id
    ).first()
    if not question:
        return

    if request.action == "delete":
        from app.routers.questions import perform_question_delete
        perform_question_delete(db, question)
        return

    payload = request.payload or {}
    base = payload.get("base") or {}

    if payload.get("full_state"):
        _wipe_subtypes(db, question.id)

    for field in (
        "category_id", "type", "name", "question_text",
        "default_mark", "general_feedback", "is_active",
    ):
        if field in base and base[field] is not None:
            value = base[field]
            if field == "default_mark":
                value = Decimal(str(value))
            setattr(question, field, value)

    _apply_subtypes(db, question.id, payload)


def resolve_request(db, request: QuestionChangeRequest,
                    status_value: str, reviewer, note: str | None = None):
    request.status = status_value
    request.reviewed_by = reviewer.id
    request.reviewed_at = utcnow()
    request.review_note = note

    question = db.query(Question).filter(
        Question.id == request.question_id
    ).first()
    qname = question.name if question else f"#{request.question_id}"
    verb = "deletion" if request.action == "delete" else "update"
    approved = status_value == "approved"
    notify(
        db,
        request.requested_by,
        f"Question {verb} {'approved' if approved else 'rejected'}",
        f"Your {verb} request for question {request.question_id} "
        f"({qname}) was {'approved' if approved else 'rejected'}"
        f"{f': {note}' if note else ''}.",
        "question.change_resolved",
        link="/questions",
    )


# --------------------------------------------------
# Current-state snapshot (for the approvals diff)
# --------------------------------------------------
#
# Emits the question's current state in the same shape as the staged
# ``full_state`` payload so the approvals UI can diff old vs new.

def question_snapshot(db, question: Question) -> dict:
    snap = {
        "base": {
            "category_id": question.category_id,
            "name": question.name,
            "question_text": question.question_text,
            "default_mark": float(question.default_mark or 0),
        }
    }

    rows = db.query(QuestionOption).filter(
        QuestionOption.question_id == question.id
    ).order_by(QuestionOption.sort_order).all()
    if rows:
        snap["options"] = [{
            "option_text": o.option_text,
            "image_url": o.image_url,
            "is_correct": o.is_correct,
            "fraction": float(o.fraction or 0),
            "sort_order": o.sort_order,
        } for o in rows]

    row = db.query(QuestionTrueFalse).filter(
        QuestionTrueFalse.question_id == question.id
    ).first()
    if row:
        snap["truefalse"] = {"true_answer": row.true_answer}

    row = db.query(QuestionShortAnswer).filter(
        QuestionShortAnswer.question_id == question.id
    ).first()
    if row:
        snap["shortanswer"] = {
            "answer_text": row.answer_text,
            "case_sensitive": row.case_sensitive,
        }

    row = db.query(QuestionNumerical).filter(
        QuestionNumerical.question_id == question.id
    ).first()
    if row:
        snap["numerical"] = {
            "answer_value": float(row.answer_value or 0),
            "tolerance": float(row.tolerance or 0),
        }

    row = db.query(QuestionEssay).filter(
        QuestionEssay.question_id == question.id
    ).first()
    if row:
        snap["essay"] = {"max_words": row.max_words}

    row = db.query(QuestionMultiAnswer).filter(
        QuestionMultiAnswer.question_id == question.id
    ).first()
    if row:
        snap["multianswer"] = {
            "answer_text": row.answer_text,
            "answer_format": row.answer_format,
        }

    rows = db.query(QuestionMatch).filter(
        QuestionMatch.question_id == question.id
    ).order_by(QuestionMatch.sort_order).all()
    if rows:
        snap["match"] = [{
            "sub_question": m.sub_question,
            "sub_answer": m.sub_answer,
            "sort_order": m.sort_order,
        } for m in rows]

    rows = db.query(QuestionGapSelect).filter(
        QuestionGapSelect.question_id == question.id
    ).order_by(
        QuestionGapSelect.blank_no, QuestionGapSelect.sort_order
    ).all()
    if rows:
        snap["gapselect"] = [{
            "blank_no": g.blank_no,
            "option_text": g.option_text,
            "is_correct": g.is_correct,
            "sort_order": g.sort_order,
        } for g in rows]

    rows = db.query(QuestionOrdering).filter(
        QuestionOrdering.question_id == question.id
    ).order_by(QuestionOrdering.position).all()
    if rows:
        snap["ordering"] = [{
            "item_text": o.item_text,
            "position": o.position,
        } for o in rows]

    row = db.query(QuestionCalculated).filter(
        QuestionCalculated.question_id == question.id
    ).first()
    if row:
        snap["calculated"] = {
            "formula": row.formula,
            "tolerance": float(row.tolerance or 0),
            "units": row.units,
            "datasets": row.datasets,
        }

    row = db.query(QuestionDescription).filter(
        QuestionDescription.question_id == question.id
    ).first()
    if row:
        snap["description"] = {"content": row.content}

    rows = db.query(QuestionImage).filter(
        QuestionImage.question_id == question.id
    ).order_by(QuestionImage.position).all()
    if rows:
        snap["images"] = [{
            "image_url": i.image_url,
            "alt_text": i.alt_text,
            "position": i.position,
        } for i in rows]

    row = db.query(QuestionParagraph).filter(
        QuestionParagraph.question_id == question.id
    ).first()
    if row:
        snap["paragraph"] = {
            "question_ids": row.child_question_ids or [],
        }

    coding = db.query(CodingQuestion).filter(
        CodingQuestion.question_id == question.id
    ).first()
    if coding:
        cases = db.query(CodingTestCase).filter(
            CodingTestCase.coding_question_id == coding.id
        ).order_by(CodingTestCase.sort_order).all()
        snap["coding"] = {
            "language": coding.language,
            "starter_code": coding.starter_code,
            "time_limit": coding.time_limit,
            "test_cases": [{
                "input_text": tc.input_text,
                "expected_output": tc.expected_output,
                "is_hidden": tc.is_hidden,
                "marks": float(tc.marks or 0),
                "sort_order": tc.sort_order,
            } for tc in cases],
        }

    return snap
