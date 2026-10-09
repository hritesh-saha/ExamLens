"""
test_integration.py
===================
End-to-end HTTP workflow against a running ExamLens API.

Requires:
  uvicorn app.main:app --reload   (from the backend directory)
  pip package: requests

Uses the repo-root sample PDF at ../sample_exam_paper.pdf
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

BASE_URL = os.environ.get("EXAMLENS_BASE_URL", "http://localhost:8000")
SAMPLE_PDF = Path(__file__).resolve().parent.parent / "sample_exam_paper.pdf"


def _ok(step: str, detail: str = "") -> None:
    extra = f" {detail}" if detail else ""
    print(f"[OK] {step}{extra}")


def _fail(step: str, response: requests.Response | None = None, extra: str = "") -> None:
    body = ""
    if response is not None:
        body = f" [{response.status_code}] {response.text[:500]}"
    print(f"[FAIL] {step}{body}{extra}")
    sys.exit(1)


def _database_path() -> Path:
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parent / "_verify.db"


def _seed_notes_for_export(document_id: int) -> None:
    """Insert one Note + Flashcard so export can be validated without OCR."""
    from sqlalchemy.orm import Session

    from app.database import dispose_engines, get_engine
    from app.models import Flashcard, Note

    os.environ.setdefault("DATABASE_PATH", str(_database_path()))
    session = Session(bind=get_engine())
    try:
        existing = (
            session.query(Note).filter(Note.document_id == document_id).first()
        )
        if existing is None:
            existing = Note(
                document_id=document_id,
                page=1,
                text="Integration note body",
                latex="x^2",
            )
            session.add(existing)
            session.flush()
        has_card = (
            session.query(Flashcard).filter(Flashcard.note_id == existing.id).first()
        )
        if has_card is None:
            session.add(Flashcard(note_id=existing.id, front="Q", back="A"))
        session.commit()
    finally:
        session.close()
        dispose_engines()


def run_tests() -> None:
    print("--- ExamLens end-to-end integration ---\n")
    print(f"API: {BASE_URL}")
    print(f"PDF: {SAMPLE_PDF}\n")

    if not SAMPLE_PDF.is_file():
        _fail("Sample PDF missing", extra=f": {SAMPLE_PDF}")

    # 1. Upload
    print("1. POST /api/ingest/upload")
    with SAMPLE_PDF.open("rb") as handle:
        response = requests.post(
            f"{BASE_URL}/api/ingest/upload",
            files={"files": (SAMPLE_PDF.name, handle, "application/pdf")},
            data={"doc_type": "lecture_board", "lecture_date": "2026-09-22"},
            timeout=120,
        )
    if response.status_code != 200:
        _fail("Upload", response)
    upload = response.json()
    document_id = upload.get("document_id")
    if not document_id:
        _fail("Upload did not return document_id", response)
    _ok("Upload", f"document_id={document_id} pages={upload.get('source_pages')}")
    print(json.dumps(upload, indent=2))
    print()

    # 2. Document metadata
    print(f"2. GET /api/documents/{document_id}")
    response = requests.get(f"{BASE_URL}/api/documents/{document_id}", timeout=30)
    if response.status_code != 200:
        _fail("Document metadata", response)
    metadata = response.json()
    required_meta = {"id", "type", "source_pages", "file_path"}
    missing = required_meta - set(metadata)
    if missing:
        _fail(f"Document metadata missing fields {missing}", response)
    _ok("Document metadata")
    print(json.dumps(metadata, indent=2))
    print()

    # 3. SharedPageContract for Vision / parsing
    print(f"3. GET /api/documents/{document_id}/contract")
    response = requests.get(
        f"{BASE_URL}/api/documents/{document_id}/contract", timeout=60
    )
    if response.status_code != 200:
        _fail("Shared contract", response)
    contract = response.json()
    if not isinstance(contract, list) or not contract:
        _fail("Shared contract was empty or not a list", response)
    required_contract = {
        "document_id",
        "page_number",
        "doc_type",
        "image_path",
        "embedded_text",
        "timestamp",
    }
    first = contract[0]
    missing = required_contract - set(first)
    if missing:
        _fail(f"Contract page missing fields {missing}", response)
    if first["document_id"] != document_id:
        _fail("Contract document_id does not match upload", response)
    if first["doc_type"] != "lecture_board":
        _fail("Contract doc_type is not lecture_board", response)
    _ok("Shared contract", f"{len(contract)} page(s)")
    print(json.dumps(first, indent=2))
    print()

    # 4. Master processing pipeline (Member 1 Vision + Member 2 OCR)
    print(f"4. POST /api/process/{document_id}")
    response = requests.post(f"{BASE_URL}/api/process/{document_id}", timeout=180)
    if response.status_code == 503 and "Tesseract" in response.text:
        print(
            "[BLOCKED] Processing reached Vision but Tesseract is not installed. "
            "Install UB-Mannheim Tesseract and set TESSERACT_PATH in backend/.env."
        )
        print(response.text[:400])
        print()
    elif response.status_code != 200:
        _fail("Processing pipeline", response)
    else:
        processed = response.json()
        if processed.get("status") != "success":
            _fail("Processing pipeline status was not success", response)
        _ok(
            "Processing pipeline",
            f"{processed.get('message', '')} notes={processed.get('note_ids')}",
        )
        print(json.dumps(processed, indent=2))
        print()

    # 5. Exports — 404 is correct when no notes/flashcards exist.
    # /api/process persists OCR notes but does not generate Flashcard rows.
    print("5. Export endpoints")
    md_probe = requests.get(
        f"{BASE_URL}/api/exports/markdown/{document_id}", timeout=60
    )
    if md_probe.status_code == 404:
        _seed_notes_for_export(document_id)
        _ok("Seeded note/flashcard for export (OCR did not persist notes)")
    else:
        _seed_notes_for_export(document_id)
        _ok("Ensured flashcard exists for Anki export (pipeline does not create cards)")

    export_specs = [
        ("markdown", f"/api/exports/markdown/{document_id}", "text/markdown"),
        ("pdf", f"/api/exports/pdf/{document_id}", "application/pdf"),
        ("anki", f"/api/exports/anki/{document_id}", "text/csv"),
    ]
    for name, path, expected_type in export_specs:
        response = requests.get(f"{BASE_URL}{path}", timeout=60)
        if response.status_code != 200:
            _fail(f"{name} export", response)
        content_type = (response.headers.get("content-type") or "").split(";")[0]
        if expected_type not in content_type and content_type not in (
            expected_type,
            "application/octet-stream",
        ):
            _fail(
                f"{name} export content-type {content_type!r} "
                f"(expected {expected_type})",
                response,
            )
        if name == "markdown":
            if b"ExamLens Notes Export" not in response.content:
                _fail("markdown export missing expected heading", response)
        if name == "pdf" and not response.content.startswith(b"%PDF"):
            _fail("pdf export is not a PDF artifact", response)
        if name == "anki" and b"Front" not in response.content:
            _fail("anki export missing CSV header", response)
        if len(response.content) < 8:
            _fail(f"{name} export artifact is empty", response)
        _ok(f"{name} export", f"200 {content_type} ({len(response.content)} bytes)")

    print("\n--- Integration sequence finished ---")


if __name__ == "__main__":
    run_tests()
