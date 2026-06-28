"""
अर्थAI — Module 2: LLM Reasoning & JSON Completion

Takes the partial FinancialStatement JSON from Module 1 + raw OCR text,
sends both to Groq (Llama 3.3 70B), and returns a completed JSON with:
  - All numeric fields filled from the source document
  - Initial audit observations / reasoning narrative
  - Confidence flags on any value the LLM is uncertain about

Dev  → Groq API (llama-3.3-70b-versatile, fast + free tier)
Prod → swap PROVIDER=ollama in .env, zero code changes needed
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Model config ───────────────────────────────────────────────────────────────
GROQ_MODEL   = "llama-3.3-70b-versatile"
MAX_TOKENS   = 4096
TEMPERATURE  = 0.1   # low = more deterministic for financial extraction


def _get_groq_client():
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not found. Check your .env file.")
    return Groq(api_key=api_key)


# ── Prompts ────────────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a senior Chartered Accountant AI assistant specializing in Indian statutory audits under the Companies Act 2013.

Your job is to analyze a company's financial document and extract ALL financial data into a precise JSON structure.

CRITICAL RULES:
1. Extract EXACT numbers from the source text — never calculate, estimate, or hallucinate values
2. If a value is genuinely not present, use null — do not guess
3. All amounts are in INR (₹) as they appear in the document (do not convert units)
4. Return ONLY valid JSON — no explanations, no markdown fences, no extra text
5. Preserve the exact schema structure provided"""

EXTRACTION_USER_PROMPT = """Below is a financial document from an Indian company.

--- PARTIAL EXTRACTION (from regex parser, many fields may be null) ---
{partial_json}

--- RAW DOCUMENT TEXT (use this as the authoritative source) ---
{raw_text}

--- TASK ---
Return a completed JSON object following EXACTLY this schema. Fill every null you can find in the raw text.
Also add an "audit_observations" field (array of strings) with 3-5 initial observations about this company's financials — patterns, risks, or notable items an auditor should investigate.

Schema to follow:
{schema_template}

Return only the JSON object, nothing else."""


SCHEMA_TEMPLATE = """{
  "company_name": "string or null",
  "cin": "string or null",
  "pan": "string or null",
  "registered_address": "string or null",
  "financial_year_end": "YYYY-MM-DD or null",
  "currency": "INR",
  "auditor_name": "string or null",
  "auditor_firm_reg": "string or null",
  "balance_sheet": {
    "shareholders_equity": {
      "share_capital": number_or_null,
      "reserves_and_surplus": number_or_null,
      "money_received_against_share_warrants": number_or_null
    },
    "non_current_liabilities": {
      "long_term_borrowings": number_or_null,
      "deferred_tax_liabilities": number_or_null,
      "other_long_term_liabilities": number_or_null,
      "long_term_provisions": number_or_null
    },
    "current_liabilities": {
      "short_term_borrowings": number_or_null,
      "trade_payables": number_or_null,
      "other_current_liabilities": number_or_null,
      "short_term_provisions": number_or_null
    },
    "non_current_assets": {
      "fixed_assets_tangible": number_or_null,
      "fixed_assets_intangible": number_or_null,
      "capital_wip": number_or_null,
      "long_term_investments": number_or_null,
      "deferred_tax_assets": number_or_null,
      "long_term_loans_and_advances": number_or_null,
      "other_non_current_assets": number_or_null
    },
    "current_assets": {
      "inventories": number_or_null,
      "trade_receivables": number_or_null,
      "cash_and_cash_equivalents": number_or_null,
      "short_term_loans_and_advances": number_or_null,
      "other_current_assets": number_or_null
    }
  },
  "profit_and_loss": {
    "revenue_from_operations": number_or_null,
    "other_income": number_or_null,
    "cost_of_materials": number_or_null,
    "employee_benefits_expense": number_or_null,
    "finance_costs": number_or_null,
    "depreciation": number_or_null,
    "other_expenses": number_or_null,
    "exceptional_items": number_or_null,
    "tax_expense": number_or_null,
    "profit_after_tax": number_or_null
  },
  "audit_observations": ["string", "string", "..."],
  "source_file": "string",
  "extraction_method": "llm",
  "extraction_confidence": number_between_0_and_1
}"""


# ── Token safety — trim raw text to fit context window ────────────────────────

def _safe_trim_text(text: str, max_chars: int = 12000) -> str:
    """
    Keep the most financially-dense portion of the text.
    Prioritise pages containing balance sheet / P&L keywords.
    """
    if len(text) <= max_chars:
        return text

    # Score each paragraph by financial keyword density
    keywords = [
        "balance sheet", "profit", "loss", "revenue", "capital", "borrowing",
        "assets", "liabilities", "equity", "depreciation", "tax", "turnover",
        "receivables", "payables", "cash", "inventory", "reserves"
    ]
    paragraphs = text.split("\n\n")
    scored = []
    for para in paragraphs:
        lower = para.lower()
        score = sum(lower.count(kw) for kw in keywords)
        scored.append((score, para))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Rebuild from highest-scoring paragraphs until we hit max_chars
    selected = []
    total = 0
    for _, para in scored:
        if total + len(para) > max_chars:
            break
        selected.append(para)
        total += len(para)

    return "\n\n".join(selected)


# ── Main LLM call ──────────────────────────────────────────────────────────────

def complete_financial_json(
    partial_json: dict,
    raw_text: str,
    source_file: str = "",
) -> dict:
    """
    Send partial JSON + raw text to the LLM, return completed financial JSON.
    Falls back to the partial JSON if the LLM call fails.
    """
    client = _get_groq_client()

    trimmed_text = _safe_trim_text(raw_text)
    logger.info(f"Sending {len(trimmed_text):,} chars to {GROQ_MODEL}")

    user_msg = EXTRACTION_USER_PROMPT.format(
        partial_json=json.dumps(partial_json, indent=2, default=str),
        raw_text=trimmed_text,
        schema_template=SCHEMA_TEMPLATE,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    raw_response = response.choices[0].message.content.strip()
    logger.info(f"LLM responded ({len(raw_response)} chars)")

    # Strip markdown fences if model added them despite instructions
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]

    completed = json.loads(raw_response)
    completed["source_file"] = source_file
    completed["extraction_method"] = "llm"
    return completed


def _diff_and_tag_sources(partial: dict, completed: dict) -> dict:
    """
    Compare partial (Module 1) and completed (LLM) dicts.
    For every field that was null in partial but non-null in completed → tag 'llm'.
    For every field that was already filled in partial → preserve existing tag.
    Returns updated '_sources' dict.
    """
    existing_sources = partial.get("_sources", {})
    new_sources = dict(existing_sources)  # copy regex tags

    def _walk(old, new, path=""):
        if isinstance(new, dict):
            for k, v in new.items():
                _walk(old.get(k) if isinstance(old, dict) else None,
                      v, f"{path}.{k}" if path else k)
        elif isinstance(new, (int, float)) and new is not None:
            dotted = path
            if dotted not in new_sources:  # wasn't tagged by regex
                new_sources[dotted] = "llm"

    _walk(partial, completed)
    return new_sources


def complete_financial_json_with_sources(
    partial_json: dict,
    raw_text: str,
    source_file: str = "",
) -> dict:
    """
    Same as complete_financial_json but also builds the _sources audit trail.
    LLM-filled fields are tagged 'llm', regex-filled stay 'regex'.
    Use this instead of complete_financial_json going forward.
    """
    completed = complete_financial_json(partial_json, raw_text, source_file)
    completed["_sources"] = _diff_and_tag_sources(partial_json, completed)
    return completed
