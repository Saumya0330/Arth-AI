"""
अर्थAI — Sessions API

POST /api/sessions/upload   — upload one or more PDFs/CSVs, run extraction, start pipeline
GET  /api/sessions          — list all sessions (from SQLite)
GET  /api/sessions/{id}     — get full state for a session
"""

import sys, json, shutil, sqlite3
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException

BASE_DIR  = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = BASE_DIR / "data" / "input"
OUT_LLM   = BASE_DIR / "data" / "output" / "llm"
DB_PATH   = BASE_DIR / "data" / "arth_ai_sessions.db"
sys.path.insert(0, str(BASE_DIR))

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}


def _safe_state(state: dict) -> dict:
    """Strip raw_text (large) before returning state over API."""
    s = dict(state)
    s.pop("raw_text", None)
    return s


@router.post("/upload")
async def upload_and_start(files: List[UploadFile] = File(...)):
    """
    Upload one or more financial documents (PDF, CSV, Excel).
    All files are extracted and merged into one FinancialStatement JSON.
    The merged JSON is then passed through Module 2 (LLM) and the agent pipeline.
    Session ID is derived from the first PDF filename.
    """
    if not files:
        raise HTTPException(400, "At least one file is required.")

    # Validate extensions
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {f.filename}. "
                                     f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "output").mkdir(parents=True, exist_ok=True)

    from module1.extractor import get_full_text
    from module1.parser import parse_financial_text, attach_sources
    from module1.csv_extractor import extract_from_csv
    from module1.merger import merge_financial_dicts
    from module2.reasoning import complete_financial_json_with_sources
    from backend.core.pipeline_runner import start_pipeline

    partial_dicts = []
    all_raw_text  = []
    primary_stem  = None   # used as thread_id
    primary_method = "text"

    for upload in files:
        dest = INPUT_DIR / upload.filename
        with open(dest, "wb") as fh:
            shutil.copyfileobj(upload.file, fh)

        ext = dest.suffix.lower()

        if ext == ".pdf":
            raw_text, method = get_full_text(str(dest))
            all_raw_text.append(raw_text)
            fs = parse_financial_text(raw_text, source_file=upload.filename,
                                      extraction_method=method)
            d = attach_sources(fs.to_dict())
            d["_source_file"] = upload.filename
            partial_dicts.append(d)

            # First PDF sets the session identity
            if primary_stem is None:
                primary_stem   = dest.stem
                primary_method = method

        else:  # CSV / Excel
            partial, csv_sources = extract_from_csv(str(dest))
            partial["_sources"]     = csv_sources
            partial["_source_file"] = upload.filename
            partial_dicts.append(partial)

    if primary_stem is None:
        # No PDF uploaded — use first file stem
        primary_stem = Path(files[0].filename).stem

    # Merge all partial dicts
    if len(partial_dicts) == 1:
        merged = partial_dicts[0]
    else:
        merged = merge_financial_dicts(partial_dicts)

    merged["source_file"]        = ", ".join(f.filename for f in files)
    merged["extraction_method"]  = primary_method

    # Save Module 1 output
    (BASE_DIR / "data" / "output" / f"{primary_stem}.json").write_text(
        json.dumps(merged, indent=2, default=str))

    # Module 2 — LLM fill on merged data
    combined_text = "\n\n".join(all_raw_text)
    completed = complete_financial_json_with_sources(
        merged, combined_text, source_file=merged["source_file"])
    OUT_LLM.mkdir(parents=True, exist_ok=True)
    (OUT_LLM / f"{primary_stem}.json").write_text(
        json.dumps(completed, indent=2, default=str))

    # Start pipeline
    result = start_pipeline(completed, combined_text, primary_stem)

    return {
        "session_id":             primary_stem,
        "source_files":           [f.filename for f in files],
        "company_name":           completed.get("company_name"),
        "financial_year":         completed.get("financial_year_end"),
        "extraction_confidence":  completed.get("extraction_confidence"),
        "extraction_method":      primary_method,
        "current_step":           result.get("current_step"),
        "next_nodes":             result.get("_next_nodes", []),
        "math_report":            result.get("math_report"),
        "anomaly_flags":          result.get("anomaly_flags", []),
        "field_sources":          result.get("field_sources", {}),
    }



@router.get("")
def list_sessions():
    """List all sessions from SQLite with their pipeline progress."""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    rows = conn.execute(
        "SELECT thread_id, MAX(checkpoint_id) FROM checkpoints GROUP BY thread_id"
    ).fetchall()
    conn.close()

    sessions = []
    for (thread_id, _) in rows:
        llm_file = OUT_LLM / f"{thread_id}.json"
        company, fy, conf = thread_id, "—", 0.0
        if llm_file.exists():
            try:
                d = json.load(open(llm_file))
                company = d.get("company_name", thread_id)
                fy      = d.get("financial_year_end", "—")
                conf    = d.get("extraction_confidence", 0.0)
            except Exception:
                pass

        rag_path    = BASE_DIR / "data" / "output" / "rag"    / f"{thread_id}.json"
        report_path = BASE_DIR / "data" / "output" / "reports"/ f"{thread_id}.json"
        step = ("report_generated" if report_path.exists()
                else "rag_complete"   if rag_path.exists()
                else "extraction_done")

        sessions.append({
            "session_id":   thread_id,
            "company_name": company,
            "financial_year": fy,
            "extraction_confidence": conf,
            "pipeline_step": step,
        })

    return sessions


@router.get("/{session_id}")
def get_session(session_id: str):
    """Get current pipeline state for a session."""
    from backend.core.pipeline_runner import get_state
    try:
        state = get_state(session_id)
        if not state.get("financial_json"):
            raise HTTPException(404, f"Session '{session_id}' not found.")
        return _safe_state(state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
