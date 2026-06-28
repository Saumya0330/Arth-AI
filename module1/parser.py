"""
अर्थAI — Module 1: Financial Data Parser

Takes raw extracted text from a financial PDF and maps it to the
FinancialStatement schema using regex-based heuristics tuned for
Indian Schedule III format (Companies Act 2013).

Design:
- Pure regex + pattern matching — no LLM dependency at this stage
- Every parse is best-effort: missing fields stay None, never crash
- Confidence score reflects how many key fields were successfully extracted
"""

import re
import logging
from typing import Optional

from module1.schema import (
    FinancialStatement, BalanceSheet, ProfitAndLoss,
    ShareholdersEquity, NonCurrentLiabilities, CurrentLiabilities,
    NonCurrentAssets, CurrentAssets,
)

logger = logging.getLogger(__name__)


# ── Numeric extraction helpers ─────────────────────────────────────────────────

def _parse_number(text: str) -> Optional[float]:
    """Extract first numeric value (handles Indian comma notation e.g. 1,23,456.78)."""
    text = text.replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _find_value(text: str, *patterns: str) -> Optional[float]:
    """
    Search for any of the given label patterns and return the numeric value
    found on the same line or the immediately following line.
    """
    for pattern in patterns:
        regex = re.compile(
            r"(?i)" + re.escape(pattern) + r"[^\n\d-]*([0-9,\.-]+)",
            re.IGNORECASE
        )
        m = regex.search(text)
        if m:
            val = _parse_number(m.group(1))
            if val is not None:
                return val
    return None


# ── Identity fields ────────────────────────────────────────────────────────────

def _extract_company_name(text: str) -> Optional[str]:
    patterns = [
        r"(?i)(?:name of company|company name)[:\s]+([A-Z][^\n]{3,80})",
        r"(?i)([A-Z][A-Z\s&.,()]{5,60}(?:LIMITED|LTD|PRIVATE|PVT)\.?)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None


def _extract_cin(text: str) -> Optional[str]:
    m = re.search(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b", text)
    return m.group(1) if m else None


def _extract_financial_year(text: str) -> Optional[str]:
    # Match "31st March, 2023" or "March 31, 2023" or "31-03-2023"
    patterns = [
        r"(?:31st?\s+March|March\s+31)[,\s]+(\d{4})",
        r"31[-/]03[-/](\d{4})",
        r"year\s+ended[^\n]*?(\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            year = m.group(1)
            return f"{year}-03-31"
    return None


def _extract_auditor(text: str) -> Optional[str]:
    m = re.search(
        r"(?i)(?:for\s+)?([A-Z][A-Za-z\s&.,]{3,50}(?:CO\.?|COMPANY|ASSOCIATES|LLP|PARTNERS)?)\s*"
        r"(?:chartered accountants?|firm reg)",
        text
    )
    return m.group(1).strip() if m else None


# ── Balance Sheet ──────────────────────────────────────────────────────────────

def _parse_balance_sheet(text: str) -> BalanceSheet:
    bs = BalanceSheet()

    bs.shareholders_equity = ShareholdersEquity(
        share_capital=_find_value(text, "share capital", "paid-up capital", "paid up capital"),
        reserves_and_surplus=_find_value(text, "reserves and surplus", "reserves & surplus"),
        money_received_against_share_warrants=_find_value(text, "share warrants"),
    )

    bs.non_current_liabilities = NonCurrentLiabilities(
        long_term_borrowings=_find_value(text, "long-term borrowings", "long term borrowings"),
        deferred_tax_liabilities=_find_value(text, "deferred tax liabilities", "deferred tax liability"),
        other_long_term_liabilities=_find_value(text, "other long-term liabilities", "other long term liabilities"),
        long_term_provisions=_find_value(text, "long-term provisions", "long term provisions"),
    )

    bs.current_liabilities = CurrentLiabilities(
        short_term_borrowings=_find_value(text, "short-term borrowings", "short term borrowings"),
        trade_payables=_find_value(text, "trade payables", "sundry creditors"),
        other_current_liabilities=_find_value(text, "other current liabilities"),
        short_term_provisions=_find_value(text, "short-term provisions", "short term provisions"),
    )

    bs.non_current_assets = NonCurrentAssets(
        fixed_assets_tangible=_find_value(text, "tangible assets", "property, plant", "fixed assets"),
        fixed_assets_intangible=_find_value(text, "intangible assets"),
        capital_wip=_find_value(text, "capital work-in-progress", "capital wip", "cwip"),
        long_term_investments=_find_value(text, "non-current investments", "long-term investments"),
        deferred_tax_assets=_find_value(text, "deferred tax assets"),
        long_term_loans_and_advances=_find_value(text, "long-term loans and advances"),
        other_non_current_assets=_find_value(text, "other non-current assets"),
    )

    bs.current_assets = CurrentAssets(
        inventories=_find_value(text, "inventories", "stock-in-trade"),
        trade_receivables=_find_value(text, "trade receivables", "sundry debtors"),
        cash_and_cash_equivalents=_find_value(text, "cash and cash equivalents", "cash and bank"),
        short_term_loans_and_advances=_find_value(text, "short-term loans and advances"),
        other_current_assets=_find_value(text, "other current assets"),
    )

    return bs


# ── Profit & Loss ──────────────────────────────────────────────────────────────

def _parse_profit_and_loss(text: str) -> ProfitAndLoss:
    return ProfitAndLoss(
        revenue_from_operations=_find_value(
            text, "revenue from operations", "net revenue", "turnover"),
        other_income=_find_value(text, "other income"),
        cost_of_materials=_find_value(
            text, "cost of materials consumed", "cost of goods sold",
            "purchases of stock-in-trade"),
        employee_benefits_expense=_find_value(
            text, "employee benefits expense", "staff costs", "salaries and wages"),
        finance_costs=_find_value(text, "finance costs", "interest expense"),
        depreciation=_find_value(
            text, "depreciation and amortization", "depreciation & amortization",
            "depreciation"),
        other_expenses=_find_value(text, "other expenses"),
        exceptional_items=_find_value(text, "exceptional items"),
        tax_expense=_find_value(text, "tax expense", "income tax expense", "current tax"),
        profit_after_tax=_find_value(
            text, "profit for the year", "profit after tax", "net profit"),
    )


# ── Confidence scoring ─────────────────────────────────────────────────────────

def _compute_confidence(fs: FinancialStatement) -> float:
    """
    Fraction of key financial fields successfully extracted.
    Key fields = 10 most important values for audit purposes.
    """
    key_vals = [
        fs.company_name,
        fs.financial_year_end,
        fs.balance_sheet.shareholders_equity.share_capital,
        fs.balance_sheet.shareholders_equity.reserves_and_surplus,
        fs.balance_sheet.current_liabilities.trade_payables,
        fs.balance_sheet.current_assets.cash_and_cash_equivalents,
        fs.balance_sheet.current_assets.trade_receivables,
        fs.profit_and_loss.revenue_from_operations,
        fs.profit_and_loss.profit_after_tax,
        fs.profit_and_loss.employee_benefits_expense,
    ]
    filled = sum(1 for v in key_vals if v is not None)
    return round(filled / len(key_vals), 2)


# ── Main entry point ───────────────────────────────────────────────────────────

def parse_financial_text(
    raw_text: str,
    source_file: str = "",
    extraction_method: str = "text",
) -> FinancialStatement:
    """
    Parse raw extracted text into a FinancialStatement object.
    Never raises — missing fields remain None.
    """
    fs = FinancialStatement(
        company_name=_extract_company_name(raw_text),
        cin=_extract_cin(raw_text),
        financial_year_end=_extract_financial_year(raw_text),
        auditor_name=_extract_auditor(raw_text),
        source_file=source_file,
        extraction_method=extraction_method,
        balance_sheet=_parse_balance_sheet(raw_text),
        profit_and_loss=_parse_profit_and_loss(raw_text),
    )
    fs.extraction_confidence = _compute_confidence(fs)
    return fs


def _build_sources(fs) -> dict:
    """
    Build a flat _sources dict: dotted field path → 'regex' for every
    non-null value the regex parser extracted.
    """
    sources = {}
    for field in ("company_name", "cin", "financial_year_end", "auditor_name"):
        if getattr(fs, field) is not None:
            sources[field] = "regex"
    bs = fs.balance_sheet
    for section_name, section_obj in [
        ("balance_sheet.shareholders_equity",     bs.shareholders_equity),
        ("balance_sheet.non_current_liabilities", bs.non_current_liabilities),
        ("balance_sheet.current_liabilities",     bs.current_liabilities),
        ("balance_sheet.non_current_assets",      bs.non_current_assets),
        ("balance_sheet.current_assets",          bs.current_assets),
    ]:
        for k, v in vars(section_obj).items():
            if isinstance(v, (int, float)):
                sources[f"{section_name}.{k}"] = "regex"
    for k, v in vars(fs.profit_and_loss).items():
        if isinstance(v, (int, float)):
            sources[f"profit_and_loss.{k}"] = "regex"
    return sources


def attach_sources(fs_dict: dict) -> dict:
    """
    Given a Module 1 output dict, add a top-level '_sources' key.
    Maps dotted field paths → 'regex' for every value extracted by regex.
    """
    from module1.schema import FinancialStatement
    fs = FinancialStatement.from_dict({k: v for k, v in fs_dict.items()})
    fs_dict["_sources"] = _build_sources(fs)
    return fs_dict
