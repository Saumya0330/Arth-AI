"""
अर्थAI — Page 3: Report Generation & Auditor Review

Resumes the graph: Agent 4 drafts the report, graph pauses at
human_review_report. Auditor edits each section, then finalises.
"""

import streamlit as st
import json, sys
from pathlib import Path
from datetime import date

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
REPORT_DIR = BASE_DIR / "data" / "output" / "reports"
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(page_title="Report Generation · अर्थAI", page_icon="📄", layout="wide")

with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 3 — Report Generation")
    st.divider()
    st.markdown("""
**Agent 4 (Report Drafter):**
- Receives financial data + RAG-cited flags
- No memory of other agents
- Clean context = less hallucination
- Writes full ICAI SA 700/705 report

**You then:**
- Edit any section inline
- Download final .md report
    """)
    st.divider()
    thread_id = st.session_state.get("thread_id")
    if thread_id:
        st.info(f"Session:\n`{thread_id}`")
    else:
        st.warning("No active session.")

st.title("📄 Step 3 — Audit Report Generation")
st.divider()

# ── Guard ──────────────────────────────────────────────────────────────────────
thread_id = st.session_state.get("thread_id")
if not thread_id:
    st.warning("No active session. Complete Steps 1 and 2 first.")
    st.stop()

import warnings; warnings.filterwarnings("ignore")
from agents.orchestrator import get_graph

graph    = get_graph()
config   = {"configurable": {"thread_id": thread_id}}
snapshot = graph.get_state(config)
state    = snapshot.values
step     = state.get("current_step", "")

# ── Check pipeline readiness ───────────────────────────────────────────────────
if step not in ("rag_complete", "report_drafted", "report_finalised"):
    st.warning(f"⚠️ Pipeline is at step `{step}`. Complete Step 2 first.")
    st.stop()

# ── Generate report (runs Agent 4) ────────────────────────────────────────────
report_drafted = step in ("report_drafted", "report_finalised")

if not report_drafted:
    if st.button("▶ Generate Audit Report Draft (Agent 4)", type="primary", use_container_width=True):
        with st.status("Agent 4: Drafting audit report...", expanded=True) as status:
            result = graph.invoke(None, config)
            status.update(label="✅ Draft ready for your review!", state="complete")
        st.rerun()
    else:
        st.info("Click above to have Agent 4 draft the audit report from the RAG-enriched data.")
        st.stop()

# ── Load report from state ─────────────────────────────────────────────────────
snapshot = graph.get_state(config)
state    = snapshot.values
report   = state.get("report_sections", {})
sections = report.get("report_sections", {}) if report else {}

if not sections:
    st.error("Report sections not found in state. Please re-run.")
    st.stop()

company  = report.get("company_name", "—")
fy       = report.get("financial_year", "—")
opinion  = sections.get("overall_opinion_type", "unmodified").upper()
badge    = {"UNMODIFIED": "✅ Unmodified", "QUALIFIED": "⚠️ Qualified",
            "ADVERSE": "🔴 Adverse", "DISCLAIMER_OF_OPINION": "🔴 Disclaimer"}.get(opinion, opinion)

# ── Report header ──────────────────────────────────────────────────────────────
st.subheader(f"Draft Report — {company}")
h1, h2, h3, h4 = st.columns(4)
h1.metric("Opinion", badge)
h2.metric("Financial Year", fy)
h3.metric("Flags Addressed", len(state.get("flags_with_citations") or []))
h4.metric("Status", "DRAFT")

st.caption(
    "⚠️ **Every section is editable.** Review the AI draft, make corrections, "
    "then save or download."
)
st.divider()

# ── Editable sections ──────────────────────────────────────────────────────────
edited = {}

def section(key, label, content, height=160):
    st.markdown(f"### {label}")
    st.caption("`[AUDITOR: REVIEW REQUIRED]`")
    val = st.text_area(label, value=content, height=height,
                       key=f"sec_{key}", label_visibility="collapsed")
    edited[key] = val
    st.divider()

op  = sections.get("opinion_section", {})
boo = sections.get("basis_of_opinion", {})
fh  = sections.get("financial_highlights", {})
mr  = sections.get("management_responsibility", {})
ar  = sections.get("auditor_responsibility", {})
olr = sections.get("report_on_other_legal_requirements", {})
kam = sections.get("key_audit_matters", {})

# Qualification basis (only if modified opinion)
qual = sections.get("qualification_basis")
if qual and qual != "null":
    section("qual_basis", "📝 Basis for Qualification", qual, height=120)

section("opinion",    "📝 Opinion",              op.get("body", ""))
section("basis",      "📝 Basis for Opinion",    boo.get("body", ""))
section("highlights", "📝 Financial Highlights", fh.get("body", ""))

# KAMs
st.markdown("### 📝 Key Audit Matters")
st.caption("`[AUDITOR: REVIEW REQUIRED]`")
for i, item in enumerate(kam.get("items", []), 1):
    edited[f"kam_{i}"] = st.text_area(
        f"KAM {i}", value=item, height=130, key=f"sec_kam_{i}")
st.divider()

section("mgmt",    "�� Management Responsibility", mr.get("body", ""), height=130)
section("auditor", "📝 Auditor Responsibility",    ar.get("body", ""), height=130)

caro_text = "\n".join(f"{i+1}. {o}"
    for i, o in enumerate(olr.get("caro_observations", [])))
section("caro", "📝 CARO 2020 Observations", caro_text, height=120)

# ── Finalise ───────────────────────────────────────────────────────────────────
st.markdown("### ✍️ Auditor Sign-off")
st.caption("`[AUDITOR: COMPLETE BEFORE FINALISING]`")
col_a, col_b = st.columns(2)
firm_name = col_a.text_input("Firm Name", placeholder="e.g. ABC & Associates")
firm_reg  = col_a.text_input("Firm Reg. No.", placeholder="e.g. 123456W")
ca_name   = col_b.text_input("Auditor Name", placeholder="e.g. CA Priya Sharma")
memb_no   = col_b.text_input("Membership No.", placeholder="e.g. 123456")
place     = col_a.text_input("Place", placeholder="e.g. Mumbai")
sign_date = col_b.date_input("Date", value=date.today())

st.divider()
col_save, col_dl = st.columns(2)

if col_save.button("💾 Save & Finalise Report", type="primary", use_container_width=True):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = state.get("source_file", "report").replace(".pdf", "")

    # Build markdown
    md_lines = [
        "# Independent Auditor's Report",
        f"## {company}",
        f"**Financial Year Ending:** {fy}  ",
        f"**Opinion Type:** {badge}  ",
        f"**Status:** AUDITOR-REVIEWED FINAL DRAFT  ",
        "", "---", "",
    ]
    for key, label in [
        ("qual_basis", "Basis for Qualification"),
        ("opinion",    "Opinion"),
        ("basis",      "Basis for Opinion"),
        ("highlights", "Financial Highlights"),
    ]:
        if key in edited:
            md_lines += [f"## {label}", "", edited[key], "", "---", ""]

    md_lines += ["## Key Audit Matters", ""]
    for i in range(1, len(kam.get("items", [])) + 1):
        if f"kam_{i}" in edited:
            md_lines += [f"### KAM {i}", "", edited[f"kam_{i}"], ""]

    md_lines += ["---", ""]
    for key, label in [
        ("mgmt",    "Management's Responsibility"),
        ("auditor", "Auditor's Responsibility"),
        ("caro",    "CARO 2020 Observations"),
    ]:
        if key in edited:
            md_lines += [f"## {label}", "", edited[key], "", "---", ""]

    # Sign-off
    md_lines += [
        "## Auditor Sign-off", "",
        f"**For:** {firm_name or '_______________'}  ",
        "**Chartered Accountants**  ",
        f"**Firm Reg. No.:** {firm_reg or '_______________'}  ",
        "",
        f"**Name:** {ca_name or '_______________'}  ",
        f"**Membership No.:** {memb_no or '_______________'}  ",
        f"**Place:** {place or '_______________'}  ",
        f"**Date:** {sign_date.isoformat()}  ",
        "",
        "---",
        "*Generated by अर्थAI — AI-Augmented Financial Audit System*  ",
        "*Reviewed and approved by a qualified CA.*",
    ]

    final_md = "\n".join(md_lines)
    out_path = REPORT_DIR / f"{stem}_final.md"
    out_path.write_text(final_md)

    # Resume graph to finalise
    graph.update_state(config, {"auditor_edits": edited, "report_finalised": True},
                       as_node="human_review_report")
    graph.invoke(None, config)

    st.success(f"✅ Report finalised and saved to `data/output/reports/{stem}_final.md`")
    st.balloons()

    # Download button
    col_dl.download_button(
        "⬇️ Download Final Report (.md)",
        data=final_md,
        file_name=f"{stem}_final.md",
        mime="text/markdown",
        use_container_width=True,
    )

elif state.get("report_markdown"):
    # Download draft even before finalising
    col_dl.download_button(
        "⬇️ Download Draft (.md)",
        data=state["report_markdown"],
        file_name="audit_report_draft.md",
        mime="text/markdown",
        use_container_width=True,
    )

with st.expander("👁️ Preview current draft (Markdown render)"):
    st.markdown(state.get("report_markdown", "_No draft yet._"))
