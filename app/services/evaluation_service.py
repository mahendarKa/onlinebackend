"""
Auto-evaluation helpers for objective question types.

Each grader returns (is_correct: bool, marks_obtained: Decimal) or None
when the question type is not auto-gradable and must be evaluated
manually by a teacher/admin.
"""
import math
import random
import re
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.question_calculated import QuestionCalculated
from app.models.question_option import QuestionOption
from app.models.question_truefalse import QuestionTrueFalse
from app.models.question_shortanswer import QuestionShortAnswer
from app.models.question_numerical import QuestionNumerical
from app.models.question_match import QuestionMatch
from app.models.question_multianswer import QuestionMultiAnswer
from app.models.question_gapselect import QuestionGapSelect
from app.models.question_ordering import QuestionOrdering
from app.models.coding_question import CodingQuestion, CodingTestCase
from app.services.code_executor import run_test_cases

ZERO = Decimal("0.00")


def _grade_multichoice(db: Session, question, answer, max_marks: Decimal):
    if answer.selected_option_id is None:
        return None

    option = db.query(QuestionOption).filter(
        QuestionOption.id == answer.selected_option_id,
        QuestionOption.question_id == question.id,
    ).first()

    if not option:
        return False, ZERO

    is_correct = bool(option.is_correct)
    return is_correct, max_marks if is_correct else ZERO


def _grade_multiselect(db: Session, question, answer, max_marks: Decimal):
    if not answer.selected_option_ids:
        return None

    options = db.query(QuestionOption).filter(
        QuestionOption.question_id == question.id
    ).all()

    fraction_map = {o.id: Decimal(str(o.fraction or 0)) for o in options}
    correct_ids = {o.id for o in options if o.is_correct}
    selected_ids = set(answer.selected_option_ids)

    # Moodle-style: sum fractions of selected options, clamp to [0, 100].
    earned_fraction = sum(
        fraction_map.get(option_id, Decimal("0"))
        for option_id in selected_ids
    )
    earned_fraction = max(Decimal("0"), min(Decimal("100"), earned_fraction))

    marks = (max_marks * earned_fraction / Decimal("100")).quantize(
        Decimal("0.01")
    )
    is_correct = selected_ids == correct_ids and len(correct_ids) > 0

    return is_correct, marks


def _grade_truefalse(db: Session, question, answer, max_marks: Decimal):
    if not answer.answer_text:
        return None

    config = db.query(QuestionTrueFalse).filter(
        QuestionTrueFalse.question_id == question.id
    ).first()

    if not config:
        return None

    student_answer = answer.answer_text.strip().lower()
    correct_answer = "true" if config.true_answer else "false"

    is_correct = student_answer == correct_answer
    return is_correct, max_marks if is_correct else ZERO


def _grade_shortanswer(db: Session, question, answer, max_marks: Decimal):
    if not answer.answer_text or not answer.answer_text.strip():
        return None

    config = db.query(QuestionShortAnswer).filter(
        QuestionShortAnswer.question_id == question.id
    ).first()

    if not config:
        return None

    student_text = answer.answer_text.strip()
    expected_text = (config.answer_text or "").strip()

    if config.case_sensitive:
        is_correct = student_text == expected_text
    else:
        is_correct = student_text.lower() == expected_text.lower()

    return is_correct, max_marks if is_correct else ZERO


def _grade_numerical(db: Session, question, answer, max_marks: Decimal):
    if not answer.answer_text or not answer.answer_text.strip():
        return None

    config = db.query(QuestionNumerical).filter(
        QuestionNumerical.question_id == question.id
    ).first()

    if not config:
        return None

    try:
        student_value = Decimal(answer.answer_text.strip())
    except InvalidOperation:
        return False, ZERO

    expected = Decimal(str(config.answer_value))
    tolerance = Decimal(str(config.tolerance or 0))

    is_correct = abs(student_value - expected) <= tolerance
    return is_correct, max_marks if is_correct else ZERO


def _grade_match(db: Session, question, answer, max_marks: Decimal):
    if not answer.match_answers:
        return None

    pairs = db.query(QuestionMatch).filter(
        QuestionMatch.question_id == question.id
    ).all()

    if not pairs:
        return None

    total = len(pairs)
    correct_pairs = sum(
        1 for pair in pairs
        if str(answer.match_answers.get(pair.sub_question, "")).strip().lower()
        == pair.sub_answer.strip().lower()
    )

    marks = (max_marks * Decimal(correct_pairs) / Decimal(total)).quantize(
        Decimal("0.01")
    )
    is_correct = correct_pairs == total

    return is_correct, marks


def _normalize_multianswer(text: str) -> str:
    """Canonicalize a multianswer response: case-insensitive and
    separator-insensitive (commas, semicolons, extra spaces all equal).
    """
    return re.sub(r"\s+", " ", re.sub(r"[,;]", " ", text)).strip().lower()


def _grade_multianswer(db: Session, question, answer, max_marks: Decimal):
    if not answer.answer_text or not answer.answer_text.strip():
        return None

    config = db.query(QuestionMultiAnswer).filter(
        QuestionMultiAnswer.question_id == question.id
    ).first()

    if not config:
        return None

    lines = [
        l.strip()
        for l in (config.answer_text or "").splitlines()
        if l.strip()
    ]
    student_text = _normalize_multianswer(answer.answer_text)

    if len(lines) > 1:
        # One line per blank — compare positionally. Students separate
        # blanks with commas; whitespace split is the lenient fallback.
        parts = [
            p.strip()
            for p in re.split(r"[,;]", answer.answer_text or "")
            if p.strip()
        ]
        if len(parts) != len(lines):
            parts = (answer.answer_text or "").split()
        is_correct = len(parts) == len(lines) and all(
            _normalize_multianswer(s) == _normalize_multianswer(exp)
            for s, exp in zip(parts, lines)
        )
    else:
        # Single-line config: each line is a full accepted answer.
        accepted = {_normalize_multianswer(l) for l in lines}
        is_correct = student_text in accepted

    return is_correct, max_marks if is_correct else ZERO


def _grade_selectmissing(db: Session, question, answer, max_marks: Decimal):
    # match_answers carries {blank_no: chosen option text}.
    if not answer.match_answers:
        return None

    rows = db.query(QuestionGapSelect).filter(
        QuestionGapSelect.question_id == question.id
    ).all()

    if not rows:
        return None

    correct_map = {}
    for row in rows:
        if row.is_correct:
            correct_map[row.blank_no] = (
                row.option_text or ""
            ).strip().lower()

    if not correct_map:
        return None

    total = len(correct_map)
    got = sum(
        1
        for blank_no, correct_text in correct_map.items()
        if str(answer.match_answers.get(str(blank_no), "")).strip().lower()
        == correct_text
    )

    marks = (max_marks * Decimal(got) / Decimal(total)).quantize(
        Decimal("0.01")
    )
    return got == total, marks


def _grade_ordering(db: Session, question, answer, max_marks: Decimal):
    # match_answers carries {"order": [item ids in student's order]}.
    order = (answer.match_answers or {}).get("order")
    if not order:
        return None

    items = db.query(QuestionOrdering).filter(
        QuestionOrdering.question_id == question.id
    ).order_by(QuestionOrdering.position, QuestionOrdering.id).all()

    if len(items) < 2:
        return None

    correct_seq = [i.id for i in items]
    student_rank = {item_id: idx for idx, item_id in enumerate(order)}

    # Only items the student actually placed can be scored.
    placed = [i for i in correct_seq if i in student_rank]
    total_pairs = len(placed) * (len(placed) - 1) // 2
    if total_pairs == 0:
        return False, ZERO

    # Relative-order grading: each correctly ordered pair earns a
    # share, so a single swap doesn't zero the whole question.
    correct_pairs = sum(
        1
        for x in range(len(placed))
        for y in range(x + 1, len(placed))
        if student_rank[placed[x]] < student_rank[placed[y]]
    )

    marks = (
        max_marks * Decimal(correct_pairs) / Decimal(total_pairs)
    ).quantize(Decimal("0.01"))
    is_correct = (
        len(order) == len(correct_seq)
        and correct_pairs == total_pairs
    )
    return is_correct, marks


def wildcard_values(datasets, seed):
    """Draw one random value per dataset range, reproducibly.

    datasets: list of {name, min_value|min, max_value|max, decimals}.
    seed:    anything hashable — same seed + datasets => same values.
    """
    if not datasets:
        return {}

    rng = random.Random(str(seed))
    values = {}
    for d in sorted(datasets, key=lambda x: str(x.get("name", ""))):
        # Strip braces — some clients saved "{a}" instead of "a".
        name = re.sub(r"[{}]", "", str(d.get("name", ""))).strip()
        if not name:
            continue
        lo = float(d.get("min_value", d.get("min", 0)) or 0)
        hi = float(d.get("max_value", d.get("max", lo)) or lo)
        decimals = int(d.get("decimals", 0) or 0)
        value = rng.uniform(lo, hi)
        value = round(value, decimals)
        values[name] = int(value) if decimals == 0 else value
    return values


def substitute_wildcards(text: str, values: dict) -> str:
    """Replace {name} tokens in text with the drawn wildcard values."""
    if not text or not values:
        return text

    def repl(m):
        name = m.group(1)
        return str(values[name]) if name in values else m.group(0)

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", repl, text)


def calculated_wildcards(db: Session, question_id: int, seed):
    """Wildcard {name: value} map for a question + attempt/user seed."""
    config = db.query(QuestionCalculated).filter(
        QuestionCalculated.question_id == question_id
    ).first()
    if not config or not config.datasets:
        return {}
    return wildcard_values(config.datasets, f"{question_id}:{seed}")


def eval_formula(formula: str, values: dict | None = None):
    """Evaluate a stored math formula like 'sqrt(2) * 10' or '2*pi*{a}'.

    {name} wildcards are replaced by the given values first. Only
    math-module names, numbers and operators are allowed; '^' is
    treated as exponentiation. Returns a float or None if invalid.
    """
    if not formula or not formula.strip():
        return None

    expr = substitute_wildcards(formula.strip(), values or {})
    expr = expr.replace("^", "**")
    if not re.fullmatch(r"[0-9a-zA-Z_+\-*/()., ]*", expr):
        return None

    env = {
        name: getattr(math, name)
        for name in dir(math)
        if not name.startswith("_")
    }
    env.update({"abs": abs, "min": min, "max": max, "round": round, "pow": pow})

    try:
        return float(eval(expr, {"__builtins__": {}}, env))  # noqa: S307
    except Exception:
        return None


def _grade_calculated(db: Session, question, answer, max_marks: Decimal):
    if not answer.answer_text or not answer.answer_text.strip():
        return None

    config = db.query(QuestionCalculated).filter(
        QuestionCalculated.question_id == question.id
    ).first()

    if not config:
        return None

    # Same seed used when the question was delivered, so the wildcards
    # resolve to the exact numbers the student saw.
    values = wildcard_values(
        config.datasets, f"{question.id}:{answer.exam_attempt_id}"
    )

    # calculatedmulti stores one expected formula per part: 'a+b | a-b'.
    parts = [p.strip() for p in config.formula.split("|") if p.strip()]
    expected = [eval_formula(p, values) for p in parts]

    if any(e is None for e in expected):
        # Formula is broken — do not auto-fail the student; flag for review.
        return None

    student_parts = [s.strip() for s in answer.answer_text.split(",")]
    tolerance = Decimal(str(config.tolerance or 0))

    correct_parts = 0
    for i, exp in enumerate(expected):
        if i >= len(student_parts):
            break
        try:
            student_value = Decimal(student_parts[i])
        except InvalidOperation:
            continue
        if abs(student_value - Decimal(str(exp))) <= tolerance:
            correct_parts += 1

    is_correct = correct_parts == len(expected)
    # Multi-part questions earn a fraction of the marks per correct part.
    marks = max_marks * Decimal(correct_parts) / Decimal(len(expected))
    return is_correct, marks


def _grade_coding(db: Session, question, answer, max_marks: Decimal):
    """Execute the submitted code against every configured test case.

    Marks are proportional to the per-case weights. When the question has
    no coding configuration or no test cases, returns None so the answer
    stays in the manual-evaluation queue.
    """
    config = db.query(CodingQuestion).filter(
        CodingQuestion.question_id == question.id
    ).first()
    if not config:
        return None

    cases = db.query(CodingTestCase).filter(
        CodingTestCase.coding_question_id == config.id
    ).order_by(CodingTestCase.sort_order, CodingTestCase.id).all()
    if not cases:
        return None

    if not answer.code_text or not answer.code_text.strip():
        return False, ZERO

    results = run_test_cases(
        config.language, answer.code_text, cases,
        time_limit=config.time_limit,
    )

    total_weight = sum(Decimal(str(c.marks)) for c in cases)
    earned = sum(
        Decimal(str(c.marks))
        for c, r in zip(cases, results)
        if r.passed
    )
    if total_weight <= 0:
        return None

    is_correct = earned == total_weight
    marks = (max_marks * earned / total_weight).quantize(Decimal("0.01"))
    return is_correct, marks


GRADERS = {
    "multichoice": _grade_multichoice,
    "multiselect": _grade_multiselect,
    "truefalse": _grade_truefalse,
    "shortanswer": _grade_shortanswer,
    "numerical": _grade_numerical,
    "match": _grade_match,
    "multianswer": _grade_multianswer,
    # Image questions are single-choice over text/image options.
    "image": _grade_multichoice,
    # Calculated variants all evaluate the stored formula + tolerance.
    "calculated": _grade_calculated,
    "calculatedsimple": _grade_calculated,
    "calculatedmulti": _grade_calculated,
    # Gap-select dropdown answers and ordering sequences are objective.
    "selectmissing": _grade_selectmissing,
    "ordering": _grade_ordering,
    # Coding questions auto-grade via subprocess test-case execution when
    # a config + test cases exist; otherwise the grader returns None.
    "coding": _grade_coding,
}


def auto_grade_answer(db: Session, question, answer, max_marks: Decimal):
    """
    Auto-grade an answer when the question type supports it.

    Returns (is_correct, marks_obtained) or None if the type requires
    manual evaluation (essay, coding, description, etc.).
    """
    grader = GRADERS.get(question.type)
    if grader is None:
        return None

    return grader(db, question, answer, max_marks)


def answer_has_content(answer) -> bool:
    """True when the student actually provided an answer."""
    return (
        answer.selected_option_id is not None
        or bool(answer.selected_option_ids)
        or bool(answer.match_answers)
        or bool(answer.answer_text and answer.answer_text.strip())
        or bool(answer.code_text and answer.code_text.strip())
        or bool(answer.answer_file)
    )
