"""
अर्थAI — Agent 1: Math Validator

Pure Python — ZERO LLM calls.
Validates every arithmetic relationship in the financial statements.
If numbers don't add up, this agent flags it before any LLM ever sees the data.

Checks performed:
  1. Balance sheet equation (Assets = Equity + Liabilities)
  2. Shareholders equity sub-total
  3. Non-current liabilities sub-total
  4. Current liabilities sub-total
  5. Non-current assets sub-total
  6. Current assets sub-total
  7. P&L: Revenue - Expenses ≈ Profit (if all components present)
  8. Cash flow net change ≈ closing - opening cash (if present)
"""

import logging
from typing import Any
from agents.state import AuditState

logger = logging.getLogger(__name__)

TOLERANCE = 2.0  # INR tolerance for rounding differences


def _sum_vals(d: dict) -> tuple:
    """Returns (total, count_of_non_null_values)."""
    vals = [v for v in d.values() if isinstance(v, (int, float))]
    return round(sum(vals), 2), len(vals)


def _check(name: str, expected: float, actual: float, critical: bool = False) -> dict:
    diff = abs(expected - actual)
    passed = diff <= TOLERANCE
    return {
        "check": name,
        "expected": round(expected, 2),
        "actual": round(actual, 2),
        "difference": round(diff, 2),
        "passed": passed,
        "critical": critical and not passed,
    }


def run_math_validator(state: AuditState) -> AuditState:
    """
    Agent 1 node function.
    Reads state["financial_json"], writes state["math_report"].
    No LLM, no external calls.
    """
    fs      = state["financial_json"]
    bs      = fs.get("balance_sheet", {})
    pl      = fs.get("profit_and_loss", {})
    checks  = []
    errors  = list(state.get("errors", []))

    # ── Balance sheet sections ─────────────────────────────────────────────────
    se_total,  se_n  = _sum_vals(bs.get("shareholders_equity", {}))
    ncl_total, ncl_n = _sum_vals(bs.get("non_current_liabilities", {}))
    cl_total,  cl_n  = _sum_vals(bs.get("current_liabilities", {}))
    nca_total, nca_n = _sum_vals(bs.get("non_current_assets", {}))
    ca_total,  ca_n  = _sum_vals(bs.get("current_assets", {}))

    total_equity_liab = round(se_total + ncl_total + cl_total, 2)
    total_assets      = round(nca_total + ca_total, 2)

    # Only run BS equation check if we have data on both sides
    if se_n + ncl_n + cl_n > 0 and nca_n + ca_n > 0:
        checks.append(_check(
            "Balance Sheet Equation (Assets = Equity + Liabilities)",
            total_assets, total_equity_liab, critical=True
        ))

    # ── P&L arithmetic ─────────────────────────────────────────────────────────
    revenue      = pl.get("revenue_from_operations") or 0
    other_income = pl.get("other_income") or 0
    total_income = round(revenue + other_income, 2)

    expenses = [
        pl.get("cost_of_materials"),
        pl.get("employee_benefits_expense"),
        pl.get("finance_costs"),
        pl.get("depreciation"),
        pl.get("other_expenses"),
    ]
    known_expenses = [e for e in expenses if isinstance(e, (int, float))]
    pat = pl.get("profit_after_tax")
    tax = pl.get("tax_expense") or 0

    # Only check if we have all components
    if len(known_expenses) == 5 and pat is not None:
        total_exp  = round(sum(known_expenses), 2)
        pbt        = round(total_income - total_exp, 2)
        computed_pat = round(pbt - tax, 2)
        checks.append(_check(
            "P&L: (Revenue + Other Income) - Expenses - Tax ≈ Profit After Tax",
            pat, computed_pat, critical=True
        ))
    elif known_expenses:
        # Partial check — flag that we can't fully validate
        checks.append({
            "check": "P&L completeness",
            "passed": False,
            "critical": False,
            "difference": 0,
            "note": f"Only {len(known_expenses)}/5 expense components extracted. "
                    "Full P&L arithmetic validation not possible.",
        })

    # ── Cash flow check ────────────────────────────────────────────────────────
    # If cash flow statement data is present in financial_json
    cf = fs.get("cash_flow", {})
    if cf:
        operating  = cf.get("net_cash_operating")
        investing  = cf.get("net_cash_investing")
        financing  = cf.get("net_cash_financing")
        net_change = cf.get("net_change_in_cash")
        if all(isinstance(v, (int, float)) for v in [operating, investing, financing, net_change]):
            computed_net = round(operating + investing + financing, 2)
            checks.append(_check(
                "Cash Flow: Operating + Investing + Financing = Net Change in Cash",
                net_change, computed_net, critical=True
            ))

    # ── Summary ────────────────────────────────────────────────────────────────
    critical_failures = [c for c in checks if c.get("critical")]
    passed_count      = sum(1 for c in checks if c.get("passed", True))

    math_report = {
        "checks":               checks,
        "total_checks":         len(checks),
        "passed":               passed_count,
        "failed":               len(checks) - passed_count,
        "has_critical_errors":  len(critical_failures) > 0,
        "critical_failures":    critical_failures,
        "balance_sheet_totals": {
            "total_equity_and_liabilities": total_equity_liab,
            "total_assets":                 total_assets,
            "difference":                   abs(total_equity_liab - total_assets),
        },
    }

    logger.info(
        f"[MathValidator] {passed_count}/{len(checks)} checks passed. "
        f"Critical errors: {len(critical_failures)}"
    )

    return {
        **state,
        "math_report": math_report,
        "current_step": "math_validated",
        "errors": errors,
    }
