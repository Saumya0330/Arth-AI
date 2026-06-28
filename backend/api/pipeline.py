"""
अर्थAI — Pipeline API

POST /api/pipeline/{id}/flags/review     — submit auditor flag decisions → resumes graph → RAG runs
POST /api/pipeline/{id}/report/generate  — trigger Agent 4 (report drafter)
POST /api/pipeline/{id}/report/finalise  — save auditor edits, mark complete
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# ── Request models ─────────────────────────────────────────────────────────────

class FlagDecision(BaseModel):
    rule_id:  str
    decision: str   # "confirm" | "dismiss" | "escalate"
    note:     Optional[str] = None


class FlagReviewRequest(BaseModel):
    decisions: List[FlagDecision]


class ReportFinaliseRequest(BaseModel):
    edits: Dict[str, str]           # section_key → edited text
    auditor_name:    Optional[str] = None
    firm_name:       Optional[str] = None
    firm_reg:        Optional[str] = None
    membership_no:   Optional[str] = None
    place:           Optional[str] = None
    sign_date:       Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/{session_id}/flags/review")
def review_flags(session_id: str, body: FlagReviewRequest):
    """
    Auditor submits flag decisions.
    Dismissed flags are dropped; confirmed/escalated go to Agent 3 (RAG).
    Graph resumes through human_review_flags → rag_retriever → report_drafter.
    Returns state including flags_with_citations.
    """
    from backend.core.pipeline_runner import get_state, invoke

    state = get_state(session_id)
    if not state.get("financial_json"):
        raise HTTPException(404, f"Session '{session_id}' not found.")

    all_flags  = state.get("anomaly_flags") or []
    decisions  = {d.rule_id: d.decision for d in body.decisions}
    confirmed  = [f for f in all_flags
                  if decisions.get(f["rule_id"], "confirm") != "dismiss"]

    result = invoke(
        session_id,
        update={"auditor_flag_decisions": decisions, "confirmed_flags": confirmed},
        as_node="human_review_flags",
    )

    # Graph pauses again at human_review_report after report is drafted
    return {
        "current_step":         result.get("current_step"),
        "next_nodes":           result.get("_next_nodes", []),
        "confirmed_flags_count": len(confirmed),
        "dismissed_count":      len(body.decisions) - len(confirmed),
        "flags_with_citations": result.get("flags_with_citations", []),
        "report_sections":      result.get("report_sections"),
        "report_markdown":      result.get("report_markdown"),
    }


@router.post("/{session_id}/report/finalise")
def finalise_report(session_id: str, body: ReportFinaliseRequest):
    """
    Auditor saves edits and signs off.
    Graph resumes through human_review_report → END.
    Returns the final markdown report.
    """
    import json
    from pathlib import Path
    from datetime import date
    from backend.core.pipeline_runner import get_state, invoke

    state = get_state(session_id)
    if not state.get("report_sections"):
        raise HTTPException(400, "No report draft found. Run flag review first.")

    report  = state.get("report_sections", {})
    sections = report.get("report_sections", {})

    # Build final markdown with auditor edits applied
    edits    = body.edits
    company  = report.get("company_name", "")
    fy       = report.get("financial_year", "")
    opinion  = sections.get("overall_opinion_type", "unmodified").upper()

    sign_date = body.sign_date or date.today().isoformat()

    def _edited(key: str, fallback_section: dict = None) -> str:
        if key in edits:
            return edits[key]
        if fallback_section:
            return fallback_section.get("body", "")
        return ""

    md_lines = [
        "# Independent Auditor's Report",
        f"## {company}",
        f"**Financial Year Ending:** {fy}",
        f"**Opinion Type:** {opinion}",
        f"**Status:** AUDITOR-REVIEWED FINAL", "", "---", "",
    ]

    for key, label, section_key in [
        ("opinion",    "Opinion",            "opinion_section"),
        ("basis",      "Basis for Opinion",  "basis_of_opinion"),
        ("highlights", "Financial Highlights","financial_highlights"),
        ("mgmt",       "Management's Responsibility", "management_responsibility"),
        ("auditor",    "Auditor's Responsibility",    "auditor_responsibility"),
    ]:
        content = _edited(key, sections.get(section_key, {}))
        md_lines += [f"## {label}", "", content, "", "---", ""]

    # KAMs
    kam   = sections.get("key_audit_matters", {})
    items = kam.get("items", [])
    md_lines += ["## Key Audit Matters", ""]
    for i, item in enumerate(items, 1):
        md_lines += [f"### KAM {i}", "", edits.get(f"kam_{i}", item), ""]
    md_lines += ["---", ""]

    # CARO
    olr      = sections.get("report_on_other_legal_requirements", {})
    caro_obs = olr.get("caro_observations", [])
    caro_default = "\n".join(f"{i+1}. {o}" for i, o in enumerate(caro_obs))
    md_lines += [
        "## CARO 2020 Observations", "",
        edits.get("caro", caro_default), "", "---", "",
        "## Auditor Sign-off", "",
        f"**For:** {body.firm_name or '_______________'}",
        "**Chartered Accountants**",
        f"**Firm Reg. No.:** {body.firm_reg or '_______________'}", "",
        f"**Name:** {body.auditor_name or '_______________'}",
        f"**Membership No.:** {body.membership_no or '_______________'}",
        f"**Place:** {body.place or '_______________'}",
        f"**Date:** {sign_date}", "",
        "---",
        "*Generated by अर्थAI · Reviewed and approved by a qualified CA.*",
    ]

    final_md = "\n".join(md_lines)

    # Save to disk
    report_dir = BASE_DIR / "data" / "output" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{session_id}_final.md").write_text(final_md)

    # Resume graph to END
    result = invoke(
        session_id,
        update={"auditor_edits": edits, "report_finalised": True},
        as_node="human_review_report",
    )

    return {
        "current_step":   result.get("current_step"),
        "report_finalised": True,
        "report_markdown":  final_md,
        "saved_to":        f"data/output/reports/{session_id}_final.md",
    }
