"""Processing hub: Vision → OCR notes, without requiring live Tesseract/Gemini."""

import io

import pytest
from fastapi.testclient import TestClient

from app.database import dispose_engines
from app.database.db import init_db
from app.main import app
from app.models import Note
from app.vision.models import CleanedPage


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = str(tmp_path / "proc.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    init_db(db_path)
    with TestClient(app) as test_client:
        yield test_client
    dispose_engines()


def _tiny_pdf_bytes():
    import fitz

    pdf = fitz.open()
    page = pdf.new_page(width=200, height=200)
    page.insert_text((20, 40), "Lecture board sample")
    data = pdf.tobytes()
    pdf.close()
    return data


def test_process_lecture_board_persists_notes_when_ocr_is_injected(client, monkeypatch):
    def fake_store(cleaned_pages, db, lecture_date=None):
        ids = []
        for page in cleaned_pages:
            note = Note(
                document_id=page.document_id,
                page=page.page_number,
                text="Newton second law",
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

    uploaded = client.post(
        "/api/ingest/upload",
        data={"doc_type": "lecture_board", "lecture_date": "2026-09-22"},
        files={"files": ("board.pdf", io.BytesIO(_tiny_pdf_bytes()), "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document_id"]

    processed = client.post(f"/api/process/{document_id}")
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert body["status"] == "success"
    assert body["note_ids"]
    assert body["structuring"]["status"] == "skipped"

    notes = client.get(f"/api/exports/markdown/{document_id}")
    assert notes.status_code == 200
    assert "Newton second law" in notes.text


def test_process_returns_503_when_tesseract_missing(client, monkeypatch):
    monkeypatch.setattr("app.routers.processing.is_tesseract_available", lambda: False)
    monkeypatch.setattr(
        "app.routers.processing.process_board_images",
        lambda pages: [
            CleanedPage(
                document_id=pages[0].document_id,
                page_number=1,
                source_page_numbers=[1],
                doc_type="lecture_board",
                image_path=pages[0].image_path,
                regions=[],
            )
        ],
    )

    uploaded = client.post(
        "/api/ingest/upload",
        data={"doc_type": "lecture_board"},
        files={"files": ("board.pdf", io.BytesIO(_tiny_pdf_bytes()), "application/pdf")},
    )
    document_id = uploaded.json()["document_id"]
    processed = client.post(f"/api/process/{document_id}")
    assert processed.status_code == 503
    assert "Tesseract" in processed.json()["detail"]


def test_question_paper_process_does_not_duplicate_questions(client):
    from tests.test_api import create_sample_pdf_bytes

    uploaded = client.post(
        "/api/ingest/upload",
        data={"doc_type": "question_paper"},
        files={"files": ("exam.pdf", io.BytesIO(create_sample_pdf_bytes()), "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document_id"]

    first = client.post(f"/api/process/{document_id}")
    assert first.status_code == 200, first.text
    count = first.json()["question_count"]
    assert count >= 4

    second = client.post(f"/api/process/{document_id}")
    assert second.status_code == 200, second.text
    assert second.json()["question_count"] == count

    listed = client.get("/api/exam/questions")
    assert listed.status_code == 200
    assert len(listed.json()) == count
