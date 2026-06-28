"""
अर्थAI — Page 2: Anomaly Detection & Regulatory Lookup

Resumes the LangGraph graph from the human_review_flags checkpoint.
Auditor reviews each flag, marks decisions, then graph resumes:
  Agent 3 (RAG) fetches citations only for confirmed flags.
Graph then pauses again at human_review_report.
"""

import streamlit as st
import json, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(page_title="Anomaly Detection · अर्थAI", page_icon="🔍", layout="wide")

with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 2 — Anomaly Detection")
    st.divider()
    st.markdown("""
**Agents running here:**
- **Agent 2** (already ran) detected compliance flags
- You review each flag and decide:
  - ✅ Confirm → goes to RAG
  - ❌ Dismiss → dropped entirely
  - ⚡ Escalate → goes to RAG + marked urgent
- **Agent 3 (RAG)** retrieves CARO/SA citations
  only for your confirmed flags
    """)
    st.divider()
    thread_id = st.session_state.get("thread_id")
    if thread_id:
        st.info(f"Session:\n`{thread_id}`")
    else:
        st.warning("No active session.\nComplete Step 1 first.")

st.title("🔍 Step 2 — Anomaly Detection & Regulatory Lookup")
st.divider()

# ── Guard: need active session ─────────────────────────────────────────────────
thread_id = st.session_state.get("thread_id")
if not thread_id:
    st.warning("⚠️ No active session found. Please complete **Step 1 — Upload & Ingest** first.")
    st.stop()

import warnings; warnings.filterwarnings("ignore")
from agents.orchestrator import get_graph

graph  = get_graph()
config = {"configurable": {"thread_id": thread_id}}

# Get current graph state
snapshot = graph.get_state(config)
state    = snapshot.values
current_step = state.get("current_step", "")
next_nodes   = list(snapshot.next)

# ── Already past flag review? ──────────────────────────────────────────────────
already_past_rag = current_step in ("rag_complete", "report_drafted", "report_finalised")
if already_past_rag:
    st.info("ℹ️ Flag review already completed for this session.")
    flags_with_citations = state.get("flags_with_citations", [])
    st.subheader("Confirmed Flags with Regulatory Citations")
    _show_cited_flags(flags_with_citations)
    st.success("Proceed to **📄 Report Generation**.")
    st.stop()

# ── Show anomaly flags from Agent 2 ───────────────────────────────────────────
flags = state.get("anomaly_flags", [])
math  = state.get("math_report", {})

# Math summary banner
if math.get("has_critical_errors"):
    st.error(
        f"🔴 **Agent 1 (Math Validator) found {len(math.get('critical_failures', []))} "
        f"critical arithmetic error(s)** — these are included below."
    )

if not flags and not math.get("has_critical_errors"):
    st.success("✅ No compliance anomalies detected by Agent 2.")
    if st.button("Proceed to Report Generation →", type="primary"):
        graph.update_state(config, {"confirmed_flags": [], "auditor_flag_decisions": {}},
                           as_node="human_review_flags")
        graph.invoke(None, config)
        st.success("Graph resumed. Proceed to **📄 Report Generation**.")
    st.stop()

st.subheader(f"Agent 2 found {len(flags)} compliance flag(s) — review each below")
st.caption("For each flag: confirm to include in the report, dismiss to drop it, or escalate for urgent attention.")

# ── Per-flag review UI ─────────────────────────────────────────────────────────
decisions = {}
SEVERITY_ICON = {"critical": "🔴", "warning": "🟡", "info": "🔵"}

# Merge math critical failures as extra flags to review
all_display_flags = list(flags)
for cf in math.get("critical_failures", []):
    all_display_flags.insert(0, {
        "rule_id":     "MATH-" + cf["check"][:10].replace(" ", "_"),
        "severity":    "critical",
        "field":       "balance_sheet / profit_and_loss",
        "description": f"Arithmetic error: {cf['check']} — "
                       f"expected {cf['expected']}, got {cf['actual']}, diff {cf['difference']}",
        "expected":    str(cf.get("expected")),
        "actual":      str(cf.get("actual")),
    })

for i, flag in enumerate(all_display_flags):
    sev  = flag.get("severity", "warning")
    icon = SEVERITY_ICON.get(sev, "🟡")
    rule = flag.get("rule_id", f"FLAG-{i}")

    with st.expander(
        f"{icon} [{rule}]  {flag.get('description', '')[:90]}...",
        expanded=(sev == "critical")
    ):
        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.markdown("**Anomaly Details**")
            st.write(f"**Rule ID:** `{rule}`")
            st.write(f"**Severity:** `{sev.upper()}`")
            st.write(f"**Field:** `{flag.get('field', '—')}`")
            if flag.get("expected"):
                st.write(f"**Expected:** {flag['expected']}")
            if flag.get("actual"):
                st.write(f"**Actual:** {flag['actual']}")

        with col_r:
            st.markdown("**Your Decision**")
            decision = st.radio(
                "Decision",
                options=["✅ Confirm — include in report",
                         "❌ Dismiss — not material",
                         "⚡ Escalate — urgent, needs investigation"],
                index=0,
                key=f"decision_{i}",
                label_visibility="collapsed",
            )
            note = st.text_input("Auditor note (optional)", key=f"note_{i}")

        decisions[rule] = (
            "confirm"   if "Confirm"   in decision else
            "dismiss"   if "Dismiss"   in decision else
            "escalate"
        )

st.divider()

# ── Submit decisions + resume graph ───────────────────────────────────────────
confirmed_count  = sum(1 for v in decisions.values() if v in ("confirm", "escalate"))
dismissed_count  = sum(1 for v in decisions.values() if v == "dismiss")

col_summary, col_btn = st.columns([2, 1])
col_summary.markdown(
    f"**Summary:** {confirmed_count} flag(s) will go to RAG · "
    f"{dismissed_count} dismissed"
)

if col_btn.button("▶ Submit Decisions & Fetch Regulatory Citations",
                   type="primary", use_container_width=True):
    # Map decisions back onto the original (non-math) flags
    confirmed_flags = [
        f for f in flags
        if decisions.get(f["rule_id"], "confirm") != "dismiss"
    ]

    with st.status("Agent 3: Fetching regulatory citations from VectorDB...",
                   expanded=True) as status:
        # Resume graph through human_review_flags → rag_retriever
        graph.update_state(
            config,
            {"auditor_flag_decisions": decisions,
             "confirmed_flags": confirmed_flags},
            as_node="human_review_flags",
        )
        result = graph.invoke(None, config)
        status.update(label="✅ Citations retrieved!", state="complete")

    cited_flags = result.get("flags_with_citations", [])
    st.divider()
    st.subheader(f"📚 Regulatory Citations — {len(cited_flags)} flag(s)")

    for flag in cited_flags:
        rule = flag.get("rule_id", "?")
        sev  = flag.get("severity", "warning")
        icon = SEVERITY_ICON.get(sev, "🟡")
        with st.expander(f"{icon} [{rule}] Regulatory Response", expanded=True):
            st.markdown("**Retrieved Sources**")
            for p in flag.get("regulatory_passages", [])[:3]:
                st.markdown(
                    f"📄 `{p['source']}` p.{p['page']}  "
                    f"*(relevance: {p['relevance_score']:.2f})*"
                )
            st.markdown("**AI Regulatory Response**")
            st.info(flag.get("regulatory_response", "—"))

    st.divider()
    st.success("✅ RAG complete! Proceed to **📄 Report Generation** in the sidebar.")
