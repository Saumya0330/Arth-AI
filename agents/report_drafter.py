"""
अर्थAI — Agent 4: Report Drafter

Receives the financial JSON + cited flags.
Generates structured audit report sections.
Knows nothing about math checks or how flags were detected.
Context window is clean — only gets what it needs to write the report.
"""

import logging
from agents.state import AuditState

logger = logging.getLogger(__name__)


def run_report_drafter(state: AuditState) -> AuditState:
    """
    Agent 4 node function.
    Reads state["financial_json"] + state["flags_with_citations"].
    Writes state["report_sections"] + state["report_markdown"].
    """
    from module5.report_generator import generate_report
    from module5.renderer import render_markdown

    # Build an enriched fs dict with only what the report needs
    fs = {
        **state["financial_json"],
        "anomaly_flags":   state.get("flags_with_citations") or [],
        "anomaly_summary": {
            "total":    len(state.get("flags_with_citations") or []),
            "critical": sum(1 for f in (state.get("flags_with_citations") or [])
                            if f.get("severity") == "critical"),
            "warning":  sum(1 for f in (state.get("flags_with_citations") or [])
                            if f.get("severity") == "warning"),
            "info":     0,
        },
    }

    # Also inject math report as an additional observation for the LLM
    math = state.get("math_report", {})
    if math.get("has_critical_errors"):
        critical_checks = math.get("critical_failures", [])
        math_obs = [
            f"Math validation failed: {c['check']} "
            f"(expected {c['expected']}, got {c['actual']}, diff {c['difference']})"
            for c in critical_checks
        ]
        existing_obs = fs.get("audit_observations") or []
        fs["audit_observations"] = existing_obs + math_obs

    logger.info(f"[ReportDrafter] Generating report for {fs.get('company_name', '?')}")
    report = generate_report(fs)
    md     = render_markdown(report)

    return {
        **state,
        "report_sections": report,
        "report_markdown": md,
        "current_step": "report_drafted",
    }
