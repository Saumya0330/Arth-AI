"""
अर्थAI — Agent 2: Compliance Checker

Runs all rule-based anomaly checks from module3.
Receives financial_json, knows nothing about math_report or any other agent.
Returns a flat list of anomaly flags for auditor review.
"""

import logging
from agents.state import AuditState

logger = logging.getLogger(__name__)


def run_compliance_checker(state: AuditState) -> AuditState:
    """
    Agent 2 node function.
    Reads state["financial_json"], writes state["anomaly_flags"].
    Isolated — no knowledge of math_validator output.
    """
    from module3.anomaly import run_all_checks

    fs    = state["financial_json"]
    flags = run_all_checks(fs)

    critical = [f for f in flags if f["severity"] == "critical"]
    warnings = [f for f in flags if f["severity"] == "warning"]

    logger.info(
        f"[ComplianceChecker] {len(flags)} flags: "
        f"{len(critical)} critical, {len(warnings)} warnings"
    )

    return {
        **state,
        "anomaly_flags": flags,
        "current_step": "compliance_checked",
    }
