"""
अर्थAI — Home / Dashboard
"""

import streamlit as st
import json, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
BASE_DIR   = Path(__file__).resolve().parent.parent
LLM_DIR    = BASE_DIR / "data" / "output" / "llm"
RAG_DIR    = BASE_DIR / "data" / "output" / "rag"
REPORT_DIR = BASE_DIR / "data" / "output" / "reports"
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(
    page_title="अर्थAI — Financial Audit",
    page_icon="📊",
    layout="wide",
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
    st.caption("Thapar Institute · CPG327")

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📊 अर्थAI — Financial Audit Platform")
st.markdown(
    "**End-to-End AI-Augmented Architecture for Financial Auditing**  \n"
    "Thapar Institute of Engineering and Technology · Capstone CPG327"
)
st.divider()

# ── Metrics ────────────────────────────────────────────────────────────────────
llm_files    = list(LLM_DIR.glob("*.json"))     if LLM_DIR.exists()    else []
rag_files    = list(RAG_DIR.glob("*.json"))     if RAG_DIR.exists()    else []
report_files = list(REPORT_DIR.glob("*.json"))  if REPORT_DIR.exists() else []

total_critical = 0
for f in rag_files:
    try:
        total_critical += json.load(open(f)).get("anomaly_summary", {}).get("critical", 0)
    except Exception:
        pass

c1, c2, c3, c4 = st.columns(4)
c1.metric("Documents Processed", len(llm_files))
c2.metric("Reports Generated",   len(report_files))
c3.metric("Critical Flags",      total_critical)
c4.metric("Pipeline",            "5 Agents")

st.divider()

# ── Session resume ─────────────────────────────────────────────────────────────
st.subheader("📂 Resume an Audit Session")
st.caption(
    "Sessions are saved to SQLite and survive restarts. "
    "Select a previous session to continue where you left off."
)

if not llm_files:
    st.info("👋 No sessions yet. Go to **📥 Upload & Ingest** to start.")
else:
    # Build session list from LLM output files
    sessions = []
    for f in sorted(llm_files, key=lambda x: x.stat().st_mtime, reverse=True):
        thread_id = f.stem   # deterministic — same as what Page 1 sets
        try:
            data = json.load(open(f))
        except Exception:
            continue

        # Figure out pipeline progress
        has_rag    = (RAG_DIR / f.name).exists()    if RAG_DIR    else False
        has_report = (REPORT_DIR / f.name).exists() if REPORT_DIR else False
        step = ("✅ Report generated" if has_report
                else "📚 RAG complete" if has_rag
                else "🤖 Extraction done")

        sessions.append({
            "thread_id":  thread_id,
            "company":    data.get("company_name", f.stem),
            "fy":         data.get("financial_year_end", "—"),
            "confidence": f"{data.get('extraction_confidence', 0):.0%}",
            "step":       step,
            "file":       f,
        })

    # Display as cards
    for s in sessions:
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"**{s['company']}**  \n"
                f"FY: `{s['fy']}` · Confidence: `{s['confidence']}` · {s['step']}"
            )
        with col_btn:
            if st.button("▶ Resume", key=f"resume_{s['thread_id']}",
                         use_container_width=True):
                st.session_state["thread_id"]   = s["thread_id"]
                st.session_state["source_file"] = s["thread_id"] + ".pdf"
                st.success(
                    f"✅ Session restored: `{s['thread_id']}`  \n"
                    f"Navigate to any step in the sidebar to continue."
                )
                st.rerun()

        st.divider()

# ── Active session indicator ───────────────────────────────────────────────────
if st.session_state.get("thread_id"):
    tid = st.session_state["thread_id"]
    st.success(f"🟢 **Active session:** `{tid}`  \nUse the sidebar to navigate pipeline steps.")
    if st.button("🗑️ Clear active session"):
        st.session_state.pop("thread_id", None)
        st.session_state.pop("source_file", None)
        st.rerun()

st.divider()
st.markdown(
    "Model: `jinaai/jina-embeddings-v2-base-en` · "
    "LLM: `llama-3.3-70b-versatile` via Groq · "
    "OCR: Tesseract 5"
)
