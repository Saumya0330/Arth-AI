"""
अर्थAI — Report API

GET  /api/report/{id}           — get current report draft
GET  /api/report/{id}/download  — download final markdown file
"""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/{session_id}")
def get_report(session_id: str):
    """Get the current report draft sections + markdown."""
    from backend.core.pipeline_runner import get_state
    state = get_state(session_id)
    if not state.get("financial_json"):
        raise HTTPException(404, f"Session '{session_id}' not found.")
    if not state.get("report_sections"):
        raise HTTPException(400, "Report not generated yet. Complete flag review first.")
    return {
        "report_sections": state["report_sections"],
        "report_markdown": state.get("report_markdown", ""),
        "report_finalised": state.get("report_finalised", False),
    }


@router.get("/{session_id}/download")
def download_report(session_id: str):
    """Download the finalised audit report as a markdown file."""
    report_path = BASE_DIR / "data" / "output" / "reports" / f"{session_id}_final.md"
    if not report_path.exists():
        raise HTTPException(404, "Finalised report not found. Complete Step 4 first.")
    return FileResponse(
        path=str(report_path),
        media_type="text/markdown",
        filename=f"{session_id}_audit_report.md",
    )
