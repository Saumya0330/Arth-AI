"""
अर्थAI — Page 2: Anomaly Detection + RAG
Runs Module 3 + Module 4 with auditor review of each flag.
"""

import streamlit as st
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
LLM_DIR    = BASE_DIR / "data" / "output" / "llm"
ANOMALY_DIR = BASE_DIR / "data" / "output" / "anomaly"
RAG_DIR    = BASE_DIR / "data" / "output" / "rag"

st.set_page_config(page_title="Anomaly Detection · अर्थAI", page_icon="🔍", layout="wide")

with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 2 of 5")
    st.divider()
    st.markdown("""
**What happens here:**
- Module 3 runs financial ratio checks
- Benford's Law test for fraud signals
- Module 4 retrieves relevant regulations
  from CARO 2020, SA 700/705 + all your
  other embedded regulatory documents
- You review each flag before report
    """)

st.title("🔍 Step 2 — Anomaly Detection & Regulatory Lookup")
st.divider()

# ── File selector ──────────────────────────────────────────────────────────────
llm_files = sorted(LLM_DIR.glob("*.json")) if LLM_DIR.exists() else []
if not llm_files:
    st.warning("No processed documents found. Complete Step 1 first.")
    st.stop()

names = {f.stem.replace("-", " ").title(): f for f in llm_files}
selected_name = st.selectbox("Select a document", list(names.keys()))
selected_file = names[selected_name]

rag_out = RAG_DIR / selected_file.name
already_done = rag_out.exists()

if already_done:
    st.info("ℹ️ Anomaly detection already run for this document.")

if st.button("▶ Run Anomaly Detection + RAG", type="primary", use_container_width=True):
    with open(selected_file) as f:
        fs = json.load(f)

    with st.status("Running anomaly detection...", expanded=True) as status:
        st.write("**Module 3:** Running financial checks...")
        from module3.anomaly import run_all_checks
        flags = run_all_checks(fs)

        critical = [f for f in flags if f["severity"] == "critical"]
        warnings  = [f for f in flags if f["severity"] == "warning"]
        st.write(f"  ✅ Found **{len(flags)}** flags  "
                 f"(🔴 {len(critical)} critical, 🟡 {len(warnings)} warnings)")

        fs["anomaly_flags"] = flags
        fs["anomaly_summary"] = {
            "total": len(flags), "critical": len(critical),
            "warning": len(warnings), "info": 0
        }

        ANOMALY_DIR.mkdir(parents=True, exist_ok=True)
        anomaly_path = ANOMALY_DIR / selected_file.name
        with open(anomaly_path, "w") as f_out:
            json.dump(fs, f_out, indent=2)

        st.write("**Module 4:** Retrieving regulations from VectorDB...")
        from module4.rag import process_anomaly_flags
        enriched = process_anomaly_flags(fs)

        RAG_DIR.mkdir(parents=True, exist_ok=True)
        with open(rag_out, "w") as f_out:
            json.dump(enriched, f_out, indent=2)
        st.write("  ✅ RAG citations attached to all flags")
        status.update(label="✅ Done!", state="complete")

# ── Show results ───────────────────────────────────────────────────────────────
if rag_out.exists():
    st.divider()
    with open(rag_out) as f:
        enriched = json.load(f)

    flags = enriched.get("anomaly_flags", [])
    if not flags:
        st.success("✅ No anomalies detected for this document.")
    else:
        summary = enriched.get("anomaly_summary", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 Critical", summary.get("critical", 0))
        c2.metric("🟡 Warnings", summary.get("warning", 0))
        c3.metric("Total Flags", summary.get("total", 0))

        st.subheader("Anomaly Flags — Auditor Review")
        st.caption("Review each flag and the AI-retrieved regulation. Mark your decision.")

        for i, flag in enumerate(flags):
            sev = flag["severity"]
            icon = "🔴" if sev == "critical" else "🟡" if sev == "warning" else "🔵"
            with st.expander(f"{icon} [{flag['rule_id']}] {flag['description'][:80]}...", expanded=(sev == "critical")):
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("**Anomaly Details**")
                    st.write(f"**Rule:** `{flag['rule_id']}`")
                    st.write(f"**Severity:** {sev.upper()}")
                    st.write(f"**Field:** `{flag['field']}`")
                    if flag.get("expected"):
                        st.write(f"**Expected:** {flag['expected']}")
                    if flag.get("actual"):
                        st.write(f"**Actual:** {flag['actual']}")

                with col_r:
                    st.markdown("**Retrieved Regulatory Sources**")
                    for p in flag.get("regulatory_passages", [])[:3]:
                        st.markdown(
                            f"📄 `{p['source']}` p.{p['page']} "
                            f"*(relevance: {p['relevance_score']:.2f})*"
                        )

                st.markdown("**AI Regulatory Response**")
                st.info(flag.get("regulatory_response", "—"))

                st.markdown("**Auditor Decision**")
                decision = st.radio(
                    "Your assessment:",
                    ["Confirm — include in report", "Dismiss — not material", "Escalate — needs manual investigation"],
                    key=f"flag_{i}",
                    horizontal=True,
                )
                note = st.text_input("Optional note:", key=f"note_{i}")

        st.divider()
        if st.button("✅ Save decisions & proceed to Report Generation", type="primary", use_container_width=True):
            st.success("Decisions saved! Go to **📄 Report Generation** in the sidebar.")
