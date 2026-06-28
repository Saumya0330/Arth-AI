"""
अर्थAI — Page 1: Upload & Ingest
Runs Module 1 (extraction) + Module 2 (LLM completion) with auditor confirmation.
"""

import streamlit as st
import json
import shutil
from pathlib import Path
import sys

BASE_DIR  = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = BASE_DIR / "data" / "input"
OUT_DIR   = BASE_DIR / "data" / "output"
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(page_title="Upload & Ingest · अर्थAI", page_icon="📥", layout="wide")

with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 1 of 5")
    st.divider()
    st.markdown("""
**What happens here:**
- Upload company financial PDF
- Module 1 extracts text (OCR if scanned)
- Module 2 uses LLM to fill in all financial fields
- You review and confirm before proceeding
    """)

st.title("📥 Step 1 — Upload & Ingest")
st.caption("Upload a company's financial statement PDF to begin the audit pipeline.")
st.divider()

# ── Upload ─────────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload Financial Statement PDF",
    type=["pdf"],
    help="Supports both text-based and scanned PDFs. Scanned PDFs use OCR automatically."
)

if uploaded:
    # Save to data/input/
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = INPUT_DIR / uploaded.name
    with open(dest, "wb") as f:
        f.write(uploaded.getbuffer())
    st.success(f"✅ Uploaded: **{uploaded.name}** ({uploaded.size/1024:.1f} KB)")

    st.divider()

    # Check if already processed
    llm_out = OUT_DIR / "llm" / (dest.stem + ".json")
    already_done = llm_out.exists()

    if already_done:
        st.info("ℹ️ This file has already been processed. You can re-run or continue.")

    col1, col2 = st.columns(2)
    run_m1 = col1.button("▶ Run Module 1 (Extract)", use_container_width=True,
                         disabled=already_done and not col2.button("🔄 Re-run", use_container_width=True))

    if run_m1 or (already_done and st.session_state.get("rerun")):
        with st.status("Running extraction pipeline...", expanded=True) as status:

            st.write("**Module 1:** Extracting text from PDF...")
            from module1.extractor import get_full_text
            from module1.parser import parse_financial_text
            import time

            raw_text, method = get_full_text(str(dest))
            st.write(f"  ✅ Extracted {len(raw_text):,} characters via **{method}**")

            fs = parse_financial_text(raw_text, source_file=uploaded.name, extraction_method=method)
            m1_dict = fs.to_dict()

            m1_path = OUT_DIR / (dest.stem + ".json")
            m1_path.parent.mkdir(parents=True, exist_ok=True)
            with open(m1_path, "w") as f:
                json.dump(m1_dict, f, indent=2, default=str)
            st.write(f"  ✅ Module 1 JSON saved")

            st.write("**Module 2:** Running LLM completion (Groq Llama 3.3 70B)...")
            from module2.reasoning import complete_financial_json
            completed = complete_financial_json(m1_dict, raw_text, source_file=uploaded.name)

            llm_path = OUT_DIR / "llm" / (dest.stem + ".json")
            llm_path.parent.mkdir(parents=True, exist_ok=True)
            with open(llm_path, "w") as f:
                json.dump(completed, f, indent=2, default=str)
            st.write("  ✅ LLM extraction complete")
            status.update(label="✅ Extraction complete!", state="complete")

        # ── Auditor Review ─────────────────────────────────────────────────────
        st.divider()
        st.subheader("🔎 Review Extracted Data")
        st.caption("Verify the extracted financial data before proceeding to anomaly detection.")

        with open(llm_path) as f:
            completed = json.load(f)

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**Company Information**")
            st.write(f"**Name:** {completed.get('company_name', '—')}")
            st.write(f"**CIN:** {completed.get('cin', '—')}")
            st.write(f"**FY End:** {completed.get('financial_year_end', '—')}")
            st.write(f"**Auditor:** {completed.get('auditor_name', '—')}")
            st.write(f"**Confidence:** {completed.get('extraction_confidence', 0):.0%}")

        with col_r:
            st.markdown("**Key Financials (₹)**")
            pl = completed.get("profit_and_loss", {})
            bs = completed.get("balance_sheet", {})
            st.write(f"**Revenue:** {pl.get('revenue_from_operations', '—')}")
            st.write(f"**PAT:** {pl.get('profit_after_tax', '—')}")
            ca = bs.get("current_assets", {})
            cl = bs.get("current_liabilities", {})
            se = bs.get("shareholders_equity", {})
            st.write(f"**Cash:** {ca.get('cash_and_cash_equivalents', '—')}")
            st.write(f"**Share Capital:** {se.get('share_capital', '—')}")

        with st.expander("📋 View Full Extracted JSON"):
            st.json(completed)

        if completed.get("audit_observations"):
            st.markdown("**💡 Initial AI Observations**")
            for obs in completed["audit_observations"]:
                st.markdown(f"- {obs}")

        st.divider()
        st.markdown("**Does the extracted data look correct?**")
        col_yes, col_no = st.columns(2)
        if col_yes.button("✅ Looks good — proceed to Anomaly Detection", use_container_width=True, type="primary"):
            st.success("Confirmed! Go to **🔍 Anomaly Detection** in the sidebar.")
            st.balloons()
        if col_no.button("⚠️ Data issues — flag for manual review", use_container_width=True):
            note = st.text_area("Describe the issue (this will be logged):")
            if note:
                flag_path = OUT_DIR / "llm" / (dest.stem + "_review_flag.txt")
                flag_path.write_text(note)
                st.warning("Flagged for manual review. Logged to output folder.")
