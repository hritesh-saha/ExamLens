"""Persistence: JSON sidecar (word-level data for the edit UI) + Note rows.

Note has no column for word boxes, so the full result lives in
output/ocr/doc_<id>/page_<n>.json and Note gets text / latex / confidence.
No schema change is needed.
"""

import json
from pathlib import Path
from typing import Optional

from app.ocr.models import PageOCRResult
from app.ocr.pipeline import OUTPUT_ROOT, run_ocr_and_math


def _path(doc_id: int, page: int) -> Path:
    return OUTPUT_ROOT / f"doc_{doc_id}" / f"page_{page}.json"


def save_result(res: PageOCRResult) -> Path:
    p = _path(res.document_id, res.page_number)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(res.model_dump_json(indent=2), encoding="utf-8")
    return p


def load_result(doc_id: int, page: int) -> Optional[PageOCRResult]:
    p = _path(doc_id, page)
    return PageOCRResult.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None


def list_pages(doc_id: int) -> list[int]:
    d = OUTPUT_ROOT / f"doc_{doc_id}"
    return sorted(int(f.stem.split("_")[1]) for f in d.glob("page_*.json")) if d.exists() else []


def upsert_note(db, res: PageOCRResult, lecture_date: Optional[str] = None) -> int:
    from app.models import Note
    note = db.query(Note).filter(
        Note.document_id == res.document_id, Note.page == res.page_number
    ).first()
    if note is None:
        note = Note(document_id=res.document_id, page=res.page_number)
        db.add(note)
    note.text = res.text
    note.latex = res.latex
    note.confidence = res.confidence
    note.lecture_date = lecture_date or res.timestamp or note.lecture_date
    db.flush()
    return note.id


def run_and_store(cleaned_pages, db, lecture_date: Optional[str] = None) -> list[int]:
    """What Member 6 calls from /api/process. Returns Note ids."""
    ids = []
    for res in run_ocr_and_math(cleaned_pages):
        save_result(res)
        ids.append(upsert_note(db, res, lecture_date))
    return ids
