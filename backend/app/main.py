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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exam_routes import router as exam_router
from app.database.db import get_all_topics, init_db
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

# Register Routers
app.include_router(exam_router)


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
    return {
        "status": "healthy",
        "database": "connected",
    }
