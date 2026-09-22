from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Note, Flashcard, Question
from app.services.export import generate_markdown_export, generate_pdf_export, generate_anki_csv_export

router = APIRouter(prefix="/api/exports", tags=["Exports"])

@router.get("/markdown/{document_id}")
def export_markdown(document_id: int, db: Session = Depends(get_db)):
    notes = db.query(Note).filter(Note.document_id == document_id).order_by(Note.page).all()
    if not notes:
        raise HTTPException(status_code=404, detail="No notes found for document")

    md_content = generate_markdown_export(notes)
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=document_{document_id}_notes.md"}
    )

@router.get("/pdf/{document_id}")
def export_pdf(document_id: int, db: Session = Depends(get_db)):
    notes = db.query(Note).filter(Note.document_id == document_id).order_by(Note.page).all()
    if not notes:
        raise HTTPException(status_code=404, detail="No notes found for document")

    pdf_bytes = generate_pdf_export(notes)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=document_{document_id}_notes.pdf"}
    )

@router.get("/anki/{document_id}")
def export_anki(document_id: int, db: Session = Depends(get_db)):
    results = db.query(Flashcard, Note, Question)\
                .join(Note, Flashcard.note_id == Note.id)\
                .outerjoin(Question, Flashcard.linked_question_id == Question.id)\
                .filter(Note.document_id == document_id)\
                .all()

    if not results:
        raise HTTPException(status_code=404, detail="No flashcards found for document")

    csv_content = generate_anki_csv_export(results)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=document_{document_id}_flashcards.csv"}
    )