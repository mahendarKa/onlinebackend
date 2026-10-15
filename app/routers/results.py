
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam, ExamQuestion
from app.models.exam_attempt import ExamAttempt, StudentAnswer, ExamResult
from app.models.question import Question
from app.models.question_calculated import QuestionCalculated
from app.models.question_image import QuestionImage
from app.models.question_gapselect import QuestionGapSelect
from app.models.question_match import QuestionMatch
from app.models.question_multianswer import QuestionMultiAnswer
from app.models.question_ordering import QuestionOrdering
from app.models.question_numerical import QuestionNumerical
from app.models.question_option import QuestionOption
from app.models.question_shortanswer import QuestionShortAnswer
from app.models.question_truefalse import QuestionTrueFalse
from app.models.user import User
from app.schemas.result import ManualEvaluationRequest
from app.services.evaluation_service import (
    answer_has_content,
    calculated_wildcards,
    eval_formula,
    substitute_wildcards,
    wildcard_values,
)
from app.utils.dependencies import require_role
from app.utils.permissions import (
    is_admin,
    require_exam_grade,
    teacher_gradeable_exam_ids,
)
from app.services.activity_service import log_audit, notify

router = APIRouter(prefix="/api/results", tags=["Results"])

teacher_admin = Depends(require_role("admin", "teacher"))
student_only = Depends(require_role("student"))


def get_answer(answer_id: int, db: Session):
    answer = db.query(StudentAnswer).filter(
        StudentAnswer.id == answer_id
    ).first()

    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    return answer


def recalculate_result(attempt: ExamAttempt, db: Session):
    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()

    items = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == attempt.exam_id
    ).all()

    # Map only live questions: deleted (is_active=False) or removed
    # questions no longer count toward the result.
    question_types = {
        q.id: q.type for q in db.query(Question).filter(
            Question.id.in_([i.question_id for i in items]),
            Question.is_active.is_(True),
        ).all()
    }

    # Description/paragraph items are informational text, not questions.
    items = [
        i for i in items
        if i.question_id in question_types
        and question_types[i.question_id] not in ("description", "paragraph")
    ]

    answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_attempt_id == attempt.id
    ).all()

    answer_map = {a.question_id: a for a in answers}

    attempted = correct = wrong = 0
    total_marks = Decimal("0.00")
    pending_manual = False

    for item in items:
        answer = answer_map.get(item.question_id)

        if not answer:
            continue

        if not answer_has_content(answer):
            continue

        attempted += 1

        if answer.marks_obtained is not None:
            total_marks += Decimal(str(answer.marks_obtained))
        else:
            pending_manual = True

        if answer.is_correct is True:
            correct += 1
        elif answer.is_correct is False:
            wrong += 1

    skipped = len(items) - attempted
    maximum_marks = Decimal(str(exam.total_marks))
    percentage = (
        (total_marks / maximum_marks * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if maximum_marks > 0
        else Decimal("0.00")
    )

    result = db.query(ExamResult).filter(
        ExamResult.exam_attempt_id == attempt.id
    ).first()

    if not result:
        result = ExamResult(exam_attempt_id=attempt.id)
        db.add(result)

    result.total_questions = len(items)
    result.attempted = attempted
    result.correct = correct
    result.wrong = wrong
    result.skipped = skipped
    result.total_marks = total_marks
    result.percentage = percentage
    result.pass_fail = "PENDING" if pending_manual else (
        "PASS" if total_marks >= Decimal(str(exam.pass_cutoff)) else "FAIL"
    )

    attempt.total_marks = total_marks
    attempt.status = "submitted" if pending_manual else "evaluated"

    db.commit()
    db.refresh(result)

    return result


# TEACHER: VIEW ANSWERS FOR A SUBMITTED ATTEMPT
@router.get("/attempts/{attempt_id}/answers")
def view_attempt_answers(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == attempt_id
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if exam:
        require_exam_grade(current_user, exam, db)

    if attempt.status not in ("submitted", "evaluated"):
        raise HTTPException(
            status_code=400,
            detail="Only submitted attempts can be evaluated",
        )

    answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_attempt_id == attempt_id
    ).all()

    result = []

    for answer in answers:
        question = db.query(Question).filter(
            Question.id == answer.question_id
        ).first()

        exam_question = db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == attempt.exam_id,
            ExamQuestion.question_id == answer.question_id,
        ).first()

        # Skip answers whose question was deleted (soft or removed
        # from the exam) after the attempt was submitted.
        if not question or not question.is_active or not exam_question:
            continue

        result.append({
            "answer_id": answer.id,
            "question_id": answer.question_id,
            "question_text": question.question_text if question else None,
            "question_type": question.type if question else None,
            "answer_text": answer.answer_text,
            "code_text": answer.code_text,
            "answer_file": answer.answer_file,
            "selected_option_id": answer.selected_option_id,
            "selected_option_ids": answer.selected_option_ids,
            "match_answers": answer.match_answers,
            "maximum_marks": exam_question.marks if exam_question else 0,
            "marks_obtained": answer.marks_obtained,
            "is_correct": answer.is_correct,
        })

    return result


# TEACHER: EVALUATE ONE ANSWER
@router.put("/answers/{answer_id}/evaluate")
def evaluate_answer(
    answer_id: int,
    data: ManualEvaluationRequest,
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    answer = get_answer(answer_id, db)

    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == answer.exam_attempt_id
    ).first()

    if not attempt or attempt.status not in ("submitted", "evaluated"):
        raise HTTPException(
            status_code=400,
            detail="Attempt must be submitted before evaluation",
        )

    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if exam:
        require_exam_grade(current_user, exam, db)

    exam_question = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == attempt.exam_id,
        ExamQuestion.question_id == answer.question_id,
    ).first()

    if not exam_question:
        raise HTTPException(status_code=404, detail="Exam question not found")

    question = db.query(Question).filter(
        Question.id == answer.question_id
    ).first()
    if not question or not question.is_active:
        raise HTTPException(
            status_code=400,
            detail="This question has been deleted and cannot be graded",
        )

    marks = data.marks_obtained

    if not marks.is_finite() or marks > Decimal(str(exam_question.marks)):
        raise HTTPException(
            status_code=400,
            detail="Marks must be between zero and the question's maximum marks",
        )

    answer.marks_obtained = marks
    answer.is_correct = data.is_correct
    answer.evaluated_by = current_user.id
    answer.evaluated_at = datetime.now()

    db.commit()

    was_evaluated = attempt.status == "evaluated"
    result = recalculate_result(attempt, db)

    log_audit(
        db, current_user.id, "evaluation.update", "student_answer",
        answer.id,
        details=f"attempt {attempt.id}: marks={marks}",
    )
    # Student gets notified once — when the last pending answer is
    # graded and the attempt becomes fully evaluated.
    if not was_evaluated and attempt.status == "evaluated":
        exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
        exam_name = exam.name if exam else "your exam"
        notify(
            db, attempt.user_id,
            f"Result published: {exam_name}",
            f"Your result for \"{exam_name}\" is available. "
            f"Score: {result.total_marks} ({result.percentage}%) "
            f"— {result.pass_fail}.",
            "result.published",
        )
    db.commit()

    return {
        "message": "Answer evaluated successfully",
        "answer_id": answer.id,
        "marks_obtained": answer.marks_obtained,
        "result": {
            "total_marks": result.total_marks,
            "percentage": result.percentage,
            "pass_fail": result.pass_fail,
        },
    }


# TEACHER: ANSWERS STILL WAITING FOR MANUAL EVALUATION
@router.get("/pending-evaluation")
def pending_evaluation(
    exam_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user=teacher_admin,
):
    attempts_query = db.query(ExamAttempt).filter(
        ExamAttempt.status.in_(["submitted", "evaluated"]),
    )

    if exam_id is not None:
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")
        require_exam_grade(current_user, exam, db)
        attempts_query = attempts_query.filter(
            ExamAttempt.exam_id == exam_id
        )

    # Teachers only grade exams they created or that are assigned to
    # their batches (and only where grading wasn't restricted away
    # from them via selected graders).
    if not is_admin(current_user):
        attempts_query = attempts_query.filter(
            ExamAttempt.exam_id.in_(
                teacher_gradeable_exam_ids(db, current_user.id) or {0}
            )
        )

    attempt_ids = [a.id for a in attempts_query.all()]

    if not attempt_ids:
        return []

    answers = (
        db.query(StudentAnswer)
        .filter(
            StudentAnswer.exam_attempt_id.in_(attempt_ids),
            StudentAnswer.marks_obtained.is_(None),
        )
        .all()
    )

    output = []

    for answer in answers:
        if not answer_has_content(answer):
            continue

        attempt = db.query(ExamAttempt).filter(
            ExamAttempt.id == answer.exam_attempt_id
        ).first()

        question = db.query(Question).filter(
            Question.id == answer.question_id
        ).first()

        # Deleted questions no longer need grading.
        if not question or not question.is_active:
            continue

        # Description/paragraph items are informational and never need grading.
        if question.type in ("description", "paragraph"):
            continue

        student = db.query(User).filter(
            User.id == attempt.user_id
        ).first() if attempt else None

        exam_question = db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == attempt.exam_id,
            ExamQuestion.question_id == answer.question_id,
        ).first()

        # Question was removed from this exam after submission.
        if not exam_question:
            continue

        output.append({
            "answer_id": answer.id,
            "attempt_id": answer.exam_attempt_id,
            "exam_id": attempt.exam_id if attempt else None,
            "student_id": attempt.user_id if attempt else None,
            "student_name": student.name if student else None,
            "question_id": answer.question_id,
            "question_text": question.question_text if question else None,
            "question_type": question.type if question else None,
            "answer_text": answer.answer_text,
            "code_text": answer.code_text,
            "answer_file": answer.answer_file,
            "selected_option_id": answer.selected_option_id,
            "selected_option_ids": answer.selected_option_ids,
            "match_answers": answer.match_answers,
            "maximum_marks": exam_question.marks if exam_question else 0,
        })

    return output


# STUDENT: VIEW OWN RESULTS
@router.get("/my-results")
def my_results(
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.user_id == current_user.id,
        ExamAttempt.status.in_(["submitted", "evaluated"]),
    ).order_by(ExamAttempt.id.desc()).all()

    output = []

    for attempt in attempts:
        result = db.query(ExamResult).filter(
            ExamResult.exam_attempt_id == attempt.id
        ).first()

        exam = db.query(Exam).filter(
            Exam.id == attempt.exam_id
        ).first()

        output.append({
            "attempt_id": attempt.id,
            "exam_id": attempt.exam_id,
            "exam_name": exam.name if exam else None,
            "attempt_no": attempt.attempt_no,
            "status": attempt.status,
            "total_marks": result.total_marks if result else None,
            "maximum_marks": exam.total_marks if exam else None,
            "percentage": result.percentage if result else None,
            "pass_fail": result.pass_fail if result else None,
        })

    return output


# STUDENT: VIEW ONE OF THEIR OWN RESULTS
@router.get("/my-results/{attempt_id}")
def my_result_detail(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == attempt_id,
        ExamAttempt.user_id == current_user.id,
        ExamAttempt.status.in_(["submitted", "evaluated"]),
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Result not found")

    result = db.query(ExamResult).filter(
        ExamResult.exam_attempt_id == attempt.id
    ).first()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Result has not been generated yet",
        )

    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()

    # Recount live excluding informational items (description/
    # paragraph) so results stored before the exclusion existed
    # still display correct counts.
    items = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == attempt.exam_id
    ).all()
    # Only live questions count: skip deleted (is_active=False) ones too.
    question_types = {
        q.id: q.type for q in db.query(Question).filter(
            Question.id.in_([i.question_id for i in items]),
            Question.is_active.is_(True),
        ).all()
    }
    items = [
        i for i in items
        if i.question_id in question_types
        and question_types[i.question_id] not in ("description", "paragraph")
    ]

    answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_attempt_id == attempt.id
    ).all()
    answer_map = {a.question_id: a for a in answers}

    attempted = correct = wrong = pending = no_verdict = 0
    for item in items:
        answer = answer_map.get(item.question_id)
        if not answer or not answer_has_content(answer):
            continue
        attempted += 1
        if answer.is_correct is True:
            correct += 1
        elif answer.is_correct is False:
            wrong += 1
        elif answer.marks_obtained is not None:
            # Graded without a correct/wrong verdict.
            no_verdict += 1
        else:
            # Attempted but no marks yet — genuinely awaiting grading.
            pending += 1

    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "total_questions": len(items),
        "attempted": attempted,
        "correct": correct,
        "wrong": wrong,
        "pending": pending,
        "no_verdict": no_verdict,
        "skipped": len(items) - attempted,
        "total_marks": result.total_marks,
        "maximum_marks": exam.total_marks if exam else None,
        "percentage": result.percentage,
        "pass_fail": result.pass_fail,
    }


def _correct_payload(question: Question, db: Session, attempt_id=None):
    """Build the correct-answer display data for one question type.

    Returns (options, correct_answer, match_items, gap_blanks,
    ordering_items); unused entries are None.
    """
    if question.type in ("multichoice", "multiselect", "image"):
        options = db.query(QuestionOption).filter(
            QuestionOption.question_id == question.id
        ).order_by(QuestionOption.sort_order, QuestionOption.id).all()
        return (
            [
                {
                    "id": o.id,
                    "option_text": o.option_text,
                    "image_url": o.image_url,
                    "is_correct": o.is_correct,
                }
                for o in options
            ],
            None,
            None,
            None,
            None,
        )

    if question.type == "truefalse":
        cfg = db.query(QuestionTrueFalse).filter(
            QuestionTrueFalse.question_id == question.id
        ).first()
        return None, ("true" if cfg.true_answer else "false") if cfg else None, None, None, None

    if question.type == "shortanswer":
        cfg = db.query(QuestionShortAnswer).filter(
            QuestionShortAnswer.question_id == question.id
        ).first()
        return None, cfg.answer_text if cfg else None, None, None, None

    if question.type == "numerical":
        cfg = db.query(QuestionNumerical).filter(
            QuestionNumerical.question_id == question.id
        ).first()
        if not cfg:
            return None, None, None, None, None
        text = str(cfg.answer_value)
        if cfg.tolerance:
            text += f" (\u00b1{cfg.tolerance})"
        return None, text, None, None, None

    if question.type == "match":
        rows = db.query(QuestionMatch).filter(
            QuestionMatch.question_id == question.id
        ).order_by(QuestionMatch.sort_order, QuestionMatch.id).all()
        return None, None, [
            {"sub_question": m.sub_question, "correct": m.sub_answer}
            for m in rows
        ], None, None

    if question.type == "multianswer":
        cfg = db.query(QuestionMultiAnswer).filter(
            QuestionMultiAnswer.question_id == question.id
        ).first()
        return None, cfg.answer_text if cfg else None, None, None, None

    if question.type == "selectmissing":
        rows = db.query(QuestionGapSelect).filter(
            QuestionGapSelect.question_id == question.id
        ).order_by(
            QuestionGapSelect.blank_no,
            QuestionGapSelect.sort_order,
            QuestionGapSelect.id,
        ).all()
        grouped = {}
        for r in rows:
            slot = grouped.setdefault(r.blank_no, {"options": []})
            slot["options"].append(r.option_text)
            if r.is_correct:
                slot["correct"] = r.option_text
        return None, None, None, [
            {
                "blank_no": bn,
                "options": slot["options"],
                "correct": slot.get("correct"),
            }
            for bn, slot in sorted(grouped.items())
        ], None

    if question.type == "ordering":
        rows = db.query(QuestionOrdering).filter(
            QuestionOrdering.question_id == question.id
        ).order_by(QuestionOrdering.position, QuestionOrdering.id).all()
        return None, None, None, None, [
            {"id": r.id, "item_text": r.item_text, "position": r.position}
            for r in rows
        ]

    if question.type in ("calculated", "calculatedsimple", "calculatedmulti"):
        cfg = db.query(QuestionCalculated).filter(
            QuestionCalculated.question_id == question.id
        ).first()
        if not cfg:
            return None, None, None, None, None
        values = wildcard_values(
            cfg.datasets, f"{question.id}:{attempt_id}"
        ) if attempt_id else {}
        # calculatedmulti stores one formula per expected part: 'a+b | a-b'.
        parts = [p.strip() for p in cfg.formula.split("|") if p.strip()]
        expected_parts = [eval_formula(p, values) for p in parts]
        if all(e is not None for e in expected_parts):
            text = ", ".join(str(e) for e in expected_parts)
        else:
            text = f"formula: {cfg.formula}"
        if cfg.tolerance:
            text += f" (\u00b1{cfg.tolerance})"
        if cfg.units:
            text += f" {cfg.units}"
        return None, text, None, None, None

    # essay, coding, etc. have no single stored correct answer.
    return None, None, None, None, None


# STUDENT: PER-QUESTION REVIEW OF OWN ATTEMPT
@router.get("/my-results/{attempt_id}/answers")
def my_result_answers(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == attempt_id,
        ExamAttempt.user_id == current_user.id,
        ExamAttempt.status.in_(["submitted", "evaluated"]),
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Result not found")

    items = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == attempt.exam_id
    ).order_by(ExamQuestion.sort_order, ExamQuestion.id).all()

    questions = {
        q.id: q for q in db.query(Question).filter(
            Question.id.in_([i.question_id for i in items])
        ).all()
    }

    answers = {
        a.question_id: a for a in db.query(StudentAnswer).filter(
            StudentAnswer.exam_attempt_id == attempt.id
        ).all()
    }

    output = []

    for item in items:
        question = questions.get(item.question_id)

        # Description/paragraph items are informational text, not questions.
        if not question or question.type in ("description", "paragraph"):
            continue

        answer = answers.get(item.question_id)
        options, correct_answer, match_items, gap_blanks, ordering_items = (
            _correct_payload(question, db, attempt_id)
        )

        images = []
        if question.type == "image":
            images = [
                {"image_url": img.image_url, "alt_text": img.alt_text}
                for img in db.query(QuestionImage).filter(
                    QuestionImage.question_id == question.id
                ).order_by(QuestionImage.position, QuestionImage.id).all()
            ]

        # Show the same wildcard values the student saw during the attempt.
        q_text = question.question_text
        if question.type in (
            "calculated", "calculatedsimple", "calculatedmulti"
        ):
            wc = calculated_wildcards(db, question.id, attempt_id)
            if wc:
                q_text = substitute_wildcards(q_text, wc)

        output.append({
            "question_id": question.id,
            "name": question.name,
            "question_text": q_text,
            "question_type": question.type,
            "marks": item.marks,
            "images": images,
            "answered": bool(answer and answer_has_content(answer)),
            "is_correct": answer.is_correct if answer else None,
            "marks_obtained": answer.marks_obtained if answer else None,
            "answer_text": answer.answer_text if answer else None,
            "code_text": answer.code_text if answer else None,
            "answer_file": answer.answer_file if answer else None,
            "selected_option_id": answer.selected_option_id if answer else None,
            "selected_option_ids": answer.selected_option_ids if answer else None,
            "match_answers": answer.match_answers if answer else None,
            "options": options,
            "correct_answer": correct_answer,
            "match_items": match_items,
            "gap_blanks": gap_blanks,
            "ordering_items": ordering_items,
        })

    return output
