"""
अर्थAI — Page 2: Anomaly Detection & Regulatory Lookup
Agent 2 (compliance) output → auditor reviews flags → Agent 3 (RAG) fetches citations.
"""

import streamlit as st
import json, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(page_title="Anomaly Detection · अर्थAI", page_icon="🔍", layout="wide")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 2 — Anomaly Detection")
    st.divider()
    st.markdown("""
**Agents running here:**
- **Agent 2** detected compliance flags  
- You review each flag:
  - ✅ Confirm → sent to RAG
  - ❌ Dismiss → dropped
  - ⚡ Escalate → urgent + RAG
- **Agent 3 (RAG)** retrieves CARO/SA  
  citations for confirmed flags only
    """)
    st.divider()
    from app.rag_chat import render_rag_chat
    render_rag_chat()
    thread_id = st.session_state.get("thread_id")
    if thread_id:
        st.info(f"Session:\n`{thread_id}`")
    else:
        st.warning("No active session.\nComplete Step 1 first.")

# ── Helper functions (must be defined before use) ──────────────────────────────

SEVERITY_ICON = {"critical": "🔴", "warning": "🟡", "info": "🔵"}

def show_cited_flags(flags: list):
    if not flags:
        st.success("No flags to show.")
        return
    for flag in flags:
        sev  = flag.get("severity", "warning")
        icon = SEVERITY_ICON.get(sev, "🟡")
        with st.expander(f"{icon} [{flag.get('rule_id','?')}] {flag.get('description','')[:80]}..."):
            st.markdown("**Retrieved Regulatory Sources**")
            for p in flag.get("regulatory_passages", [])[:3]:
                st.markdown(
                    f"📄 `{p['source']}` p.{p['page']}  "
                    f"*(relevance: {p['relevance_score']:.2f})*"
                )
            st.markdown("**AI Regulatory Response**")
            st.info(flag.get("regulatory_response", "—"))


def show_source_panel(state: dict):
    """Show which financial fields are regex-extracted vs LLM-extracted."""
    sources = state.get("field_sources") or state.get("financial_json", {}).get("_sources", {})
    if not sources:
        return

    llm_fields   = {k: v for k, v in sources.items() if v == "llm"}
    regex_fields = {k: v for k, v in sources.items() if v == "regex"}
    verified     = {k: v for k, v in sources.items() if v == "auditor_verified"}

    st.subheader("📋 Field Source Audit Trail")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Regex-extracted", len(regex_fields), help="Extracted deterministically by code")
    c2.metric("⚠️ LLM-extracted", len(llm_fields), help="Filled by LLM — needs verification")
    c3.metric("🔒 Auditor-verified", len(verified))

    if regex_fields:
        with st.expander(f"✅ {len(regex_fields)} regex-extracted fields (trusted)", expanded=False):
            fs = state.get("financial_json", {})
            rows = []
            for path in sorted(regex_fields):
                val = fs
                for key in path.split("."):
                    val = val.get(key, "—") if isinstance(val, dict) else "—"
                rows.append({"Field": path, "Value": str(val), "Source": "✅ regex"})
            st.table(rows)

    if llm_fields:
        with st.expander(f"⚠️ {len(llm_fields)} LLM-extracted fields (verify before finalising)", expanded=True):
            fs = state.get("financial_json", {})
            rows = []
            for path in sorted(llm_fields):
                val = fs
                for key in path.split("."):
                    val = val.get(key, "—") if isinstance(val, dict) else "—"
                rows.append({"Field": path, "Value": str(val), "Source": "⚠️ LLM"})
            st.table(rows)
            st.caption("These values were extracted by the LLM from OCR text. "
                       "Cross-check against the source PDF before signing the report.")


# ── Main ───────────────────────────────────────────────────────────────────────
st.title("🔍 Step 2 — Anomaly Detection & Regulatory Lookup")
st.divider()

thread_id = st.session_state.get("thread_id")
if not thread_id:
    st.warning("⚠️ No active session. Complete **Step 1 — Upload & Ingest** first.")
    st.stop()

from agents.orchestrator import get_graph

graph    = get_graph()
config   = {"configurable": {"thread_id": thread_id}}
snapshot = graph.get_state(config)
state    = snapshot.values
step     = state.get("current_step", "")
next_nodes = list(snapshot.next)

# Show source audit trail on this page too
show_source_panel(state)
st.divider()

# ── Already past flag review ───────────────────────────────────────────────────
if step in ("rag_complete", "report_drafted", "report_finalised"):
    st.info("ℹ️ Flag review already completed for this session.")
    st.subheader("Confirmed Flags with Regulatory Citations")
    show_cited_flags(state.get("flags_with_citations", []))
    st.success("Proceed to **📄 Report Generation**.")
    st.stop()

# ── Show anomaly flags from Agent 2 ───────────────────────────────────────────
flags = state.get("anomaly_flags", [])
math  = state.get("math_report", {})

if math.get("has_critical_errors"):
    st.error(
        f"🔴 **Agent 1 (Math Validator): {len(math.get('critical_failures', []))} "
        f"critical arithmetic error(s) found**"
    )

if not flags and not math.get("has_critical_errors"):
    st.success("✅ No compliance anomalies detected.")
    if st.button("Proceed to Report Generation →", type="primary"):
        graph.update_state(config, {"confirmed_flags": [], "auditor_flag_decisions": {}},
                           as_node="human_review_flags")
        graph.invoke(None, config)
        st.success("Go to **📄 Report Generation**.")
    st.stop()

st.subheader(f"Agent 2 found {len(flags)} compliance flag(s) — review each below")
st.caption("Confirm to include in report · Dismiss to drop · Escalate for urgent attention")

# ── Build display list (merge math failures) ───────────────────────────────────
display_flags = []
for cf in math.get("critical_failures", []):
    display_flags.append({
        "rule_id":     "MATH-" + cf["check"][:12].replace(" ", "_"),
        "severity":    "critical",
        "field":       "balance_sheet / profit_and_loss",
        "description": f"Arithmetic error: {cf['check']} — "
                       f"expected {cf['expected']}, got {cf['actual']} (diff {cf['difference']})",
        "expected":    str(cf.get("expected")),
        "actual":      str(cf.get("actual")),
    })
display_flags.extend(flags)

decisions = {}
for i, flag in enumerate(display_flags):
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
                ["✅ Confirm — include in report",
                 "❌ Dismiss — not material",
                 "⚡ Escalate — urgent"],
                index=0, key=f"dec_{i}", label_visibility="collapsed",
            )
            st.text_input("Auditor note (optional)", key=f"note_{i}")

        decisions[rule] = (
            "confirm"  if "Confirm"  in decision else
            "dismiss"  if "Dismiss"  in decision else
            "escalate"
        )

# ── Submit ─────────────────────────────────────────────────────────────────────
st.divider()
confirmed_n = sum(1 for v in decisions.values() if v != "dismiss")
dismissed_n = sum(1 for v in decisions.values() if v == "dismiss")

st.markdown(f"**{confirmed_n} flag(s) → RAG · {dismissed_n} dismissed**")

if st.button("▶ Submit Decisions & Fetch Regulatory Citations",
             type="primary", use_container_width=True):

    confirmed_flags = [
        f for f in flags
        if decisions.get(f["rule_id"], "confirm") != "dismiss"
    ]

    with st.status("Agent 3: Fetching citations from VectorDB...", expanded=True) as status:
        graph.update_state(
            config,
            {"auditor_flag_decisions": decisions, "confirmed_flags": confirmed_flags},
            as_node="human_review_flags",
        )
        result = graph.invoke(None, config)
        status.update(label="✅ Citations retrieved!", state="complete")

    cited = result.get("flags_with_citations", [])
    st.divider()
    st.subheader(f"📚 Regulatory Citations — {len(cited)} flag(s)")
    show_cited_flags(cited)
    st.divider()
    st.success("✅ Done! Proceed to **📄 Report Generation** in the sidebar.")
