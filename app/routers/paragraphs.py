from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.paragraph_passage import ParagraphPassage
from app.models.paragraph_question import ParagraphQuestion
from app.models.question import Question
from app.models.question_paragraph import QuestionParagraph
from app.schemas.paragraph import (
    ParagraphPassageCreate,
    ParagraphPassageUpdate,
    ParagraphPassageResponse,
    ParagraphQuestionLinkCreate,
    ParagraphQuestionLinkResponse,
    QuestionParagraphLinkSet,
)
from app.utils.dependencies import get_current_user, require_role


router = APIRouter(
    prefix="/api/paragraphs",
    tags=["Paragraph Questions"]
)


# CREATE PASSAGE

@router.post(
    "/",
    response_model=ParagraphPassageResponse,
    status_code=status.HTTP_201_CREATED
)
def create_passage(
    data: ParagraphPassageCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    passage = ParagraphPassage(
        content=data.content,
        created_by=current_user.id
    )

    db.add(passage)
    db.commit()
    db.refresh(passage)

    return passage


# GET ALL PASSAGES

@router.get("/", response_model=list[ParagraphPassageResponse])
def get_passages(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(ParagraphPassage).order_by(
        ParagraphPassage.id.desc()
    ).all()


# GET ONE PASSAGE

@router.get("/{passage_id}", response_model=ParagraphPassageResponse)
def get_passage(
    passage_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    passage = db.query(ParagraphPassage).filter(
        ParagraphPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    return passage


# UPDATE PASSAGE

@router.put("/{passage_id}", response_model=ParagraphPassageResponse)
def update_passage(
    passage_id: int,
    data: ParagraphPassageUpdate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    passage = db.query(ParagraphPassage).filter(
        ParagraphPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    passage.content = data.content

    db.commit()
    db.refresh(passage)

    return passage


# DELETE PASSAGE

@router.delete("/{passage_id}")
def delete_passage(
    passage_id: int,
    current_user=Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    passage = db.query(ParagraphPassage).filter(
        ParagraphPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    links = db.query(ParagraphQuestion).filter(
        ParagraphQuestion.passage_id == passage_id
    ).all()

    for link in links:
        db.delete(link)

    db.delete(passage)
    db.commit()

    return {"message": "Paragraph passage deleted successfully"}


# LINK A QUESTION TO A PASSAGE

@router.post(
    "/{passage_id}/questions",
    response_model=ParagraphQuestionLinkResponse,
    status_code=status.HTTP_201_CREATED
)
def link_question(
    passage_id: int,
    data: ParagraphQuestionLinkCreate,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    passage = db.query(ParagraphPassage).filter(
        ParagraphPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    question = db.query(Question).filter(
        Question.id == data.question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question.type == "paragraph":
        raise HTTPException(
            status_code=400,
            detail="A paragraph question cannot be linked as a child question"
        )

    existing = db.query(ParagraphQuestion).filter(
        ParagraphQuestion.passage_id == passage_id,
        ParagraphQuestion.question_id == data.question_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Question is already linked to this passage"
        )

    link = ParagraphQuestion(
        passage_id=passage_id,
        question_id=data.question_id,
        sort_order=data.sort_order
    )

    db.add(link)
    db.commit()
    db.refresh(link)

    return link


# GET QUESTIONS LINKED TO A PASSAGE

@router.get(
    "/{passage_id}/questions",
    response_model=list[ParagraphQuestionLinkResponse]
)
def get_linked_questions(
    passage_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    passage = db.query(ParagraphPassage).filter(
        ParagraphPassage.id == passage_id
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    return (
        db.query(ParagraphQuestion)
        .filter(ParagraphQuestion.passage_id == passage_id)
        .order_by(ParagraphQuestion.sort_order, ParagraphQuestion.id)
        .all()
    )


# UNLINK QUESTION FROM PASSAGE

@router.delete("/{passage_id}/questions/{question_id}")
def unlink_question(
    passage_id: int,
    question_id: int,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    link = db.query(ParagraphQuestion).filter(
        ParagraphQuestion.passage_id == passage_id,
        ParagraphQuestion.question_id == question_id
    ).first()

    if not link:
        raise HTTPException(status_code=404, detail="Question link not found")

    db.delete(link)
    db.commit()

    return {"message": "Question unlinked successfully"}


# ============================================================
# Paragraph-type questions: link child questions to a passage
# ============================================================

def _get_paragraph_question(question_id: int, db: Session) -> Question:
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.is_active == True
    ).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question.type != "paragraph":
        raise HTTPException(
            status_code=400,
            detail="Question is not a paragraph type"
        )

    return question


@router.get("/question/{question_id}")
def get_paragraph_links(
    question_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_paragraph_question(question_id, db)

    config = db.query(QuestionParagraph).filter(
        QuestionParagraph.question_id == question_id
    ).first()

    return {
        "question_id": question_id,
        "child_question_ids": (config.child_question_ids or [])
        if config else [],
    }


@router.post("/question/{question_id}")
def set_paragraph_links(
    question_id: int,
    data: QuestionParagraphLinkSet,
    current_user=Depends(require_role("admin", "teacher")),
    db: Session = Depends(get_db)
):
    _get_paragraph_question(question_id, db)

    ids = list(dict.fromkeys(data.question_ids))  # dedupe, keep order
    if not ids:
        raise HTTPException(
            status_code=400,
            detail="Select at least one question for this paragraph"
        )

    children = db.query(Question).filter(
        Question.id.in_(ids),
        Question.is_active == True
    ).all()
    found = {q.id: q for q in children}

    for qid in ids:
        child = found.get(qid)
        if not child:
            raise HTTPException(
                status_code=400,
                detail=f"Question {qid} not found or inactive"
            )
        if child.type in ("paragraph", "description"):
            raise HTTPException(
                status_code=400,
                detail=f"Question {qid} ({child.type}) cannot be a "
                       "paragraph child question"
            )

    config = db.query(QuestionParagraph).filter(
        QuestionParagraph.question_id == question_id
    ).first()

    if not config:
        config = QuestionParagraph(question_id=question_id)
        db.add(config)

    config.child_question_ids = ids
    db.commit()

    return {"question_id": question_id, "child_question_ids": ids}