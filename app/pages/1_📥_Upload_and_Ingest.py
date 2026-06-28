"""
अर्थAI — Page 1: Upload & Ingest
Extracts text from PDF, runs Module 1+2, then kicks off the
orchestrator which runs math_validator + compliance_checker
and pauses waiting for auditor flag review.
"""

import streamlit as st
import json, sys
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

INPUT_DIR = BASE_DIR / "data" / "input"
OUT_LLM   = BASE_DIR / "data" / "output" / "llm"

st.set_page_config(page_title="Upload & Ingest · अर्थAI", page_icon="📥", layout="wide")

with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 1 — Upload & Ingest")
    st.divider()
    st.markdown("""
**What runs here:**
- PDF text extraction (OCR if scanned)
- LLM fills in financial fields (Module 2)
- Orchestrator starts:
  - Agent 1 validates all arithmetic
  - Agent 2 checks compliance rules
- Graph pauses for your flag review
    """)
    st.divider()
    if st.session_state.get("thread_id"):
        st.success(f"Active session:\n`{st.session_state['thread_id']}`")
        if st.button("🗑️ Clear session"):
            for k in ["thread_id", "source_file"]:
                st.session_state.pop(k, None)
            st.rerun()
    from app.rag_chat import render_rag_chat
    render_rag_chat()

st.title("📥 Step 1 — Upload & Ingest")
st.caption("Upload a company financial statement PDF to begin the audit pipeline.")
st.divider()

uploaded = st.file_uploader(
    "Upload Financial Statement PDF",
    type=["pdf"],
    help="Supports text-based and scanned (OCR) PDFs.",
)

if not uploaded:
    st.stop()

# ── Save PDF ───────────────────────────────────────────────────────────────────
INPUT_DIR.mkdir(parents=True, exist_ok=True)
dest = INPUT_DIR / uploaded.name
dest.write_bytes(uploaded.getbuffer())
st.success(f"✅ Uploaded: **{uploaded.name}** ({uploaded.size/1024:.1f} KB)")

llm_path   = OUT_LLM / (dest.stem + ".json")
rerun_flag = st.checkbox("Re-run extraction (overwrite existing)", value=not llm_path.exists())

if not st.button("▶ Extract & Start Audit Pipeline", type="primary", use_container_width=True):
    if llm_path.exists() and not rerun_flag:
        st.info("ℹ️ Extraction already done. Uncheck 'Re-run' and click the button to use cached data.")
    st.stop()

# ── Extraction ─────────────────────────────────────────────────────────────────
with st.status("Running extraction pipeline...", expanded=True) as status:
    import warnings; warnings.filterwarnings("ignore")

    # Deterministic thread_id — same file always gets same session
    # This means sessions survive Streamlit restarts
    st.write("**Module 1:** Extracting text from PDF...")
    from module1.extractor import get_full_text
    from module1.parser import parse_financial_text
    raw_text, method = get_full_text(str(dest))
    st.write(f"  ✅ {len(raw_text):,} chars extracted via **{method}**")

    fs_m1 = parse_financial_text(raw_text, source_file=uploaded.name, extraction_method=method)
    m1_dict = fs_m1.to_dict()
    from module1.parser import attach_sources
    m1_dict = attach_sources(m1_dict)
    (BASE_DIR / "data" / "output").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "output" / (dest.stem + ".json")).write_text(
        json.dumps(m1_dict, indent=2, default=str))

    st.write("**Module 2:** LLM completing financial fields (Groq)...")
    from module2.reasoning import complete_financial_json_with_sources as complete_financial_json
    completed = complete_financial_json(m1_dict, raw_text, source_file=uploaded.name)
    OUT_LLM.mkdir(parents=True, exist_ok=True)
    llm_path.write_text(json.dumps(completed, indent=2, default=str))
    st.write(f"  ✅ LLM confidence: **{completed.get('extraction_confidence', 0):.0%}**")

    st.write("**Orchestrator:** Running Math Validator + Compliance Checker...")
    from agents.orchestrator import get_graph, create_initial_state

    graph     = get_graph()
    thread_id = dest.stem  # deterministic — same file = same session
    config    = {"configurable": {"thread_id": thread_id}}
    init_state = create_initial_state(completed, raw_text)

    result = graph.invoke(init_state, config)

    st.session_state["thread_id"]   = thread_id
    st.session_state["source_file"] = uploaded.name
    st.write(f"  ✅ Graph paused at: **{list(graph.get_state(config).next)}**")
    status.update(label="✅ Ready for your review!", state="complete")

# ── Show extraction summary ────────────────────────────────────────────────────
st.divider()
st.subheader("📊 Extraction Summary")

col_l, col_r = st.columns(2)
with col_l:
    st.markdown("**Company Information**")
    st.write(f"**Name:** {completed.get('company_name', '—')}")
    st.write(f"**CIN:** {completed.get('cin', '—')}")
    st.write(f"**FY End:** {completed.get('financial_year_end', '—')}")
    st.write(f"**Auditor:** {completed.get('auditor_name', '—')}")
    conf = completed.get("extraction_confidence", 0)
    st.progress(conf, text=f"Extraction confidence: {conf:.0%}")

with col_r:
    st.markdown("**Key Financials (₹)**")
    pl = completed.get("profit_and_loss", {})
    ca = completed.get("balance_sheet", {}).get("current_assets", {})
    st.write(f"**Revenue:** {pl.get('revenue_from_operations', '—')}")
    st.write(f"**PAT:** {pl.get('profit_after_tax', '—')}")
    st.write(f"**Cash:** {ca.get('cash_and_cash_equivalents', '—')}")

# Math report quick view
math = result.get("math_report", {})
if math:
    st.divider()
    st.subheader("🔢 Math Validation (Agent 1 — Pure Python)")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Total Checks", math.get("total_checks", 0))
    mc2.metric("Passed", math.get("passed", 0))
    failed = math.get("failed", 0)
    mc3.metric("Failed", failed, delta=f"-{failed}" if failed else None,
               delta_color="inverse")

    if math.get("has_critical_errors"):
        st.error("⚠️ Critical arithmetic errors detected — see Anomaly Detection page.")
    else:
        st.success("✅ All math checks passed.")

    with st.expander("View all math checks"):
        for c in math.get("checks", []):
            icon = "✅" if c.get("passed") else ("🔴" if c.get("critical") else "🟡")
            st.write(f"{icon} **{c['check']}**")
            if not c.get("passed") and c.get("difference") is not None:
                st.caption(f"  Expected: {c.get('expected')}  |  Got: {c.get('actual')}  |  Diff: {c.get('difference')}")

# ── Source audit trail ─────────────────────────────────────────────────────────
sources = completed.get("_sources", {})
if sources:
    st.divider()
    st.subheader("📋 Field Source Audit Trail")
    regex_fields = {k: v for k, v in sources.items() if v == "regex"}
    llm_fields   = {k: v for k, v in sources.items() if v == "llm"}

    sc1, sc2 = st.columns(2)
    sc1.metric("✅ Regex-extracted (trusted)", len(regex_fields))
    sc2.metric("⚠️ LLM-extracted (verify)", len(llm_fields))

    if regex_fields:
        with st.expander(f"✅ {len(regex_fields)} fields extracted by regex — deterministic, no LLM", expanded=True):
            rows = []
            for path in sorted(regex_fields):
                val = completed
                for key in path.split("."):
                    val = val.get(key, "—") if isinstance(val, dict) else "—"
                rows.append({"Field": path, "Value": str(val), "Source": "✅ regex"})
            st.table(rows)

    if llm_fields:
        with st.expander(f"⚠️ {len(llm_fields)} fields filled by LLM — cross-check against source PDF"):
            rows = []
            for path in sorted(llm_fields):
                val = completed
                for key in path.split("."):
                    val = val.get(key, "—") if isinstance(val, dict) else "—"
                rows.append({"Field": path, "Value": str(val), "Source": "⚠️ LLM"})
            st.table(rows)

with st.expander("📋 Full extracted JSON"):
    st.json(completed)

st.divider()
st.success(f"✅ Pipeline running! Session ID: `{thread_id}`  \nProceed to **🔍 Anomaly Detection** in the sidebar.")
