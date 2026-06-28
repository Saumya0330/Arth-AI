"""
अर्थAI — Module 3: Anomaly Detection & Calculation Validation

Every flag raised here is traceable to either:
  (a) A mathematical rule  — e.g. Balance Sheet must balance
  (b) A financial ratio    — e.g. Current Ratio < 1 signals liquidity risk
  (c) Benford's Law        — first-digit distribution for fraud detection
  (d) A statutory rule     — e.g. CARO 2020 / Companies Act thresholds

Output: a list of AnomalyFlag objects, each with:
  - rule_id      : unique identifier (used by Module 4 RAG to fetch regulation)
  - severity     : "critical" | "warning" | "info"
  - field        : which JSON field triggered it
  - expected     : what was expected
  - actual       : what was found
  - description  : plain-English explanation for the auditor
"""

import math
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Anomaly Flag ───────────────────────────────────────────────────────────────

@dataclass
class AnomalyFlag:
    rule_id: str
    severity: str          # "critical" | "warning" | "info"
    field: str
    description: str
    expected: Optional[str] = None
    actual: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── Helper: safe division ──────────────────────────────────────────────────────

def _safe_div(a, b) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 4)


def _val(d: dict, *keys) -> Optional[float]:
    """Drill into nested dict safely."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d if isinstance(d, (int, float)) else None


def _sum_section(section: dict) -> Optional[float]:
    vals = [v for v in section.values() if isinstance(v, (int, float))]
    return round(sum(vals), 2) if vals else None


# ── Rule set ───────────────────────────────────────────────────────────────────

def check_balance_sheet_equation(fs: dict) -> list:
    """
    RULE BS-001: Assets = Equity + Liabilities
    Source: Schedule III, Companies Act 2013
    """
    flags = []
    bs = fs.get("balance_sheet", {})

    eq  = _sum_section(bs.get("shareholders_equity", {}))
    ncl = _sum_section(bs.get("non_current_liabilities", {}))
    cl  = _sum_section(bs.get("current_liabilities", {}))
    nca = _sum_section(bs.get("non_current_assets", {}))
    ca  = _sum_section(bs.get("current_assets", {}))

    if None in (eq, cl, nca, ca):
        return flags  # insufficient data

    total_equity_liab = round((eq or 0) + (ncl or 0) + (cl or 0), 2)
    total_assets = round((nca or 0) + (ca or 0), 2)
    diff = abs(total_equity_liab - total_assets)

    if diff > 1:
        flags.append(AnomalyFlag(
            rule_id="BS-001",
            severity="critical",
            field="balance_sheet",
            description=f"Balance sheet does not balance. "
                        f"Equity+Liabilities = {total_equity_liab:,.2f}, "
                        f"Assets = {total_assets:,.2f}, Difference = {diff:,.2f}",
            expected="Equity + Liabilities == Total Assets",
            actual=f"Difference of {diff:,.2f}",
        ))
    return flags


def check_liquidity_ratios(fs: dict) -> list:
    """
    RULE LR-001: Current Ratio = Current Assets / Current Liabilities
      < 1.0  → critical (cannot meet short-term obligations)
      1.0–1.5 → warning
    RULE LR-002: Cash Ratio = Cash / Current Liabilities
      < 0.1  → warning (very low cash cushion)
    """
    flags = []
    bs = fs.get("balance_sheet", {})
    ca_section = bs.get("current_assets", {})
    cl_section = bs.get("current_liabilities", {})

    total_ca = _sum_section(ca_section)
    total_cl = _sum_section(cl_section)
    current_ratio = _safe_div(total_ca, total_cl)

    if current_ratio is not None:
        if current_ratio < 1.0:
            flags.append(AnomalyFlag(
                rule_id="LR-001",
                severity="critical",
                field="balance_sheet.current_assets / current_liabilities",
                description=f"Current Ratio is {current_ratio:.2f} (< 1.0). "
                            f"Company may be unable to meet short-term obligations. "
                            f"Auditor should assess going concern.",
                expected=">= 1.0",
                actual=str(current_ratio),
            ))
        elif current_ratio < 1.5:
            flags.append(AnomalyFlag(
                rule_id="LR-001",
                severity="warning",
                field="balance_sheet.current_assets / current_liabilities",
                description=f"Current Ratio is {current_ratio:.2f} (low). "
                            f"Short-term liquidity may be strained.",
                expected=">= 1.5",
                actual=str(current_ratio),
            ))

    cash = _val(bs, "current_assets", "cash_and_cash_equivalents")
    cash_ratio = _safe_div(cash, total_cl)
    if cash_ratio is not None and cash_ratio < 0.1:
        flags.append(AnomalyFlag(
            rule_id="LR-002",
            severity="warning",
            field="balance_sheet.current_assets.cash_and_cash_equivalents",
            description=f"Cash Ratio is {cash_ratio:.3f} (< 0.1). "
                        f"Very low immediate cash cover for current liabilities.",
            expected=">= 0.1",
            actual=str(cash_ratio),
        ))
    return flags


def check_profitability(fs: dict) -> list:
    """
    RULE PR-001: Net Profit Margin = PAT / Revenue
      < 0    → critical (loss-making)
      0–5%   → warning
    RULE PR-002: Revenue present but PAT null → extraction gap flagged
    """
    flags = []
    pl = fs.get("profit_and_loss", {})
    revenue = pl.get("revenue_from_operations")
    pat = pl.get("profit_after_tax")

    if revenue and pat is not None:
        margin = _safe_div(pat, revenue)
        if margin is not None:
            if margin < 0:
                flags.append(AnomalyFlag(
                    rule_id="PR-001",
                    severity="critical",
                    field="profit_and_loss.profit_after_tax",
                    description=f"Company is loss-making. Net margin = {margin*100:.2f}%. "
                                f"Auditor must assess going concern and accumulated losses.",
                    expected=">= 0",
                    actual=f"{margin*100:.2f}%",
                ))
            elif margin < 0.05:
                flags.append(AnomalyFlag(
                    rule_id="PR-001",
                    severity="warning",
                    field="profit_and_loss.profit_after_tax",
                    description=f"Net profit margin is very thin at {margin*100:.2f}%. "
                                f"Vulnerable to cost increases.",
                    expected=">= 5%",
                    actual=f"{margin*100:.2f}%",
                ))
    elif revenue and pat is None:
        flags.append(AnomalyFlag(
            rule_id="PR-002",
            severity="warning",
            field="profit_and_loss.profit_after_tax",
            description="Revenue is present but Profit After Tax could not be extracted. "
                        "Manual verification required.",
            expected="Numeric value",
            actual="null",
        ))
    return flags


def check_debt_metrics(fs: dict) -> list:
    """
    RULE DT-001: Debt-to-Equity = Total Borrowings / Shareholders Equity
      > 2.0  → warning
      > 4.0  → critical
    RULE DT-002: Finance costs present but borrowings null → flag inconsistency
    """
    flags = []
    bs = fs.get("balance_sheet", {})
    pl = fs.get("profit_and_loss", {})

    lt_borrow = _val(bs, "non_current_liabilities", "long_term_borrowings") or 0
    st_borrow = _val(bs, "current_liabilities", "short_term_borrowings") or 0
    total_debt = lt_borrow + st_borrow

    eq_section = bs.get("shareholders_equity", {})
    equity = _sum_section(eq_section)

    de_ratio = _safe_div(total_debt, equity)
    if de_ratio is not None:
        if de_ratio > 4.0:
            flags.append(AnomalyFlag(
                rule_id="DT-001",
                severity="critical",
                field="balance_sheet.non_current_liabilities.long_term_borrowings",
                description=f"Debt-to-Equity ratio is {de_ratio:.2f} (> 4.0). "
                            f"Highly leveraged. Lenders may impose restrictive covenants.",
                expected="<= 2.0",
                actual=str(de_ratio),
            ))
        elif de_ratio > 2.0:
            flags.append(AnomalyFlag(
                rule_id="DT-001",
                severity="warning",
                field="balance_sheet.non_current_liabilities.long_term_borrowings",
                description=f"Debt-to-Equity ratio is {de_ratio:.2f} (> 2.0). Elevated leverage.",
                expected="<= 2.0",
                actual=str(de_ratio),
            ))

    finance_costs = pl.get("finance_costs")
    if finance_costs and finance_costs > 0 and total_debt == 0:
        flags.append(AnomalyFlag(
            rule_id="DT-002",
            severity="warning",
            field="profit_and_loss.finance_costs",
            description=f"Finance costs of {finance_costs:,.2f} are reported but no borrowings "
                        f"were extracted. Off-balance-sheet debt or extraction gap.",
            expected="Corresponding borrowings on balance sheet",
            actual="Borrowings = null/0",
        ))
    return flags


def check_benford_law(fs: dict) -> list:
    """
    RULE BF-001: Benford's Law first-digit test.
    Collect all numeric values > 0 from the financial statement,
    check if the distribution of first digits significantly deviates
    from the expected Benford distribution.
    Deviation > 0.15 MAD → warning (potential data manipulation).

    Source: Nigrini (2017) — Audit Sampling Using Benford's Law
    """
    flags = []

    def _collect_numbers(obj):
        nums = []
        if isinstance(obj, dict):
            for v in obj.values():
                nums.extend(_collect_numbers(v))
        elif isinstance(obj, (int, float)) and obj > 0:
            nums.append(obj)
        return nums

    numbers = _collect_numbers(fs.get("balance_sheet", {}))
    numbers += _collect_numbers(fs.get("profit_and_loss", {}))

    if len(numbers) < 10:
        return flags  # not enough data for Benford test

    # Expected Benford probabilities for digits 1-9
    benford_expected = {d: math.log10(1 + 1/d) for d in range(1, 10)}

    first_digits = []
    for n in numbers:
        first = int(str(abs(n)).replace(".", "").lstrip("0")[0])
        if 1 <= first <= 9:
            first_digits.append(first)

    if not first_digits:
        return flags

    total = len(first_digits)
    observed = {d: first_digits.count(d) / total for d in range(1, 10)}

    # Mean Absolute Deviation
    mad = sum(abs(observed.get(d, 0) - benford_expected[d]) for d in range(1, 10)) / 9

    if mad > 0.15:
        flags.append(AnomalyFlag(
            rule_id="BF-001",
            severity="warning",
            field="balance_sheet + profit_and_loss (all numeric values)",
            description=f"Benford's Law test: MAD = {mad:.4f} (threshold 0.15). "
                        f"First-digit distribution deviates from expected. "
                        f"May indicate data manipulation or rounding. "
                        f"Sample size: {total} values.",
            expected="MAD <= 0.15",
            actual=f"MAD = {mad:.4f}",
        ))
    return flags


def check_employee_costs(fs: dict) -> list:
    """
    RULE EC-001: Employee costs > 60% of revenue → unusual for most industries.
    """
    flags = []
    pl = fs.get("profit_and_loss", {})
    revenue = pl.get("revenue_from_operations")
    emp_cost = pl.get("employee_benefits_expense")

    ratio = _safe_div(emp_cost, revenue)
    if ratio is not None and ratio > 0.60:
        flags.append(AnomalyFlag(
            rule_id="EC-001",
            severity="warning",
            field="profit_and_loss.employee_benefits_expense",
            description=f"Employee costs are {ratio*100:.1f}% of revenue — unusually high. "
                        f"Verify headcount, compensation structure, and related-party payments.",
            expected="<= 60% of revenue",
            actual=f"{ratio*100:.1f}%",
        ))
    return flags


# ── Master runner ──────────────────────────────────────────────────────────────

ALL_CHECKS = [
    check_balance_sheet_equation,
    check_liquidity_ratios,
    check_profitability,
    check_debt_metrics,
    check_benford_law,
    check_employee_costs,
]


def run_all_checks(fs: dict) -> list:
    """
    Run all anomaly checks on a FinancialStatement dict.
    Returns a list of AnomalyFlag dicts, sorted by severity.
    """
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_flags = []

    for check_fn in ALL_CHECKS:
        try:
            flags = check_fn(fs)
            all_flags.extend(flags)
            if flags:
                for f in flags:
                    logger.info(f"  [{f.severity.upper()}] {f.rule_id}: {f.description[:80]}...")
        except Exception as e:
            logger.warning(f"Check {check_fn.__name__} failed: {e}")

    all_flags.sort(key=lambda x: severity_order.get(x.severity, 9))
    return [f.to_dict() for f in all_flags]
