import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import ingestion, documents, exports, analytics, processing

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ExamLens Platform API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router)
app.include_router(documents.router)
app.include_router(exports.router)
app.include_router(analytics.router)
app.include_router(processing.router)