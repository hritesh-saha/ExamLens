from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.database.db import get_questions_by_document, insert_questions_batch
from app.exam_parser.parser import parse_question_paper
from app.models import Document
from app.ocr.store import run_and_store
from app.ocr.tesseract_runtime import is_tesseract_available
from app.routers.documents import get_shared_contract_payload
from app.services.note__service import (
    GeminiNotConfiguredError,
    NoteStructurer,
)
from app.vision.pipeline import process_board_images

router = APIRouter(prefix="/api/process", tags=["Processing Pipeline"])

_TESSERACT_HELP = (
    "Tesseract OCR is not installed or not reachable. "
    "Install the UB-Mannheim Windows build from "
    "https://github.com/UB-Mannheim/tesseract/wiki "
    "and set TESSERACT_PATH in backend/.env."
)


def _structure_notes(db: Session, note_ids: list[int]) -> dict:
    if not note_ids:
        return {"status": "skipped", "reason": "no notes to structure"}
    try:
        return NoteStructurer().structure_notes(session=db, note_ids=note_ids)
    except GeminiNotConfiguredError as exc:
        return {"status": "skipped", "reason": str(exc)}
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


@router.post("/{document_id}")
def trigger_processing_pipeline(document_id: int, db: Session = Depends(get_db)):
    """
    Integration hub: SharedPageContract → Vision / OCR / exam parser.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    shared_contract = get_shared_contract_payload(document_id, db)

    try:
        if doc.type == "lecture_board":
            cleaned_pages = process_board_images(shared_contract)
            if not cleaned_pages:
                raise HTTPException(
                    status_code=500,
                    detail="Vision produced no cleaned pages",
                )
            if not is_tesseract_available():
                raise HTTPException(status_code=503, detail=_TESSERACT_HELP)
            note_ids = run_and_store(cleaned_pages, db, lecture_date=doc.timestamp)
            structuring = _structure_notes(db, note_ids)
            db.commit()
            return {
                "status": "success",
                "message": f"Pipeline completed for {doc.type}",
                "cleaned_pages": len(cleaned_pages),
                "note_ids": note_ids,
                "structuring": structuring,
            }

        if doc.type == "question_paper":
            existing = get_questions_by_document(doc.id)
            if existing:
                question_count = len(existing)
            else:
                parsed = parse_question_paper(doc.file_path, document_id=doc.id)
                for question in parsed.questions:
                    question.document_id = doc.id
                question_count = insert_questions_batch(parsed.questions)
            db.commit()
            return {
                "status": "success",
                "message": f"Pipeline completed for {doc.type}",
                "question_count": question_count,
            }

        raise HTTPException(status_code=400, detail=f"Unsupported document type: {doc.type}")

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Pipeline failure: {str(e)}")
