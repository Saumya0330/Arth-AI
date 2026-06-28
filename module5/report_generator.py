"""
अर्थAI — Module 5: Final Report Generator

Takes the RAG-enriched JSON (Module 4 output) and generates:
  1. A structured audit report draft (ICAI format, SA 700/705 compliant)
  2. A human-editable JSON with each section as an editable field
  3. A clean markdown file the auditor can review, edit, and approve

The LLM writes the narrative — the auditor approves each section.
No number is ever altered from the source financial data.
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_MODEL  = "llama-3.3-70b-versatile"
TEMPERATURE = 0.2   # slightly more expressive for report prose


def _get_groq_client():
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not found in .env")
    return Groq(api_key=api_key)


# ── Prompt ─────────────────────────────────────────────────────────────────────

REPORT_SYSTEM_PROMPT = """You are a senior Chartered Accountant drafting an Independent Auditor's Report for an Indian company under the Companies Act 2013 and ICAI Standards on Auditing.

STRICT RULES:
1. Never alter, round, or estimate any financial figure — use only exact values from the JSON
2. Every material observation must cite the specific regulation (SA, CARO clause, Companies Act section)
3. Write in formal, professional audit language
4. If data is missing (null), note it as "could not be verified" — never invent figures
5. Structure the report exactly as specified in the schema"""

REPORT_USER_PROMPT = """Generate an Independent Auditor's Report using the following financial data.

COMPANY FINANCIAL DATA (JSON):
{financial_json}

ANOMALY FLAGS AND REGULATORY FINDINGS:
{anomaly_section}

Generate a JSON object with EXACTLY these sections (all strings):

{{
  "report_title": "Independent Auditor's Report",
  "addressee": "To the Members of [Company Name]",
  "opinion_section": {{
    "heading": "Opinion",
    "body": "Full opinion paragraph per SA 700. State clean/qualified/adverse/disclaimer. If balance sheet is unbalanced or anomalies are critical, qualify the opinion."
  }},
  "basis_of_opinion": {{
    "heading": "Basis for Opinion",
    "body": "Audit conducted per Standards on Auditing issued by ICAI. Cite SA 700, SA 705 if modified."
  }},
  "key_audit_matters": {{
    "heading": "Key Audit Matters",
    "items": ["Each anomaly flag becomes a key audit matter with: (1) description, (2) how it was addressed, (3) regulatory citation"]
  }},
  "management_responsibility": {{
    "heading": "Management's Responsibility for the Financial Statements",
    "body": "Standard paragraph per SA 700 Section 33-35."
  }},
  "auditor_responsibility": {{
    "heading": "Auditor's Responsibility",
    "body": "Standard paragraph per SA 700 Section 36-40."
  }},
  "report_on_other_legal_requirements": {{
    "heading": "Report on Other Legal and Regulatory Requirements",
    "caro_observations": ["One observation per applicable CARO 2020 clause based on the anomaly findings"],
    "other_matters": "Any other observations under Companies Act 2013."
  }},
  "financial_highlights": {{
    "heading": "Financial Highlights",
    "body": "3-4 sentence summary of key financial figures found in the data. Use exact numbers."
  }},
  "overall_opinion_type": "unmodified OR qualified OR adverse OR disclaimer_of_opinion",
  "qualification_basis": "null if unmodified, else the specific reason"
}}

Return only the JSON object."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_anomaly_section(flags: list) -> str:
    if not flags:
        return "No anomalies detected."
    lines = []
    for f in flags:
        lines.append(
            f"[{f['rule_id']} - {f['severity'].upper()}]\n"
            f"  Field: {f['field']}\n"
            f"  Issue: {f['description']}\n"
            f"  Regulation: {f.get('regulatory_response', 'N/A')[:300]}...\n"
        )
    return "\n".join(lines)


def _strip_financial_noise(fs: dict) -> dict:
    """Return only the fields the report LLM needs — keep payload small."""
    return {
        "company_name":       fs.get("company_name"),
        "cin":                fs.get("cin"),
        "financial_year_end": fs.get("financial_year_end"),
        "auditor_name":       fs.get("auditor_name"),
        "balance_sheet":      fs.get("balance_sheet"),
        "profit_and_loss":    fs.get("profit_and_loss"),
        "anomaly_summary":    fs.get("anomaly_summary"),
        "audit_observations": fs.get("audit_observations", []),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def generate_report(fs: dict) -> dict:
    """
    Generate audit report sections from the enriched financial statement.
    Returns a report dict with all sections + metadata.
    """
    client = _get_groq_client()

    financial_summary = json.dumps(_strip_financial_noise(fs), indent=2, default=str)
    anomaly_section   = _format_anomaly_section(fs.get("anomaly_flags", []))

    user_msg = REPORT_USER_PROMPT.format(
        financial_json=financial_summary,
        anomaly_section=anomaly_section,
    )

    logger.info(f"Generating audit report for: {fs.get('company_name', '?')}")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=TEMPERATURE,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    report_sections = json.loads(raw)

    return {
        "company_name":    fs.get("company_name"),
        "financial_year":  fs.get("financial_year_end"),
        "generated_by":    "अर्थAI Module 5",
        "report_sections": report_sections,
        "source_file":     fs.get("source_file"),
        "anomaly_summary": fs.get("anomaly_summary", {}),
        "status":          "DRAFT — PENDING AUDITOR REVIEW",
    }
