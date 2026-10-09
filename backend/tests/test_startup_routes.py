"""Startup and router-registration checks against an isolated SQLite file."""

import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import dispose_engines, get_engine
from app.database.db import init_db
from app.main import app
from app.models import Flashcard, Note
from tests.test_api import create_sample_pdf_bytes


@pytest.fixture
def client(monkeypatch):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_PATH", db_path)
    init_db(db_path)
    with TestClient(app) as test_client:
        yield test_client
    dispose_engines()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_health_and_root(client):
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "healthy"
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["status"] == "online"


def test_required_routers_are_registered():
    paths = {getattr(route, "path", "") for route in app.routes}
    expected = {
        "/health",
        "/api/exam/parse",
        "/api/exam/questions",
        "/api/analytics/coverage",
        "/api/analytics/planner",
        "/api/ingest/upload",
        "/api/documents/{document_id}",
        "/api/documents/{document_id}/contract",
        "/api/process/{document_id}",
        "/api/ocr/{document_id}/review",
        "/api/exports/markdown/{document_id}",
        "/api/exports/pdf/{document_id}",
        "/api/exports/anki/{document_id}",
    }
    missing = expected - paths
    assert not missing, f"missing routes: {missing}"


def test_exam_invalid_extension_is_rejected(client):
    response = client.post(
        "/api/exam/parse",
        files={"file": ("paper.docx", b"fake", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_document_not_found(client):
    response = client.get("/api/documents/99999")
    assert response.status_code == 404


def test_process_missing_document(client):
    response = client.post("/api/process/99999")
    assert response.status_code == 404


def test_ocr_review_missing_document_is_empty(client):
    response = client.get("/api/ocr/99999/review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == 99999
    assert payload["count"] == 0
    assert payload["items"] == []


def test_analytics_coverage_and_planner_after_exam_parse(client):
    empty = client.get("/api/analytics/coverage")
    assert empty.status_code in (200, 422)

    pdf_bytes = create_sample_pdf_bytes()
    parsed = client.post(
        "/api/exam/parse?save_to_db=true",
        files={"file": ("DBMS_2025_EndSem.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["total_questions"] >= 4

    coverage = client.get("/api/analytics/coverage")
    assert coverage.status_code == 200, coverage.text
    body = coverage.json()
    assert "summary" in body
    assert body["summary"]["n_questions"] >= 4
    assert "never_asked_topics" in body
    assert "heatmap" in body

    plan = client.get("/api/analytics/planner", params={"days_left": 14, "hours_per_day": 2})
    assert plan.status_code == 200, plan.text
    assert isinstance(plan.json(), dict)


def test_ingest_process_and_export_artifacts(client, monkeypatch):
    import fitz

    def fake_store(cleaned_pages, db, lecture_date=None):
        ids = []
        for page in cleaned_pages:
            note = Note(
                document_id=page.document_id,
                page=page.page_number,
                text="Integration note body",
                latex="x^2",
                lecture_date=lecture_date,
            )
            db.add(note)
            db.flush()
            ids.append(note.id)
        return ids

    monkeypatch.setattr("app.routers.processing.is_tesseract_available", lambda: True)
    monkeypatch.setattr("app.routers.processing.run_and_store", fake_store)
    monkeypatch.setattr(
        "app.routers.processing._structure_notes",
        lambda db, ids: {"status": "skipped", "reason": "GEMINI_API_KEY is not set"},
    )

    pdf = fitz.open()
    page = pdf.new_page(width=200, height=200)
    page.insert_text((20, 40), "Lecture board sample")
    pdf_bytes = pdf.tobytes()
    pdf.close()

    invalid = client.post(
        "/api/ingest/upload",
        data={"doc_type": "not_a_type"},
        files={"files": ("board.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert invalid.status_code == 400

    uploaded = client.post(
        "/api/ingest/upload",
        data={"doc_type": "lecture_board", "lecture_date": "2026-09-22"},
        files={"files": ("board.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document_id"]
    assert document_id > 0

    meta = client.get(f"/api/documents/{document_id}")
    assert meta.status_code == 200
    assert meta.json()["type"] == "lecture_board"

    contract = client.get(f"/api/documents/{document_id}/contract")
    assert contract.status_code == 200
    pages = contract.json()
    assert isinstance(pages, list) and pages
    assert pages[0]["document_id"] == document_id
    assert pages[0]["doc_type"] == "lecture_board"

    processed = client.post(f"/api/process/{document_id}")
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "success"
    note_ids = processed.json()["note_ids"]
    assert note_ids

    session = Session(bind=get_engine())
    try:
        session.add(Flashcard(note_id=note_ids[0], front="Q", back="A"))
        session.commit()
    finally:
        session.close()

    markdown = client.get(f"/api/exports/markdown/{document_id}")
    assert markdown.status_code == 200
    assert "ExamLens Notes Export" in markdown.text
    assert "Integration note body" in markdown.text

    pdf_export = client.get(f"/api/exports/pdf/{document_id}")
    assert pdf_export.status_code == 200
    assert pdf_export.content[:4] == b"%PDF"

    anki = client.get(f"/api/exports/anki/{document_id}")
    assert anki.status_code == 200
    assert b"Front" in anki.content
    assert b"Integration note body" in anki.content
