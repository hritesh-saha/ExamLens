import os
import uuid
import pymupdf
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document
from app.services.ingestion import process_images_to_pdf, rasterize_pdf

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])

UPLOAD_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "uploads")

@router.post("/upload")
async def upload_document(
    doc_type: str = Form(...),  # "lecture_board" or "question_paper"
    lecture_date: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    if doc_type not in ["lecture_board", "question_paper"]:
        raise HTTPException(status_code=400, detail="Invalid doc_type")

    doc_uuid = str(uuid.uuid4())
    doc_dir = os.path.join(UPLOAD_BASE, doc_uuid)
    os.makedirs(doc_dir, exist_ok=True)

    timestamp = lecture_date
    final_pdf_path = os.path.join(doc_dir, "document.pdf")

    # Check file formats
    is_pdf = len(files) == 1 and files[0].filename.endswith(".pdf")

    if is_pdf:
        content = await files[0].read()
        with open(final_pdf_path, "wb") as f:
            f.write(content)
        total_pages = len(pymupdf.open(final_pdf_path))
    else:
        # Array of images: sort by EXIF and merge into single PDF
        image_tuples = []
        for file in files:
            file_bytes = await file.read()
            image_tuples.append((file.filename, file_bytes))

        pdf_bytes, exif_ts = process_images_to_pdf(image_tuples)
        if not timestamp and exif_ts:
            timestamp = exif_ts

        with open(final_pdf_path, "wb") as f:
            f.write(pdf_bytes)
        
        total_pages = len(image_tuples)

    # Save metadata to DB
    doc_record = Document(
        type=doc_type,
        source_pages=total_pages,
        timestamp=timestamp,
        file_path=final_pdf_path
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    # Rasterize PDF pages to 300 DPI images for downstream processing
    pages_dir = os.path.join(doc_dir, "pages")
    rasterize_pdf(pdf_bytes=open(final_pdf_path, "rb").read(), output_dir=pages_dir, dpi=300)

    return {
        "status": "success",
        "document_id": doc_record.id,
        "type": doc_record.type,
        "source_pages": doc_record.source_pages,
        "timestamp": doc_record.timestamp
    }