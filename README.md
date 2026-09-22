# ExamLens

**ExamLens** turns lecture-board photos and past question papers into a connected study system.

## Members

| Member | Role |
|--------|------|
| Member 1 | Vision (board photo capture) |
| Member 2 | OCR + Math extraction |
| Member 3 | **Exam Parsing Lead** ← this module |
| Member 4 | NLP + Topic Classification |
| Member 5 | Analytics + Study Planning |
| Member 6 | Platform, DB, FastAPI, Frontend |

---

## Member 3 — Exam Parser Module

This module is responsible for turning raw PDF question papers into structured `Question` records stored in the shared database.

### Pipeline

```
Question Paper PDF
      ↓
PDF Text Extraction (pdfplumber)
      ↓
OCR Fallback if no text layer (PyMuPDF + Tesseract)
      ↓
Basic Text Normalization
      ↓
Question Segmentation (regex-based)
      ↓
Metadata Extraction (year, marks, section, exam_type)
      ↓
Structured Question records
      ↓
SQLite (dev) → Member 6's shared DB (production)
```

### Output Contract

Each `Question` record produced by this module contains:

| Field | Produced by |
|-------|-------------|
| `question_id` | Member 3 (generated) |
| `document_id` | Member 6 (provided as input) |
| `page` | Member 3 |
| `raw_text` | Member 3 |
| `cleaned_text` | **NULL** — filled by Member 4 |
| `year` | Member 3 |
| `exam_type` | Member 3 |
| `section` | Member 3 |
| `marks` | Member 3 |
| `is_compulsory` | Member 3 |
| `topic_id` | **NULL** — filled by Member 4 |
| `repeat_group_id` | **NULL** — filled by Member 4 |

---

## Setup (Windows)

```bash
# 1. Clone the repo
git clone <repo-url>
cd exam-lens

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Copy env template
copy backend\.env.example backend\.env
# Then edit .env with your Tesseract path

# 5. Verify setup
python backend/app/check_env.py
```

---

## Running the API (dev)

```bash
cd backend
uvicorn app.main:app --reload
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```
