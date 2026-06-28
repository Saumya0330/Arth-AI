"""
अर्थAI — Streamlit App: Home / Pipeline Dashboard
"""

import streamlit as st
import json
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "data" / "output" / "reports"
RAG_DIR    = BASE_DIR / "data" / "output" / "rag"
LLM_DIR    = BASE_DIR / "data" / "output" / "llm"

st.set_page_config(
    page_title="अर्थAI — Financial Audit",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/accounting.png", width=64)
    st.title("अर्थAI")
    st.caption("AI-Augmented Financial Auditing")
    st.divider()
    st.markdown("""
**Pipeline Steps**
1. 📥 Upload & Ingest
2. 🤖 LLM Extraction
3. 🔍 Anomaly Detection
4. 📚 Regulatory RAG
5. 📄 Report Generation
    """)
    st.divider()
    st.caption("Thapar Institute · CPG327")

# ── Main ───────────────────────────────────────────────────────────────────────
st.title("📊 अर्थAI — Financial Audit Platform")
st.markdown(
    "**End-to-End AI-Augmented Architecture for Financial Auditing and Report Generation**  \n"
    "Thapar Institute of Engineering and Technology · Capstone Project CPG327"
)
st.divider()

# Pipeline status cards
reports = list(REPORT_DIR.glob("*.json")) if REPORT_DIR.exists() else []
rag     = list(RAG_DIR.glob("*.json"))    if RAG_DIR.exists() else []
llm     = list(LLM_DIR.glob("*.json"))    if LLM_DIR.exists() else []

col1, col2, col3, col4 = st.columns(4)
col1.metric("Documents Processed", len(llm))
col2.metric("Anomalies Detected",
    sum(json.load(open(f)).get("anomaly_summary", {}).get("total", 0)
        for f in rag if f.exists()) if rag else 0
)
col3.metric("Reports Generated", len(reports))
col4.metric("Critical Flags",
    sum(json.load(open(f)).get("anomaly_summary", {}).get("critical", 0)
        for f in rag if f.exists()) if rag else 0
)

st.divider()

# Quick start guide
if not llm:
    st.info(
        "👋 **Welcome!** No documents processed yet.  \n"
        "Go to **📥 Upload & Ingest** in the sidebar to upload your first financial PDF."
    )
else:
    st.subheader("Recent Documents")
    for f in sorted(rag, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        data = json.load(open(f))
        summary = data.get("anomaly_summary", {})
        col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])
        col_a.write(f"**{data.get('company_name', f.stem)}**")
        col_b.write(data.get("financial_year_end", "—"))
        col_c.write(
            f"🔴 {summary.get('critical',0)}  "
            f"🟡 {summary.get('warning',0)}"
        )
        col_d.write(data.get("extraction_method", "—"))

st.divider()
st.markdown(
    "**अर्थAI** uses `jinaai/jina-embeddings-v2-base-en` for regulatory retrieval · "
    "`llama-3.3-70b-versatile` via Groq for reasoning · "
    "Tesseract OCR for scanned documents"
)
