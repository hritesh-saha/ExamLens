"""
test_api.py
===========
Integration tests for ExamLens FastAPI endpoints using TestClient.
"""

import io
import os
import tempfile
import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

from app.database.db import init_db
from app.main import app


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """Ensure tests run against a clean temporary database."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_PATH", db_path)
    init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def create_sample_pdf_bytes() -> bytes:
    """Create an in-memory PDF with realistic exam content."""
    doc = fitz.open()
    page = doc.new_page()
    text = """DEPARTMENT OF COMPUTER SCIENCE
End Semester Examination 2025
Database Management Systems

Time: 3 Hours                          Max Marks: 100

SECTION A
Answer all questions. Each carries 5 marks.

1. Explain the three-schema architecture of DBMS. [5 marks]
2. What is a primary key? Give an example. [5 marks]

SECTION B
Answer any two questions. Each carries 10 marks.

3. Explain 1NF, 2NF, 3NF and BCNF with examples. [10 marks]
4. What are ACID properties in transaction processing? [10 marks]
"""
    page.insert_text((50, 72), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# ── Health & Root ────────────────────────────────────────────────────────────

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "ExamLens API"
    assert data["status"] == "online"


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ── Syllabus Endpoints ───────────────────────────────────────────────────────

def test_get_syllabus_topics(client):
    response = client.get("/api/syllabus/topics")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_upload_syllabus_csv(client):
    csv_data = "topic_code,name,syllabus_unit\nTEST-01,Test Topic,Unit 1\n"
    files = {
        "file": ("syllabus.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")
    }
    response = client.post("/api/syllabus/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["topics_count"] == 1

    # Verify topic is in database
    topics_res = client.get("/api/syllabus/topics")
    topics = topics_res.json()
    assert any(t["topic_code"] == "TEST-01" for t in topics)


def test_upload_syllabus_invalid_filetype(client):
    files = {
        "file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")
    }
    response = client.post("/api/syllabus/upload", files=files)
    assert response.status_code == 400


# ── Exam Parse & Query Endpoints ─────────────────────────────────────────────

def test_parse_exam_pdf_success(client):
    pdf_bytes = create_sample_pdf_bytes()
    files = {
        "file": ("DBMS_2025_EndSem.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }
    response = client.post("/api/exam/parse?save_to_db=true", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["year"] == 2025
    assert data["exam_type"] == "End Semester"
    assert data["total_questions"] >= 4
    assert len(data["questions"]) >= 4

    doc_id = data["document_id"]
    assert doc_id > 0

    # Verify document listing
    doc_res = client.get(f"/api/exam/documents/{doc_id}")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["file_name"] == "DBMS_2025_EndSem.pdf"
    assert len(doc_data["questions"]) >= 4


def test_parse_exam_pdf_invalid_extension(client):
    files = {
        "file": ("paper.docx", io.BytesIO(b"fake docx"), "application/octet-stream")
    }
    response = client.post("/api/exam/parse", files=files)
    assert response.status_code == 400


def test_get_document_not_found(client):
    response = client.get("/api/exam/documents/99999")
    assert response.status_code == 404


def test_query_questions_filters(client):
    # Parse a paper first
    pdf_bytes = create_sample_pdf_bytes()
    files = {
        "file": ("DBMS_2025_EndSem.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }
    client.post("/api/exam/parse?save_to_db=true", files=files)

    # Query all
    res_all = client.get("/api/exam/questions")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 4

    # Filter by year
    res_2025 = client.get("/api/exam/questions?year=2025")
    assert res_2025.status_code == 200
    assert len(res_2025.json()) >= 4

    # Filter by section
    res_sec_a = client.get("/api/exam/questions?section=A")
    assert res_sec_a.status_code == 200
    assert all(q["section"] == "A" for q in res_sec_a.json())
