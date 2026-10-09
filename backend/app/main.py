"""
main.py
=======
FastAPI application entry point for ExamLens backend.

Features:
  - Automatic DB initialization on startup
  - Automatic syllabus seeding if empty
  - CORS middleware for frontend integration
  - Health check & API metadata routes
  - Exam parser and syllabus management routes
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.env_loader import load_backend_env

load_backend_env()

from app.api.exam_routes import router as exam_router
from app.database import Base, dispose_engines, get_engine
from app.database.db import get_all_topics, get_connection, init_db
import app.models  # noqa: F401  — register SQLAlchemy tables on Base
from app.routers.analytics import router as analytics_router
from app.routers.documents import router as documents_router
from app.routers.exports import router as exports_router
from app.routers.ingestion import router as ingestion_router
from app.routers.ocr import router as ocr_router
from app.routers.processing import router as processing_router
from app.syllabus.loader import load_syllabus_to_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup & shutdown events for the application.
    Initializes DB tables and seeds sample syllabus if topics table is empty.
    """
    # ── Startup ───────────────────────────────────────────────────────────
    print("[ExamLens] Initializing database...")
    init_db()
    Base.metadata.create_all(bind=get_engine())

    # Seed syllabus if empty
    existing_topics = get_all_topics()
    if not existing_topics:
        sample_csv = Path(__file__).parent / "syllabus" / "sample_syllabus.csv"
        if sample_csv.exists():
            print(f"[ExamLens] Seeding initial syllabus from {sample_csv.name}...")
            count = load_syllabus_to_db(sample_csv)
            print(f"[ExamLens] Seeded {count} syllabus topics.")

    print("[ExamLens] Ready to serve requests.")
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────
    print("[ExamLens] Shutting down.")
    dispose_engines()


app = FastAPI(
    title="ExamLens API",
    description="Automated Question Paper Parser and Analysis Pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Member 6 frontend support
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ──────────────────────────────────────────────────────────
# Member 1 Vision is not a router; processing.py calls process_board_images().

# Member 2 — OCR review UI
app.include_router(ocr_router)

# Member 3 — Exam parser & syllabus
app.include_router(exam_router)

# Member 4 — topic/repeat assignment exists as batch scripts
# (app/services/topic_service.py, repeat_service.py) using sentence-transformers.
# There is no documented HTTP contract for app/api/nlp_routes.py, so no
# NLP router is registered. Optional deps: backend/requirements-nlp.txt.

# Member 5 — Analytics
app.include_router(analytics_router)

# Member 6 — ingestion, documents/contract, processing hub, exports
app.include_router(ingestion_router)
app.include_router(documents_router)
app.include_router(processing_router)
app.include_router(exports_router)


@app.get("/", tags=["Health & Info"])
async def root():
    return {
        "app": "ExamLens API",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }


@app.get("/health", tags=["Health & Info"])
async def health_check():
    conn = None
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"database unavailable: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()
    return {
        "status": "healthy",
        "database": "connected",
    }
