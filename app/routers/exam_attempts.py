
import random
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.exam import Exam, ExamQuestion
from app.models.exam_attempt import ExamAttempt, StudentAnswer, ExamResult
from app.models.question import Question
from app.models.question_image import QuestionImage
from app.models.question_gapselect import QuestionGapSelect
from app.models.question_match import QuestionMatch
from app.models.question_option import QuestionOption
from app.models.question_ordering import QuestionOrdering
from app.models.question_paragraph import QuestionParagraph
from app.models.coding_question import CodingQuestion, CodingTestCase
from app.schemas.exam_attempt import (
    StartAttemptResponse,
    SaveAnswerRequest,
    StudentAnswerResponse,
    ExamQuestionForStudent,
    ExamOptionForStudent,
    ExamMatchItemForStudent,
    ExamGapBlankForStudent,
    ExamOrderingItemForStudent,
    ExamCodingCaseForStudent,
    RunCodeRequest,
    RunCodeResponse,
    RunCodeCaseResult,
    SubmitAttemptResponse,
    ExamImageForStudent,
)
from app.utils.dependencies import require_role
from app.services.evaluation_service import (
    answer_has_content,
    auto_grade_answer,
    calculated_wildcards,
    substitute_wildcards,
)
from app.services.code_executor import run_test_cases
from app.services.activity_service import log_audit

router = APIRouter(prefix="/api/student/exams", tags=["Student Exam Attempts"])
student_only = Depends(require_role("student"))


def get_attempt(attempt_id: int, user_id: int, db: Session):
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.id == attempt_id,
        ExamAttempt.user_id == user_id,
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return attempt


def check_attempt_open(attempt: ExamAttempt, db: Session):
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt is not in progress")

    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    deadline = attempt.start_time + timedelta(minutes=exam.duration_minutes)
    now = datetime.now()

    if now >= deadline:
        raise HTTPException(
            status_code=400,
            detail="Exam time has expired. Submit the attempt.",
        )

    if exam.end_time and now >= exam.end_time:
        raise HTTPException(
            status_code=400,
            detail="Exam availability has ended.",
        )

    return exam, deadline


# START OR RESUME ATTEMPT
@router.post("/{exam_id}/start", response_model=StartAttemptResponse)
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    now = datetime.now()

    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.is_active == True,
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Active exam not found")

    if exam.start_time and now < exam.start_time:
        raise HTTPException(status_code=400, detail="Exam has not started yet")

    if exam.end_time and now >= exam.end_time:
        raise HTTPException(status_code=400, detail="Exam has ended")

    # Resume an existing unfinished attempt instead of creating a duplicate.
    existing = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.user_id == current_user.id,
        ExamAttempt.status == "in_progress",
    ).order_by(ExamAttempt.attempt_no.desc()).first()

    if existing:
        deadline = existing.start_time + timedelta(
            minutes=exam.duration_minutes
        )
        if now < deadline and (not exam.end_time or now < exam.end_time):
            return StartAttemptResponse(
                attempt_id=existing.id,
                exam_id=exam_id,
                attempt_no=existing.attempt_no,
                status=existing.status,
                start_time=existing.start_time,
                end_time=min(
                    deadline,
                    exam.end_time if exam.end_time else deadline,
                ),
                remaining_seconds=max(
                    0, int((min(
                        deadline,
                        exam.end_time if exam.end_time else deadline,
                    ) - now).total_seconds())
                ),
            )

        existing.status = "submitted"
        existing.end_time = min(
            now, exam.end_time if exam.end_time and now > exam.end_time else now
        )
        db.commit()

        # No retries left anyway — hand back the expired attempt with
        # remaining_seconds=0 instead of an attempt-limit error, so the
        # UI can show "time is up" and send the student back.
        if exam.attempts_allowed is not None:
            prior = db.query(ExamAttempt).filter(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.user_id == current_user.id,
            ).count()
            if prior >= exam.attempts_allowed:
                return StartAttemptResponse(
                    attempt_id=existing.id,
                    exam_id=exam_id,
                    attempt_no=existing.attempt_no,
                    status=existing.status,
                    start_time=existing.start_time,
                    end_time=existing.end_time or now,
                    remaining_seconds=0,
                )

    previous_count = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.user_id == current_user.id,
    ).count()

    if exam.attempts_allowed is not None and previous_count >= exam.attempts_allowed:
        raise HTTPException(status_code=400, detail="Attempt limit reached")

    questions_count = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam_id
    ).count()

    if questions_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No questions have been added to this exam",
        )

    deadline = now + timedelta(minutes=exam.duration_minutes)
    if exam.end_time:
        deadline = min(deadline, exam.end_time)

    attempt = ExamAttempt(
        exam_id=exam_id,
        user_id=current_user.id,
        attempt_no=previous_count + 1,
        start_time=now,
        status="in_progress",
        total_marks=0,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return StartAttemptResponse(
        attempt_id=attempt.id,
        exam_id=exam_id,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        start_time=attempt.start_time,
        end_time=deadline,
        remaining_seconds=max(0, int((deadline - now).total_seconds())),
    )


# VIEW EXAM QUESTIONS WITHOUT CORRECT ANSWERS
@router.get("/{exam_id}/attempt/{attempt_id}/questions",
            response_model=list[ExamQuestionForStudent])
def view_questions(
    exam_id: int,
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempt = get_attempt(attempt_id, current_user.id, db)

    if attempt.exam_id != exam_id:
        raise HTTPException(status_code=400, detail="Exam/attempt mismatch")

    exam, _ = check_attempt_open(attempt, db)

    rows = (
        db.query(Question, ExamQuestion)
        .join(ExamQuestion, ExamQuestion.question_id == Question.id)
        .filter(
            ExamQuestion.exam_id == exam_id,
            Question.is_active == True,
        )
        .order_by(ExamQuestion.sort_order, ExamQuestion.id)
        .all()
    )

    if exam.shuffle_questions:
        random.shuffle(rows)

    # Group each paragraph's linked questions right after it, so a
    # passage always sits immediately above all of its children.
    para_links = {}   # paragraph qid -> [child qids]
    child_owner = {}  # child qid -> paragraph qid
    for question, _ in rows:
        if question.type != "paragraph":
            continue
        cfg = db.query(QuestionParagraph).filter(
            QuestionParagraph.question_id == question.id
        ).first()
        ids = [int(x) for x in (cfg.child_question_ids or [])] if cfg else []
        para_links[question.id] = ids
        for cid in ids:
            child_owner[cid] = question.id

    by_qid = {question.id: (question, eq) for question, eq in rows}
    ordered = []
    for question, exam_question in rows:
        # Children are emitted under their paragraph, not in place.
        owner = child_owner.get(question.id)
        if owner is not None and owner in para_links:
            continue
        ordered.append((question, exam_question))
        if question.type == "paragraph":
            for cid in para_links[question.id]:
                if cid in by_qid:
                    ordered.append(by_qid[cid])
    rows = ordered

    result = []
    for question, exam_question in rows:
        options = db.query(QuestionOption).filter(
            QuestionOption.question_id == question.id
        ).order_by(QuestionOption.sort_order).all()

        images = []
        if question.type == "image":
            images = [
                ExamImageForStudent(
                    id=img.id,
                    image_url=img.image_url,
                    alt_text=img.alt_text,
                )
                for img in db.query(QuestionImage).filter(
                    QuestionImage.question_id == question.id
                ).order_by(QuestionImage.position, QuestionImage.id).all()
            ]

        match_items = []
        match_choices = []
        if question.type == "match":
            pairs = db.query(QuestionMatch).filter(
                QuestionMatch.question_id == question.id
            ).order_by(QuestionMatch.sort_order).all()
            match_items = [
                ExamMatchItemForStudent(
                    id=pair.id,
                    sub_question=pair.sub_question,
                    sort_order=pair.sort_order,
                )
                for pair in pairs
            ]
            match_choices = [pair.sub_answer for pair in pairs]
            random.shuffle(match_choices)

        # Select-missing-word: group options per [[n]] blank, shuffle
        # each dropdown (seeded per attempt so a refresh keeps the
        # same order).
        gap_blanks = []
        if question.type == "selectmissing":
            opt_rows = db.query(QuestionGapSelect).filter(
                QuestionGapSelect.question_id == question.id
            ).order_by(
                QuestionGapSelect.blank_no,
                QuestionGapSelect.sort_order,
                QuestionGapSelect.id,
            ).all()
            grouped = {}
            for o in opt_rows:
                grouped.setdefault(o.blank_no, []).append(o.option_text)
            rng = random.Random(f"gap:{question.id}:{attempt_id}")
            gap_blanks = [
                ExamGapBlankForStudent(
                    blank_no=bn, options=rng.sample(opts, len(opts))
                )
                for bn, opts in sorted(grouped.items())
            ]

        # Ordering: send the items in a stable-per-attempt shuffled
        # order; the correct sequence stays server-side for grading.
        ordering_items = []
        if question.type == "ordering":
            orows = db.query(QuestionOrdering).filter(
                QuestionOrdering.question_id == question.id
            ).order_by(QuestionOrdering.position, QuestionOrdering.id).all()
            ordering_items = [
                ExamOrderingItemForStudent(id=r.id, item_text=r.item_text)
                for r in orows
            ]
            random.Random(f"ord:{question.id}:{attempt_id}").shuffle(
                ordering_items
            )

        # Coding questions: deliver language + starter code + the
        # non-hidden sample test cases (hidden ones stay server-side
        # for auto-grading).
        coding_language = None
        starter_code = None
        coding_test_cases = []
        if question.type == "coding":
            cfg = db.query(CodingQuestion).filter(
                CodingQuestion.question_id == question.id
            ).first()
            if cfg:
                coding_language = cfg.language
                starter_code = cfg.starter_code
                sample_cases = db.query(CodingTestCase).filter(
                    CodingTestCase.coding_question_id == cfg.id,
                    CodingTestCase.is_hidden == False,  # noqa: E712
                ).order_by(
                    CodingTestCase.sort_order, CodingTestCase.id
                ).all()
                coding_test_cases = [
                    ExamCodingCaseForStudent(
                        input_text=c.input_text,
                        expected_output=c.expected_output,
                        marks=float(c.marks),
                    )
                    for c in sample_cases
                ]

        # Paragraph passages list which questions belong under them
        # (config already fetched above while grouping).
        linked_ids = para_links.get(question.id, [])

        # Calculated questions may contain {name} wildcards in the text;
        # substitute the values drawn for this attempt (seeded, so the
        # grader recomputes identical numbers).
        question_text = question.question_text
        if question.type in (
            "calculated", "calculatedsimple", "calculatedmulti"
        ):
            wc = calculated_wildcards(db, question.id, attempt_id)
            if wc:
                question_text = substitute_wildcards(question_text, wc)

        result.append(
            ExamQuestionForStudent(
                id=question.id,
                type=question.type,
                name=question.name,
                question_text=question_text,
                default_mark=float(exam_question.marks),
                options=[
                    ExamOptionForStudent(
                        id=option.id,
                        option_text=option.option_text,
                        image_url=option.image_url,
                        sort_order=option.sort_order,
                    )
                    for option in options
                ],
                images=images,
                match_items=match_items,
                linked_question_ids=linked_ids,
                match_choices=match_choices,
                gap_blanks=gap_blanks,
                ordering_items=ordering_items,
                coding_language=coding_language,
                starter_code=starter_code,
                coding_test_cases=coding_test_cases,
            )
        )

    return result


# SAVE OR UPDATE AN ANSWER
@router.put("/attempt/{attempt_id}/answers",
            response_model=StudentAnswerResponse)
def save_answer(
    attempt_id: int,
    data: SaveAnswerRequest,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempt = get_attempt(attempt_id, current_user.id, db)
    exam, _ = check_attempt_open(attempt, db)

    exam_question = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id,
        ExamQuestion.question_id == data.question_id,
    ).first()

    if not exam_question:
        raise HTTPException(
            status_code=400,
            detail="Question does not belong to this exam",
        )

    if data.selected_option_id is not None:
        option = db.query(QuestionOption).filter(
            QuestionOption.id == data.selected_option_id,
            QuestionOption.question_id == data.question_id,
        ).first()

        if not option:
            raise HTTPException(
                status_code=400,
                detail="Option does not belong to this question",
            )

    if data.selected_option_ids:
        valid_ids = {
            row.id for row in db.query(QuestionOption.id).filter(
                QuestionOption.question_id == data.question_id,
            ).all()
        }

        invalid = [
            option_id for option_id in data.selected_option_ids
            if option_id not in valid_ids
        ]

        if invalid:
            raise HTTPException(
                status_code=400,
                detail="One or more options do not belong to this question",
            )

    answer = db.query(StudentAnswer).filter(
        StudentAnswer.exam_attempt_id == attempt_id,
        StudentAnswer.question_id == data.question_id,
    ).first()

    if not answer:
        answer = StudentAnswer(
            exam_attempt_id=attempt_id,
            question_id=data.question_id,
        )
        db.add(answer)

    answer.selected_option_id = data.selected_option_id
    answer.selected_option_ids = data.selected_option_ids
    answer.match_answers = data.match_answers
    answer.answer_text = data.answer_text
    answer.code_text = data.code_text
    answer.answer_file = data.answer_file

    db.commit()
    db.refresh(answer)
    return answer


# GET SAVED ANSWERS (RESUME)
@router.get("/attempt/{attempt_id}/answers",
            response_model=list[StudentAnswerResponse])
def get_saved_answers(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempt = get_attempt(attempt_id, current_user.id, db)
    check_attempt_open(attempt, db)

    return db.query(StudentAnswer).filter(
        StudentAnswer.exam_attempt_id == attempt_id
    ).all()


# RUN CODE AGAINST THE VISIBLE (SAMPLE) TEST CASES
@router.post("/attempt/{attempt_id}/run-code",
             response_model=RunCodeResponse)
def run_code_for_attempt(
    attempt_id: int,
    data: RunCodeRequest,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempt = get_attempt(attempt_id, current_user.id, db)
    check_attempt_open(attempt, db)

    linked = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == attempt.exam_id,
        ExamQuestion.question_id == data.question_id,
    ).first()
    question = db.query(Question).filter(
        Question.id == data.question_id
    ).first()
    if not linked or not question or question.type != "coding":
        raise HTTPException(
            status_code=404, detail="Coding question not found in this exam"
        )

    config = db.query(CodingQuestion).filter(
        CodingQuestion.question_id == question.id
    ).first()
    if not config:
        raise HTTPException(
            status_code=400,
            detail="This question has no coding configuration",
        )

    cases = db.query(CodingTestCase).filter(
        CodingTestCase.coding_question_id == config.id,
        CodingTestCase.is_hidden == False,  # noqa: E712
    ).order_by(CodingTestCase.sort_order, CodingTestCase.id).all()
    if not cases:
        raise HTTPException(
            status_code=400,
            detail="No visible test cases configured for this question",
        )

    results = run_test_cases(
        config.language, data.code, cases,
        time_limit=config.time_limit,
    )
    out = [
        RunCodeCaseResult(
            input_text=r.input_text,
            expected_output=r.expected_output,
            actual_output=r.actual_output,
            passed=r.passed,
            timed_out=r.timed_out,
            error=r.error,
            marks=float(c.marks),
        )
        for r, c in zip(results, cases)
    ]
    return RunCodeResponse(
        results=out,
        passed_count=sum(1 for r in out if r.passed),
        total=len(out),
    )


# SUBMIT ATTEMPT AND AUTO-GRADE SINGLE-CORRECT MCQ
@router.post("/attempt/{attempt_id}/submit",
             response_model=SubmitAttemptResponse)
def submit_exam(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user=student_only,
):
    attempt = get_attempt(attempt_id, current_user.id, db)

    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt already submitted")

    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    now = datetime.now()
    deadline = attempt.start_time + timedelta(minutes=exam.duration_minutes)
    if exam.end_time:
        deadline = min(deadline, exam.end_time)

    # Submission is accepted even after time expires, but only saved answers count.
    attempt.end_time = min(now, deadline)
    attempt.status = "submitted"

    exam_items = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id
    ).all()

    question_types = {
        q.id: q.type for q in db.query(Question).filter(
            Question.id.in_([i.question_id for i in exam_items])
        ).all()
    }

    # Description/paragraph items are informational text, not questions.
    exam_items = [
        i for i in exam_items
        if question_types.get(i.question_id) not in ("description", "paragraph")
    ]

    answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_attempt_id == attempt.id
    ).all()
    answers_by_question = {a.question_id: a for a in answers}

    total_questions = len(exam_items)
    attempted = 0
    correct = 0
    wrong = 0
    scored_marks = Decimal("0.00")
    pending_manual = False

    for item in exam_items:
        answer = answers_by_question.get(item.question_id)
        if not answer:
            continue

        if not answer_has_content(answer):
            continue

        attempted += 1
        question = db.query(Question).filter(
            Question.id == item.question_id
        ).first()

        if not question:
            continue

        graded = auto_grade_answer(
            db, question, answer, Decimal(str(item.marks))
        )

        if graded is None:
            # Type requires manual evaluation by teacher/admin.
            answer.is_correct = None
            answer.marks_obtained = None
            pending_manual = True
            continue

        is_correct, marks = graded
        answer.is_correct = is_correct
        answer.marks_obtained = marks
        scored_marks += marks

        if is_correct:
            correct += 1
        else:
            wrong += 1

    skipped = total_questions - attempted
    attempt.total_marks = scored_marks

    percentage = (
        (scored_marks / Decimal(str(exam.total_marks))) * Decimal("100")
        if exam.total_marks else Decimal("0.00")
    )

    pass_fail = "PENDING" if pending_manual else (
        "PASS" if scored_marks >= exam.pass_cutoff else "FAIL"
    )

    result = ExamResult(
        exam_attempt_id=attempt.id,
        total_questions=total_questions,
        attempted=attempted,
        correct=correct,
        wrong=wrong,
        skipped=skipped,
        total_marks=scored_marks,
        percentage=percentage,
        pass_fail=pass_fail,
    )

    db.add(result)
    log_audit(
        db, attempt.user_id, "exam.submit", "exam_attempt", attempt.id,
        details=f"exam {exam.id} '{exam.name}': "
                f"{attempted}/{total_questions} attempted, "
                f"{scored_marks} marks",
    )
    db.commit()

    return SubmitAttemptResponse(
        attempt_id=attempt.id,
        status=attempt.status,
        attempted=attempted,
        total_questions=total_questions,
        message="Exam submitted successfully",
    )
