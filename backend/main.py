"""
अर्थAI — FastAPI Backend

Run from the PROJECT ROOT (~/Desktop/Capstone):
    ./start_backend.sh
    OR
    PYTHONPATH=. uvicorn backend.main:app --reload --port 8000

Docs: http://localhost:8000/docs
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is on path regardless of where uvicorn is invoked from
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.sessions      import router as sessions_router
from backend.api.pipeline      import router as pipeline_router
from backend.api.financials    import router as financials_router
from backend.api.report        import router as report_router
from backend.api.chat_rulebook import router as chat_rulebook_router

app = FastAPI(
    title="अर्थAI",
    description="End-to-End AI-Augmented Architecture for Financial Auditing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow React dev server and production domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # CRA fallback
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(sessions_router)
app.include_router(pipeline_router)
app.include_router(financials_router)
app.include_router(report_router)
app.include_router(chat_rulebook_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "अर्थAI Backend"}


# Serve React build in production
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
