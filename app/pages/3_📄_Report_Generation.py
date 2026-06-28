"""
अर्थAI — Page 3: Report Generation & Review
Runs Module 5, shows report, lets auditor edit each section.
"""

import streamlit as st
import json
from pathlib import Path
import sys

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
RAG_DIR    = BASE_DIR / "data" / "output" / "rag"
REPORT_DIR = BASE_DIR / "data" / "output" / "reports"

st.set_page_config(page_title="Report Generation · अर्थAI", page_icon="📄", layout="wide")

with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 3 of 5")
    st.divider()
    st.markdown("""
**What happens here:**
- Module 5 generates full ICAI-format
  audit report draft
- You review and edit each section
- Download final report as Markdown
    """)

st.title("📄 Step 3 — Audit Report Generation")
st.divider()

# ── File selector ──────────────────────────────────────────────────────────────
rag_files = sorted(RAG_DIR.glob("*.json")) if RAG_DIR.exists() else []
if not rag_files:
    st.warning("No anomaly-checked documents found. Complete Step 2 first.")
    st.stop()

names = {f.stem.replace("-", " ").title(): f for f in rag_files}
selected_name = st.selectbox("Select a document", list(names.keys()))
selected_file = names[selected_name]
report_json   = REPORT_DIR / selected_file.name
report_md     = REPORT_DIR / (selected_file.stem + ".md")

if st.button("▶ Generate Audit Report Draft", type="primary", use_container_width=True):
    with open(selected_file) as f:
        fs = json.load(f)
    with st.status("Generating report with Groq LLM...", expanded=True) as status:
        from module5.report_generator import generate_report
        from module5.renderer import render_markdown
        report = generate_report(fs)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with open(report_json, "w") as f:
            json.dump(report, f, indent=2, default=str)
        md = render_markdown(report)
        with open(report_md, "w") as f:
            f.write(md)
        status.update(label="✅ Report draft ready!", state="complete")

# ── Show report ────────────────────────────────────────────────────────────────
if report_json.exists():
    st.divider()
    with open(report_json) as f:
        report = json.load(f)

    sections = report.get("report_sections", {})
    opinion  = sections.get("overall_opinion_type", "unmodified").upper()
    badge    = {"UNMODIFIED": "✅ Unmodified", "QUALIFIED": "⚠️ Qualified",
                "ADVERSE": "🔴 Adverse", "DISCLAIMER_OF_OPINION": "🔴 Disclaimer"}.get(opinion, opinion)

    st.subheader(f"Draft Report — {report.get('company_name', '')}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Opinion Type", badge)
    col2.metric("Financial Year", report.get("financial_year", "—"))
    col3.metric("Status", "DRAFT")

    st.caption("⚠️ Review and edit each section before finalising. Changes are saved when you click **Save Section**.")
    st.divider()

    edited_sections = {}

    def _editable_section(key: str, label: str, content: str):
        st.markdown(f"### {label}")
        st.caption("`[AUDITOR: REVIEW REQUIRED]`")
        edited = st.text_area(label, value=content, height=160, key=key, label_visibility="collapsed")
        edited_sections[key] = edited
        st.divider()

    op  = sections.get("opinion_section", {})
    boo = sections.get("basis_of_opinion", {})
    fh  = sections.get("financial_highlights", {})
    mr  = sections.get("management_responsibility", {})
    ar  = sections.get("auditor_responsibility", {})
    olr = sections.get("report_on_other_legal_requirements", {})
    kam = sections.get("key_audit_matters", {})

    _editable_section("opinion",   "📝 Opinion",              op.get("body", ""))
    _editable_section("basis",     "📝 Basis for Opinion",    boo.get("body", ""))
    _editable_section("highlights","📝 Financial Highlights", fh.get("body", ""))

    # KAMs as individual text areas
    st.markdown("### 📝 Key Audit Matters")
    st.caption("`[AUDITOR: REVIEW REQUIRED]`")
    for i, item in enumerate(kam.get("items", []), 1):
        edited_sections[f"kam_{i}"] = st.text_area(
            f"KAM {i}", value=item, height=120, key=f"kam_{i}")
    st.divider()

    _editable_section("mgmt",      "📝 Management Responsibility", mr.get("body", ""))
    _editable_section("auditor",   "📝 Auditor Responsibility",    ar.get("body", ""))

    # CARO observations
    st.markdown("### 📝 CARO 2020 Observations")
    st.caption("`[AUDITOR: REVIEW REQUIRED]`")
    caro_text = "\n".join(f"{i+1}. {o}" for i, o in enumerate(olr.get("caro_observations", [])))
    edited_sections["caro"] = st.text_area("CARO Observations", value=caro_text,
                                            height=120, key="caro", label_visibility="collapsed")
    st.divider()

    col_save, col_dl = st.columns(2)
    if col_save.button("💾 Save Edited Report", use_container_width=True, type="primary"):
        # Rebuild markdown from edited content
        md_lines = [
            f"# Independent Auditor's Report",
            f"## {report.get('company_name', '')}",
            f"**Financial Year:** {report.get('financial_year', '')}  ",
            f"**Opinion:** {badge}  ",
            f"**Status:** AUDITOR-REVIEWED DRAFT",
            "", "---", "",
            "## Opinion", "", edited_sections.get("opinion", ""), "", "---", "",
            "## Basis for Opinion", "", edited_sections.get("basis", ""), "", "---", "",
            "## Financial Highlights", "", edited_sections.get("highlights", ""), "", "---", "",
            "## Key Audit Matters", "",
        ]
        for i in range(1, len(kam.get("items", [])) + 1):
            md_lines += [f"### KAM {i}", "", edited_sections.get(f"kam_{i}", ""), ""]
        md_lines += [
            "---", "",
            "## Management's Responsibility", "", edited_sections.get("mgmt", ""), "", "---", "",
            "## Auditor's Responsibility", "", edited_sections.get("auditor", ""), "", "---", "",
            "## CARO 2020 Observations", "", edited_sections.get("caro", ""), "", "---", "",
            "## Auditor Sign-off", "",
            "**For:** ___________________________  ",
            "**Firm Reg. No.:** _______________  ",
            "**Name:** _______________________  ",
            "**Membership No.:** ______________  ",
            "**Date:** _______________  ",
            "", "*Generated by अर्थAI*",
        ]
        final_md = "\n".join(md_lines)
        reviewed_path = REPORT_DIR / (selected_file.stem + "_reviewed.md")
        reviewed_path.write_text(final_md)
        st.success(f"✅ Saved to `{reviewed_path.name}`")

    # Download button
    if report_md.exists():
        col_dl.download_button(
            "⬇️ Download Report (.md)",
            data=report_md.read_text(),
            file_name=report_md.name,
            mime="text/markdown",
            use_container_width=True,
        )

    with st.expander("👁️ Preview Full Report (Markdown)"):
        if report_md.exists():
            st.markdown(report_md.read_text())
