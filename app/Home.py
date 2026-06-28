"""
अर्थAI — Home / Dashboard with proper session resume
"""

import streamlit as st
import json, sys, sqlite3, warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")
BASE_DIR   = Path(__file__).resolve().parent.parent
LLM_DIR    = BASE_DIR / "data" / "output" / "llm"
RAG_DIR    = BASE_DIR / "data" / "output" / "rag"
REPORT_DIR = BASE_DIR / "data" / "output" / "reports"
DB_PATH    = BASE_DIR / "data" / "arth_ai_sessions.db"
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(
    page_title="अर्थAI — Financial Audit",
    page_icon="📊", layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/accounting.png", width=64)
    st.title("अर्थAI")
    st.caption("AI-Augmented Financial Auditing")
    st.divider()
    st.markdown("""
**Pipeline:**
1. 📥 Upload & Ingest
2. 🔍 Anomaly Detection
3. ✏️ Verify Financials
4. 📄 Report Generation
5. 📚 Rulebook
    """)
    st.divider()
    if st.session_state.get("thread_id"):
        st.success(f"🟢 Active:\n`{st.session_state['thread_id']}`")
        if st.button("🗑️ Clear session"):
            st.session_state.pop("thread_id", None)
            st.session_state.pop("source_file", None)
            st.rerun()
    st.caption("Thapar Institute · CPG327")

st.title("📊 अर्थAI — Financial Audit Platform")
st.markdown(
    "**End-to-End AI-Augmented Architecture for Financial Auditing**  \n"
    "Thapar Institute of Engineering and Technology · Capstone CPG327"
)
st.divider()

# ── Metrics ────────────────────────────────────────────────────────────────────
llm_files    = list(LLM_DIR.glob("*.json"))     if LLM_DIR.exists()    else []
report_files = list(REPORT_DIR.glob("*.json"))  if REPORT_DIR.exists() else []
rag_files    = list(RAG_DIR.glob("*.json"))     if RAG_DIR.exists()    else []

total_critical = sum(
    json.load(open(f)).get("anomaly_summary", {}).get("critical", 0)
    for f in rag_files if f.exists()
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Documents Processed", len(llm_files))
c2.metric("Reports Generated",   len(report_files))
c3.metric("Critical Flags",      total_critical)
c4.metric("Active Agents",       "4")
st.divider()

# ── Session resume — reads actual thread IDs from SQLite ──────────────────────
st.subheader("📂 Audit Sessions")

def _load_sessions_from_db() -> list:
    """
    Read thread IDs from SQLite, match them to LLM output files,
    return a list of session dicts with all the info needed to resume.
    """
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        # Get most recent checkpoint per thread
        rows = conn.execute("""
            SELECT thread_id, MAX(checkpoint_id) as latest
            FROM checkpoints
            GROUP BY thread_id
        """).fetchall()
        conn.close()
    except Exception:
        return []

    sessions = []
    for (thread_id, _) in rows:
        # Match to LLM output file — thread_id starts with the file stem
        matched_file = None
        for f in llm_files:
            if thread_id.startswith(f.stem) or f.stem.startswith(thread_id):
                matched_file = f
                break
            # Exact match (new deterministic style)
            if thread_id == f.stem:
                matched_file = f
                break

        company   = thread_id  # fallback
        fy        = "—"
        conf      = "—"

        if matched_file and matched_file.exists():
            try:
                data    = json.load(open(matched_file))
                company = data.get("company_name", thread_id)
                fy      = data.get("financial_year_end", "—")
                conf    = f"{data.get('extraction_confidence', 0):.0%}"
            except Exception:
                pass

        # Determine progress from output folders
        stem = matched_file.stem if matched_file else thread_id
        has_report = (REPORT_DIR / f"{stem}.json").exists() if REPORT_DIR else False
        has_rag    = (RAG_DIR    / f"{stem}.json").exists() if RAG_DIR    else False
        step = ("✅ Report generated" if has_report
                else "📚 RAG complete"   if has_rag
                else "🤖 Extraction done")

        sessions.append({
            "thread_id": thread_id,
            "company":   company,
            "fy":        fy,
            "conf":      conf,
            "step":      step,
        })

    # Most recent first
    return sessions


sessions = _load_sessions_from_db()

if not sessions and not llm_files:
    st.info("👋 No sessions yet. Go to **📥 Upload & Ingest** to start your first audit.")
elif not sessions:
    st.info("No saved LangGraph sessions found. Start a new audit in **📥 Upload & Ingest**.")
else:
    st.caption(
        "Sessions are saved to SQLite and survive restarts. "
        "Click **Resume** to continue from where you left off."
    )
    for s in sessions:
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            is_active = st.session_state.get("thread_id") == s["thread_id"]
            active_tag = "  🟢 **ACTIVE**" if is_active else ""
            st.markdown(
                f"**{s['company']}**{active_tag}  \n"
                f"FY: `{s['fy']}` · Confidence: `{s['conf']}` · {s['step']}  \n"
                f"Session ID: `{s['thread_id']}`"
            )
        with col_btn:
            label = "🟢 Active" if st.session_state.get("thread_id") == s["thread_id"] \
                    else "▶ Resume"
            if st.button(label, key=f"resume_{s['thread_id']}",
                         use_container_width=True,
                         disabled=(st.session_state.get("thread_id") == s["thread_id"])):
                st.session_state["thread_id"]   = s["thread_id"]
                # Try to set source_file from the matched stem
                st.session_state["source_file"] = s["thread_id"].split("-")[0] + ".pdf"
                st.rerun()
        st.divider()

# ── Current active session status ─────────────────────────────────────────────
if st.session_state.get("thread_id"):
    tid = st.session_state["thread_id"]
    try:
        from agents.orchestrator import get_graph
        g        = get_graph()
        snapshot = g.get_state({"configurable": {"thread_id": tid}})
        state    = snapshot.values
        step     = state.get("current_step", "unknown")
        nxt      = list(snapshot.next)

        st.success(
            f"🟢 **Active session:** `{tid}`  \n"
            f"Current step: `{step}`  |  "
            f"{'Waiting for: ' + str(nxt) if nxt else 'Pipeline complete'}"
        )
    except Exception as e:
        st.warning(f"Session `{tid}` loaded but state unreadable: {e}")

st.divider()
st.markdown(
    "Model: `jinaai/jina-embeddings-v2-base-en` · "
    "LLM: `llama-3.3-70b-versatile` via Groq · "
    "OCR: Tesseract 5  \n"
    "Sessions: SQLite (`data/arth_ai_sessions.db`)"
)
