"""
exam_routes.py
==============
FastAPI router for ExamLens exam parser & question repository endpoints.

Endpoints:
  POST /api/exam/parse             - Upload and parse an exam PDF
  GET  /api/exam/documents         - List all parsed documents
  GET  /api/exam/documents/{id}    - Get document details & its questions
  GET  /api/exam/questions         - Filter/search questions (year, section, etc.)
  GET  /api/syllabus/topics        - List all syllabus topics
  POST /api/syllabus/upload        - Upload syllabus CSV to seed topics
"""

import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.database.db import (
    get_all_documents,
    get_all_questions,
    get_all_topics,
    get_document_by_id,
    get_questions_by_document,
    get_questions_by_year,
    save_parsed_document,
)
from app.exam_parser.models import ParsedDocument, Question
from app.exam_parser.parser import parse_question_paper
from app.syllabus.loader import load_syllabus_to_db

router = APIRouter(prefix="/api", tags=["Exam Parser & Syllabus"])


class ParseResponse(BaseModel):
    success: bool
    document_id: int
    file_name: str
    year: Optional[int] = None
    exam_type: Optional[str] = None
    total_pages: int
    total_questions: int
    questions: List[Question]


@router.post("/exam/parse", response_model=ParseResponse)
async def parse_exam_pdf(
    file: UploadFile = File(..., description="Exam paper PDF file to parse"),
    save_to_db: bool = Query(True, description="Whether to persist the parsed result to the database"),
):
    """
    Upload a Question Paper PDF and extract structured Question records.

    Pipeline:
      1. Save uploaded PDF temporarily
      2. Extract text with pdf_reader (fallback to OCR if scanned)
      3. Normalize text & extract document metadata (Year, Exam Type)
      4. Segment questions & extract question metadata (Marks, Section, etc.)
      5. Construct validated Question models
      6. (Optional) Save to SQLite database
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported (.pdf)",
        )

    # Save uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name
        shutil.copyfileobj(file.file, tmp)

    try:
        # Step 1: Run parser pipeline
        parsed_doc: ParsedDocument = parse_question_paper(
            pdf_path=tmp_path,
            document_id=0,  # Will be assigned if saved to DB
        )

        doc_id = 0
        if save_to_db:
            doc_id = save_parsed_document(
                parsed_doc=parsed_doc,
                file_name=file.filename,
                file_path=tmp_path,
            )
            # Update document_id in returned model
            parsed_doc.document_id = doc_id
            for q in parsed_doc.questions:
                q.document_id = doc_id

        return ParseResponse(
            success=True,
            document_id=doc_id,
            file_name=file.filename,
            year=parsed_doc.year,
            exam_type=parsed_doc.exam_type,
            total_pages=parsed_doc.total_pages,
            total_questions=len(parsed_doc.questions),
            questions=parsed_doc.questions,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse PDF: {str(e)}",
        )
    finally:
        # Keep temp file if saved, or remove if needed
        pass


@router.get("/exam/documents")
async def list_documents() -> List[Dict[str, Any]]:
    """Retrieve list of all parsed question papers in the database."""
    return get_all_documents()


@router.get("/exam/documents/{document_id}")
async def get_document(document_id: int) -> Dict[str, Any]:
    """Retrieve metadata and all extracted questions for a given document."""
    doc = get_document_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    questions = get_questions_by_document(document_id)
    doc["questions"] = questions
    doc["total_questions"] = len(questions)
    return doc


@router.get("/exam/questions")
async def query_questions(
    year: Optional[int] = Query(None, description="Filter by year"),
    document_id: Optional[int] = Query(None, description="Filter by document ID"),
    section: Optional[str] = Query(None, description="Filter by section (e.g. A, B)"),
) -> List[Dict[str, Any]]:
    """
    Query questions with optional filtering.
    """
    if document_id is not None:
        questions = get_questions_by_document(document_id)
    elif year is not None:
        questions = get_questions_by_year(year)
    else:
        questions = get_all_questions()

    if section:
        sec_upper = section.strip().upper()
        questions = [q for q in questions if (q.get("section") or "").upper() == sec_upper]

    return questions


# ═══════════════════════════════════════════════════════════════════
# SYLLABUS TOPIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/syllabus/topics")
async def list_topics() -> List[Dict[str, Any]]:
    """Retrieve all syllabus topics loaded in the system."""
    return get_all_topics()


@router.post("/syllabus/upload")
async def upload_syllabus_csv(
    file: UploadFile = File(..., description="Syllabus CSV file"),
) -> Dict[str, Any]:
    """
    Upload and parse a CSV file to populate or update the syllabus topics table.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported (.csv)",
        )

    content = (await file.read()).decode("utf-8-sig", errors="replace")
    try:
        count = load_syllabus_to_db(content)
        return {
            "success": True,
            "message": f"Successfully loaded {count} topics from {file.filename}.",
            "topics_count": count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load syllabus: {str(e)}",
        )
