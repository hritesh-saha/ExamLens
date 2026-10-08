# ExamLens



---

##  Exam Parser Module

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
