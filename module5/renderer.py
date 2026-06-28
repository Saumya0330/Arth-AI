"""
अर्थAI — Module 5: Markdown Report Renderer

Converts the structured report JSON into a clean, readable
markdown file that the auditor can open, edit, and approve.

Each section is clearly delimited with [AUDITOR: REVIEW REQUIRED]
markers so nothing slips through unreviewed.
"""

from pathlib import Path
from datetime import date


def render_markdown(report: dict) -> str:
    s = report.get("report_sections", {})
    company = report.get("company_name", "Unknown Company")
    fy      = report.get("financial_year", "Unknown Year")
    summary = report.get("anomaly_summary", {})

    opinion_type = s.get("overall_opinion_type", "unmodified").upper()
    opinion_badge = {
        "UNMODIFIED":           "✅ UNMODIFIED",
        "QUALIFIED":            "⚠️  QUALIFIED",
        "ADVERSE":              "🔴 ADVERSE",
        "DISCLAIMER_OF_OPINION":"🔴 DISCLAIMER OF OPINION",
    }.get(opinion_type, opinion_type)

    lines = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# " + s.get('report_title', "Independent Auditor's Report"),
        f"## {company}",
        f"**Financial Year Ending:** {fy}  ",
        f"**Opinion Type:** {opinion_badge}  ",
        f"**Generated:** {date.today().isoformat()}  ",
        f"**Status:** `{report.get('status', 'DRAFT')}`",
        "",
        "---",
        "",
        "> ⚠️  **This is an AI-generated draft. Every section marked**",
        "> **`[AUDITOR: REVIEW REQUIRED]` must be verified and approved**",
        "> **before this report is finalised.**",
        "",
        "---",
        "",
    ]

    # ── Anomaly summary banner ─────────────────────────────────────────────
    if summary:
        lines += [
            "## 🔍 Anomaly Detection Summary",
            "",
            f"| Severity | Count |",
            f"|----------|-------|",
            f"| 🔴 Critical | {summary.get('critical', 0)} |",
            f"| 🟡 Warning  | {summary.get('warning', 0)} |",
            f"| 🔵 Info     | {summary.get('info', 0)} |",
            f"| **Total**   | **{summary.get('total', 0)}** |",
            "",
            "---",
            "",
        ]

    # ── Addressee ──────────────────────────────────────────────────────────
    lines += [
        s.get("addressee", f"To the Members of {company}"),
        "",
    ]

    # ── Report sections ────────────────────────────────────────────────────
    def _section(heading: str, body: str):
        lines.extend([
            f"## {heading}",
            "",
            "`[AUDITOR: REVIEW REQUIRED]`",
            "",
            body,
            "",
            "---",
            "",
        ])

    # Opinion
    op = s.get("opinion_section", {})
    _section(op.get("heading", "Opinion"), op.get("body", ""))

    # Qualification basis (if any)
    qual = s.get("qualification_basis")
    if qual and qual != "null":
        lines += [
            "## Basis for Qualification / Modification",
            "",
            "`[AUDITOR: REVIEW REQUIRED]`",
            "",
            qual,
            "",
            "---",
            "",
        ]

    # Basis of opinion
    boo = s.get("basis_of_opinion", {})
    _section(boo.get("heading", "Basis for Opinion"), boo.get("body", ""))

    # Key Audit Matters
    kam = s.get("key_audit_matters", {})
    lines += [
        f"## {kam.get('heading', 'Key Audit Matters')}",
        "",
        "`[AUDITOR: REVIEW REQUIRED]`",
        "",
    ]
    for i, item in enumerate(kam.get("items", []), 1):
        lines += [f"### KAM {i}", "", item, ""]
    lines += ["---", ""]

    # Financial highlights
    fh = s.get("financial_highlights", {})
    _section(fh.get("heading", "Financial Highlights"), fh.get("body", ""))

    # Management responsibility
    mr = s.get("management_responsibility", {})
    _section(mr.get("heading", "Management's Responsibility"), mr.get("body", ""))

    # Auditor responsibility
    ar = s.get("auditor_responsibility", {})
    _section(ar.get("heading", "Auditor's Responsibility"), ar.get("body", ""))

    # CARO / Legal requirements
    olr = s.get("report_on_other_legal_requirements", {})
    lines += [
        f"## {olr.get('heading', 'Report on Other Legal and Regulatory Requirements')}",
        "",
        "`[AUDITOR: REVIEW REQUIRED]`",
        "",
        "### CARO 2020 Observations",
        "",
    ]
    for i, obs in enumerate(olr.get("caro_observations", []), 1):
        lines.append(f"{i}. {obs}")
    lines += [
        "",
        "### Other Matters",
        "",
        olr.get("other_matters", ""),
        "",
        "---",
        "",
    ]

    # ── Footer ─────────────────────────────────────────────────────────────
    lines += [
        "## Auditor Sign-off",
        "",
        "`[AUDITOR: COMPLETE BEFORE FINALISING]`",
        "",
        "**For:** ___________________________  ",
        "**Chartered Accountants**  ",
        "**Firm Reg. No.:** _______________  ",
        "",
        "**Name:** _______________________  ",
        "**Membership No.:** ______________  ",
        "**Place:** ______________________  ",
        f"**Date:** {date.today().isoformat()}  ",
        "",
        "---",
        "",
        "*Generated by अर्थAI — AI-Augmented Financial Audit System*  ",
        "*This draft must be reviewed and approved by a qualified CA before use.*",
    ]

    return "\n".join(lines)
