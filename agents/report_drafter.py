"""
अर्थAI — Agent 4: Report Drafter

Receives financial JSON + cited flags + field_sources.
Source-aware: LLM-filled numbers are marked [UNVERIFIED] in the report
so the auditor knows which figures need manual confirmation.
Knows nothing about math_validator or compliance_checker internals.
"""

import logging
from agents.state import AuditState

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "regex":             "regex-extracted",
    "llm":               "LLM-extracted — unverified",
    "auditor_verified":  "auditor-verified",
}


def _annotate_unverified(fs: dict, sources: dict) -> dict:
    """
    Walk the financial JSON and attach a '_verification_warnings' list
    that tells the report generator which fields need auditor confirmation.
    Only LLM-sourced numeric fields are flagged — regex and verified are trusted.
    """
    warnings = []
    for path, source in sources.items():
        if source == "llm":
            warnings.append(
                f"Field '{path}' was extracted by LLM and has NOT been "
                f"verified against the source document."
            )
    fs["_verification_warnings"] = warnings
    return fs


def run_report_drafter(state: AuditState) -> AuditState:
    """
    Agent 4 node function.
    Reads: financial_json, flags_with_citations, field_sources, math_report.
    Writes: report_sections, report_markdown.
    """
    from module5.report_generator import generate_report
    from module5.renderer import render_markdown

    sources = state.get("field_sources") or {}
    llm_field_count = sum(1 for s in sources.values() if s == "llm")
    regex_field_count = sum(1 for s in sources.values() if s == "regex")

    logger.info(
        f"[ReportDrafter] Field sources: "
        f"{regex_field_count} regex-verified, {llm_field_count} LLM-extracted"
    )

    fs = _annotate_unverified(
        {
            **state["financial_json"],
            "anomaly_flags":   state.get("flags_with_citations") or [],
            "anomaly_summary": {
                "total":    len(state.get("flags_with_citations") or []),
                "critical": sum(1 for f in (state.get("flags_with_citations") or [])
                                if f.get("severity") == "critical"),
                "warning":  sum(1 for f in (state.get("flags_with_citations") or [])
                                if f.get("severity") == "warning"),
                "info": 0,
            },
        },
        sources,
    )

    # Inject math failures and LLM field warnings as audit observations
    extra_obs = list(fs.get("audit_observations") or [])

    math = state.get("math_report", {})
    for cf in math.get("critical_failures", []):
        extra_obs.append(
            f"⚠️ Arithmetic error: {cf['check']} — "
            f"expected {cf['expected']}, found {cf['actual']} (diff {cf['difference']})"
        )

    if llm_field_count > 0:
        extra_obs.append(
            f"⚠️ {llm_field_count} financial field(s) were extracted by LLM and "
            f"require auditor verification against the source document before "
            f"this report is finalised."
        )

    fs["audit_observations"] = extra_obs

    logger.info(f"[ReportDrafter] Drafting report for {fs.get('company_name', '?')}")
    report = generate_report(fs)
    md = render_markdown(report)

    return {
        **state,
        "report_sections":  report,
        "report_markdown":  md,
        "current_step":     "report_drafted",
    }
