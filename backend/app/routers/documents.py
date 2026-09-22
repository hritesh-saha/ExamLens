import os
import pymupdf
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document
from app.schemas import SharedPageContract, DocumentResponse, PageReorderRequest
from app.services.ingestion import rasterize_pdf

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/{document_id}/contract", response_model=List[SharedPageContract])
def get_shared_contract_payload(document_id: int, db: Session = Depends(get_db)):
    """
    Delivers the exact Day 1 shared interface contract to Vision, OCR, and Parsing engines.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_dir = os.path.dirname(doc.file_path)
    pages_dir = os.path.join(doc_dir, "pages")

    pdf_doc = pymupdf.open(doc.file_path)
    contracts = []

    for idx in range(len(pdf_doc)):
        page_num = idx + 1
        page = pdf_doc.load_page(idx)
        text_layer = page.get_text("text").strip()

        image_path = os.path.join(pages_dir, f"page_{page_num}.png")

        contracts.append(SharedPageContract(
            document_id=doc.id,
            page_number=page_num,
            doc_type=doc.type,
            image_path=image_path,
            embedded_text=text_layer if len(text_layer) > 0 else None,
            timestamp=doc.timestamp
        ))

    pdf_doc.close()
    return contracts

@router.post("/{document_id}/reorder")
def reorder_pages(document_id: int, payload: PageReorderRequest, db: Session = Depends(get_db)):
    """
    Reorders document pages according to user UI sequence and rebuilds the source PDF.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    src_pdf = pymupdf.open(doc.file_path)
    if len(payload.new_page_order) != len(src_pdf):
        raise HTTPException(status_code=400, detail="Page count mismatch")

    new_pdf = pymupdf.open()
    for orig_page_num in payload.new_page_order:
        # Convert 1-based index to 0-based index
        new_pdf.insert_pdf(src_pdf, from_page=orig_page_num - 1, to_page=orig_page_num - 1)

    src_pdf.close()
    new_pdf.save(doc.file_path, incremental=False, encryption=0)
    new_pdf.close()

    # Re-rasterize pages after reordering
    doc_dir = os.path.dirname(doc.file_path)
    pages_dir = os.path.join(doc_dir, "pages")
    with open(doc.file_path, "rb") as f:
        rasterize_pdf(f.read(), pages_dir, dpi=300)

    return {"status": "success", "reordered_sequence": payload.new_page_order}