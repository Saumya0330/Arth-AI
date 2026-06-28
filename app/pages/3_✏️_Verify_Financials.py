"""
अर्थAI — Page 3: Manual Field Verification

Auditor can review, correct, or fill in any financial field.
Editing a field marks it as 'auditor_verified' in the source trail.
This updated financial_json flows into Agent 3 (RAG) and Agent 4 (Report).
Must be done BEFORE proceeding to Anomaly Detection.
"""

import streamlit as st
import json, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(
    page_title="Verify Financials · अर्थAI", page_icon="✏️", layout="wide"
)

with st.sidebar:
    st.title("अर्थAI")
    st.caption("Step 2 — Verify & Edit Financials")
    st.divider()
    st.markdown("""
**Why this step matters:**
- LLM-extracted values may be wrong
- You can correct any number here
- Edited fields are marked
  `auditor_verified` in the audit trail
- Only verified/regex fields go into
  the final report as trusted facts
    """)
    st.divider()
    thread_id = st.session_state.get("thread_id")
    if thread_id:
        st.info(f"Session:\n`{thread_id}`")
    else:
        st.warning("No active session.\nComplete Step 1 first.")
    from app.rag_chat import render_rag_chat
    render_rag_chat()

# ── Guard ──────────────────────────────────────────────────────────────────────
st.title("✏️ Step 2 — Verify & Correct Financial Fields")
st.caption(
    "Review every extracted value. Correct any errors. "
    "Edited fields are marked **auditor_verified** and trusted by all downstream agents."
)
st.divider()

thread_id = st.session_state.get("thread_id")
if not thread_id:
    st.warning("Complete **Step 1 — Upload & Ingest** first.")
    st.stop()

from agents.orchestrator import get_graph

graph    = get_graph()
config   = {"configurable": {"thread_id": thread_id}}
snapshot = graph.get_state(config)
state    = snapshot.values
fs       = state.get("financial_json", {})
sources  = state.get("field_sources") or fs.get("_sources", {})

if not fs:
    st.warning("No financial data found. Complete Step 1 first.")
    st.stop()

# ── Source summary ─────────────────────────────────────────────────────────────
regex_n    = sum(1 for v in sources.values() if v == "regex")
llm_n      = sum(1 for v in sources.values() if v == "llm")
verified_n = sum(1 for v in sources.values() if v == "auditor_verified")

c1, c2, c3 = st.columns(3)
c1.metric("✅ Regex-extracted", regex_n, help="Trusted — extracted by code")
c2.metric("⚠️ LLM-extracted", llm_n, help="Needs your verification")
c3.metric("🔒 Auditor-verified", verified_n)
st.divider()

# ── Helper: drill into nested dict ────────────────────────────────────────────
def get_nested(d, dotted_path, default=None):
    keys = dotted_path.split(".")
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d

def set_nested(d, dotted_path, value):
    keys = dotted_path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    try:
        d[keys[-1]] = float(value) if value not in ("", None) else None
    except (ValueError, TypeError):
        d[keys[-1]] = value

# ── Section editor factory ─────────────────────────────────────────────────────
def render_section(section_label: str, section_path: str, fields: dict):
    """
    fields = {display_label: dotted_path}
    """
    st.subheader(section_label)
    cols = st.columns(2)
    edits = {}
    for idx, (label, path) in enumerate(fields.items()):
        current_val = get_nested(fs, path)
        src         = sources.get(path, "unknown")
        src_badge   = ("✅" if src == "regex"
                       else "🔒" if src == "auditor_verified"
                       else "⚠️")

        with cols[idx % 2]:
            display = "" if current_val is None else str(current_val)
            new_val = st.text_input(
                f"{src_badge} {label}",
                value=display,
                key=f"edit_{path}",
                help=(f"Source: {src}  |  Path: {path}  |  "
                      f"{'Leave blank to keep as null.' if current_val is None else ''}"),
            )
            edits[path] = (new_val, current_val)
    return edits

# ── All editable sections ──────────────────────────────────────────────────────
all_edits = {}

with st.expander("🏢 Company Information", expanded=True):
    info_fields = {
        "Company Name":    "company_name",
        "CIN":             "cin",
        "PAN":             "pan",
        "Financial Year":  "financial_year_end",
        "Auditor Name":    "auditor_name",
        "Auditor Firm Reg":"auditor_firm_reg",
    }
    for label, path in info_fields.items():
        src = sources.get(path, "unknown")
        src_badge = "✅" if src == "regex" else "🔒" if src == "auditor_verified" else "⚠️"
        current = fs.get(path, "") or ""
        new_val = st.text_input(
            f"{src_badge} {label}", value=str(current), key=f"edit_{path}",
            help=f"Source: {src}"
        )
        all_edits[path] = (new_val, current)

st.divider()

with st.expander("⚖️ Balance Sheet — Shareholders' Equity"):
    all_edits.update(render_section("Shareholders' Equity",
        "balance_sheet.shareholders_equity", {
            "Share Capital":        "balance_sheet.shareholders_equity.share_capital",
            "Reserves & Surplus":   "balance_sheet.shareholders_equity.reserves_and_surplus",
            "Share Warrants Money": "balance_sheet.shareholders_equity.money_received_against_share_warrants",
        }))

with st.expander("⚖️ Balance Sheet — Non-Current Liabilities"):
    all_edits.update(render_section("Non-Current Liabilities",
        "balance_sheet.non_current_liabilities", {
            "Long-Term Borrowings":        "balance_sheet.non_current_liabilities.long_term_borrowings",
            "Deferred Tax Liabilities":    "balance_sheet.non_current_liabilities.deferred_tax_liabilities",
            "Other LT Liabilities":        "balance_sheet.non_current_liabilities.other_long_term_liabilities",
            "Long-Term Provisions":        "balance_sheet.non_current_liabilities.long_term_provisions",
        }))

with st.expander("⚖️ Balance Sheet — Current Liabilities"):
    all_edits.update(render_section("Current Liabilities",
        "balance_sheet.current_liabilities", {
            "Short-Term Borrowings":       "balance_sheet.current_liabilities.short_term_borrowings",
            "Trade Payables":              "balance_sheet.current_liabilities.trade_payables",
            "Other Current Liabilities":   "balance_sheet.current_liabilities.other_current_liabilities",
            "Short-Term Provisions":       "balance_sheet.current_liabilities.short_term_provisions",
        }))

with st.expander("🏗️ Balance Sheet — Non-Current Assets"):
    all_edits.update(render_section("Non-Current Assets",
        "balance_sheet.non_current_assets", {
            "Tangible Fixed Assets":       "balance_sheet.non_current_assets.fixed_assets_tangible",
            "Intangible Assets":           "balance_sheet.non_current_assets.fixed_assets_intangible",
            "Capital WIP":                 "balance_sheet.non_current_assets.capital_wip",
            "Long-Term Investments":       "balance_sheet.non_current_assets.long_term_investments",
            "Deferred Tax Assets":         "balance_sheet.non_current_assets.deferred_tax_assets",
            "LT Loans & Advances":         "balance_sheet.non_current_assets.long_term_loans_and_advances",
            "Other Non-Current Assets":    "balance_sheet.non_current_assets.other_non_current_assets",
        }))

with st.expander("🏗️ Balance Sheet — Current Assets"):
    all_edits.update(render_section("Current Assets",
        "balance_sheet.current_assets", {
            "Inventories":                 "balance_sheet.current_assets.inventories",
            "Trade Receivables":           "balance_sheet.current_assets.trade_receivables",
            "Cash & Cash Equivalents":     "balance_sheet.current_assets.cash_and_cash_equivalents",
            "ST Loans & Advances":         "balance_sheet.current_assets.short_term_loans_and_advances",
            "Other Current Assets":        "balance_sheet.current_assets.other_current_assets",
        }))

with st.expander("📈 Profit & Loss Statement"):
    all_edits.update(render_section("P&L",
        "profit_and_loss", {
            "Revenue from Operations":     "profit_and_loss.revenue_from_operations",
            "Other Income":                "profit_and_loss.other_income",
            "Cost of Materials":           "profit_and_loss.cost_of_materials",
            "Employee Benefits Expense":   "profit_and_loss.employee_benefits_expense",
            "Finance Costs":               "profit_and_loss.finance_costs",
            "Depreciation":                "profit_and_loss.depreciation",
            "Other Expenses":              "profit_and_loss.other_expenses",
            "Exceptional Items":           "profit_and_loss.exceptional_items",
            "Tax Expense":                 "profit_and_loss.tax_expense",
            "Profit After Tax":            "profit_and_loss.profit_after_tax",
        }))

# ── Save edits ─────────────────────────────────────────────────────────────────
st.divider()
changed = {path: new for path, (new, old) in all_edits.items()
           if str(new) != str(old if old is not None else "")}

if changed:
    st.info(f"**{len(changed)} field(s) modified** — click Save to apply.")
else:
    st.success("No changes made yet.")

if st.button("💾 Save Verified Values", type="primary",
             use_container_width=True, disabled=not changed):

    # Apply changes to a copy of financial_json
    import copy
    updated_fs      = copy.deepcopy(fs)
    updated_sources = dict(sources)

    for path, new_val in changed.items():
        set_nested(updated_fs, path, new_val if new_val != "" else None)
        # Mark as auditor_verified only if a real value was provided
        if new_val.strip() != "":
            updated_sources[path] = "auditor_verified"
        else:
            # Auditor explicitly cleared it — remove from sources
            updated_sources.pop(path, None)

    updated_fs["_sources"] = updated_sources

    # Push updated state back into LangGraph
    graph.update_state(
        config,
        {"financial_json": updated_fs, "field_sources": updated_sources},
    )

    # Recount for display
    new_verified = sum(1 for v in updated_sources.values() if v == "auditor_verified")
    st.success(
        f"✅ {len(changed)} field(s) saved and marked **auditor_verified**.  \n"
        f"Total verified fields: {new_verified}"
    )
    st.balloons()
    st.rerun()
