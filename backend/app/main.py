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

# ── Register Routers ──────────────────────────────────────────────────────────
# Each member uncomments their two lines below.
# Git treats each line independently → no merge conflicts.

# Member 3 — Exam parser & syllabus (this branch)
app.include_router(exam_router)

# Member 4 — NLP / topic classification
# from app.api.nlp_routes import router as nlp_router
# app.include_router(nlp_router)

# Member 5 — Analytics
# from app.routers.analytics import router as analytics_router
# app.include_router(analytics_router)

# Member 6 — Frontend ingestion / auth
# from app.routers.ingestion import router as ingestion_router
# app.include_router(ingestion_router)


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
