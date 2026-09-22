"""
Smoke test: run the full parse pipeline on a synthetic PDF.
Run from project root:
    venv\\Scripts\\python backend\\app\\exam_parser\\smoke_test.py
"""
import sys, os, tempfile, json
# Force UTF-8 output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pymupdf
from app.exam_parser.parser import parse_question_paper

# ── Create a realistic synthetic exam PDF ─────────────────────────
def make_exam_pdf() -> str:
    doc = pymupdf.open()
    page = doc.new_page()
    lines = [
        "XYZ UNIVERSITY",
        "B.Tech CSE — Semester 7",
        "END SEMESTER EXAMINATION NOVEMBER 2025",
        "Subject: Database Management Systems (CS401)",
        "Time: 3 Hours                     Max Marks: 75",
        "",
        "SECTION A",
        "Answer all questions. Each question carries 5 marks.",
        "",
        "Q1. Explain the concept of normalization in DBMS. [5 marks]",
        "",
        "Q2. What is a primary key? Explain with an example. [5 marks]",
        "",
        "SECTION B",
        "Answer any THREE questions. Each question carries 10 marks.",
        "",
        "Q3. Describe ACID properties with examples. [10 marks]",
        "",
        "Q4. Explain the ER model and its components. [10 marks]",
        "",
        "Q5. What is SQL? Write queries for the following:",
        "(a) Create a table named Students.",
        "(b) Insert a record into Students.",
        "(c) Select all records from Students.",
        "[10 marks]",
    ]
    y = 50
    for line in lines:
        page.insert_text((40, y), line, fontsize=11)
        y += 18
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()
    doc.save(tmp_path)
    doc.close()
    return tmp_path

# ── Run the pipeline ───────────────────────────────────────────────
pdf_path = make_exam_pdf()
try:
    print(f"\nParsing: {pdf_path}\n{'='*55}")
    result = parse_question_paper(pdf_path, document_id=101)

    print(f"\ndocument_id : {result.document_id}")
    print(f"year        : {result.year}")
    print(f"exam_type   : {result.exam_type}")
    print(f"total_pages : {result.total_pages}")
    print(f"questions   : {len(result.questions)}")
    print(f"\n{'─'*55}")

    for q in result.questions:
        print(f"  [{q.question_label if hasattr(q, 'question_label') else '?'}] "
              f"page={q.page} section={q.section} marks={q.marks} "
              f"compulsory={q.is_compulsory}")
        print(f"    {q.raw_text[:70].replace(chr(10),' ')}...")
        print(f"    topic_id={q.topic_id}  repeat_group_id={q.repeat_group_id}  "
              f"cleaned_text={q.cleaned_text}")
        print()

    # Verify contract
    print("Contract checks:")
    for q in result.questions:
        assert q.topic_id        is None, "FAIL: topic_id should be None"
        assert q.repeat_group_id is None, "FAIL: repeat_group_id should be None"
        assert q.cleaned_text    is None, "FAIL: cleaned_text should be None"
        assert isinstance(q.raw_text, str) and q.raw_text.strip()
    print("  All questions have topic_id=None        [OK]")
    print("  All questions have repeat_group_id=None [OK]")
    print("  All questions have cleaned_text=None    [OK]")
    print("  All questions have non-empty raw_text   [OK]")
    print(f"\nSmoke test PASSED")

finally:
    os.unlink(pdf_path)
