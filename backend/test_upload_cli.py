"""
test_upload_cli.py
==================
Quick CLI script to test uploading and parsing a PDF directly through FastAPI TestClient.
"""

from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

pdf_path = Path(__file__).resolve().parent.parent / "sample_exam_paper.pdf"

if not pdf_path.exists():
    print(f"File not found: {pdf_path}")
    exit(1)

print(f"Uploading and parsing {pdf_path.name} ...\n")

with open(pdf_path, "rb") as f:
    response = client.post(
        "/api/exam/parse?save_to_db=true",
        files={"file": (pdf_path.name, f, "application/pdf")}
    )

if response.status_code == 200:
    data = response.json()
    print("=" * 70)
    print("SUCCESSFULLY PARSED & SAVED TO DATABASE")
    print("=" * 70)
    print(f"Document ID     : {data['document_id']}")
    print(f"File Name       : {data['file_name']}")
    print(f"Exam Year       : {data['year']}")
    print(f"Exam Type       : {data['exam_type']}")
    print(f"Total Pages     : {data['total_pages']}")
    print(f"Questions Found : {data['total_questions']}")
    print("-" * 70)
    print("EXTRACTED QUESTIONS PREVIEW:")
    print("-" * 70)
    for i, q in enumerate(data["questions"], 1):
        sec = f"Sec: {q['section']}" if q['section'] else "No Sec"
        marks = f"{q['marks']} marks" if q['marks'] else "No marks"
        text_preview = q['raw_text'].replace('\n', ' ')
        if len(text_preview) > 65:
            text_preview = text_preview[:62] + "..."
        print(f"[{i:02d}] (Page {q['page']}, {sec:<7}, {marks:<8}) -> {text_preview}")
    print("=" * 70)
else:
    print(f"Error {response.status_code}: {response.text}")
