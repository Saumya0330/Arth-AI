"""
अर्थAI — Module 1: CSV Extractor

Parses CSV/Excel files exported from Tally, ERP systems, or manual spreadsheets.
Maps common column names to FinancialStatement schema fields.
Returns a partial dict in the same shape as parse_financial_text() output.

Merge strategy (used by ingest.py):
  First non-null value wins per field when merging multiple files.
  Source tag for CSV fields: "csv"
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Maps common CSV column/row label variants → schema dotted path
FIELD_MAP = {
    # Balance sheet — equity
    "share capital":              "balance_sheet.shareholders_equity.share_capital",
    "paid-up capital":            "balance_sheet.shareholders_equity.share_capital",
    "paid up capital":            "balance_sheet.shareholders_equity.share_capital",
    "reserves and surplus":       "balance_sheet.shareholders_equity.reserves_and_surplus",
    "reserves & surplus":         "balance_sheet.shareholders_equity.reserves_and_surplus",

    # Balance sheet — non-current liabilities
    "long term borrowings":       "balance_sheet.non_current_liabilities.long_term_borrowings",
    "long-term borrowings":       "balance_sheet.non_current_liabilities.long_term_borrowings",
    "deferred tax liabilities":   "balance_sheet.non_current_liabilities.deferred_tax_liabilities",
    "other long term liabilities":"balance_sheet.non_current_liabilities.other_long_term_liabilities",
    "long term provisions":       "balance_sheet.non_current_liabilities.long_term_provisions",

    # Balance sheet — current liabilities
    "short term borrowings":      "balance_sheet.current_liabilities.short_term_borrowings",
    "short-term borrowings":      "balance_sheet.current_liabilities.short_term_borrowings",
    "trade payables":             "balance_sheet.current_liabilities.trade_payables",
    "sundry creditors":           "balance_sheet.current_liabilities.trade_payables",
    "other current liabilities":  "balance_sheet.current_liabilities.other_current_liabilities",
    "short term provisions":      "balance_sheet.current_liabilities.short_term_provisions",

    # Balance sheet — non-current assets
    "tangible assets":            "balance_sheet.non_current_assets.fixed_assets_tangible",
    "fixed assets":               "balance_sheet.non_current_assets.fixed_assets_tangible",
    "property plant equipment":   "balance_sheet.non_current_assets.fixed_assets_tangible",
    "intangible assets":          "balance_sheet.non_current_assets.fixed_assets_intangible",
    "capital wip":                "balance_sheet.non_current_assets.capital_wip",
    "capital work in progress":   "balance_sheet.non_current_assets.capital_wip",
    "non current investments":    "balance_sheet.non_current_assets.long_term_investments",
    "long term investments":      "balance_sheet.non_current_assets.long_term_investments",
    "deferred tax assets":        "balance_sheet.non_current_assets.deferred_tax_assets",
    "long term loans and advances":"balance_sheet.non_current_assets.long_term_loans_and_advances",
    "other non current assets":   "balance_sheet.non_current_assets.other_non_current_assets",

    # Balance sheet — current assets
    "inventories":                "balance_sheet.current_assets.inventories",
    "stock":                      "balance_sheet.current_assets.inventories",
    "trade receivables":          "balance_sheet.current_assets.trade_receivables",
    "sundry debtors":             "balance_sheet.current_assets.trade_receivables",
    "cash and cash equivalents":  "balance_sheet.current_assets.cash_and_cash_equivalents",
    "cash and bank":              "balance_sheet.current_assets.cash_and_cash_equivalents",
    "short term loans and advances":"balance_sheet.current_assets.short_term_loans_and_advances",
    "other current assets":       "balance_sheet.current_assets.other_current_assets",

    # P&L
    "revenue from operations":    "profit_and_loss.revenue_from_operations",
    "net revenue":                "profit_and_loss.revenue_from_operations",
    "turnover":                   "profit_and_loss.revenue_from_operations",
    "other income":               "profit_and_loss.other_income",
    "cost of materials consumed": "profit_and_loss.cost_of_materials",
    "cost of goods sold":         "profit_and_loss.cost_of_materials",
    "purchases":                  "profit_and_loss.cost_of_materials",
    "employee benefits expense":  "profit_and_loss.employee_benefits_expense",
    "staff costs":                "profit_and_loss.employee_benefits_expense",
    "salaries and wages":         "profit_and_loss.employee_benefits_expense",
    "finance costs":              "profit_and_loss.finance_costs",
    "interest expense":           "profit_and_loss.finance_costs",
    "depreciation":               "profit_and_loss.depreciation",
    "other expenses":             "profit_and_loss.other_expenses",
    "exceptional items":          "profit_and_loss.exceptional_items",
    "tax expense":                "profit_and_loss.tax_expense",
    "income tax":                 "profit_and_loss.tax_expense",
    "profit after tax":           "profit_and_loss.profit_after_tax",
    "net profit":                 "profit_and_loss.profit_after_tax",
    "pat":                        "profit_and_loss.profit_after_tax",

    # Identity
    "company name":               "company_name",
    "cin":                        "cin",
    "pan":                        "pan",
    "financial year":             "financial_year_end",
    "fy":                         "financial_year_end",
}


def _parse_number(val) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("(", "-").replace(")", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _set_nested(d: dict, dotted_path: str, value) -> None:
    keys = dotted_path.split(".")
    node = d
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def extract_from_csv(file_path: str) -> tuple:
    """
    Parse a CSV or Excel file and return (partial_fs_dict, sources_dict).
    partial_fs_dict matches FinancialStatement schema shape.
    sources_dict maps dotted field path → "csv".
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for CSV support. Run: pip install pandas openpyxl")

    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, header=None)
    else:
        # Try common encodings
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(path, header=None, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"Could not read {path} with any supported encoding.")

    partial = {}
    sources = {}

    # Strategy: walk every cell — if a cell matches a known label,
    # look right and down for the first numeric value.
    rows = df.values.tolist()
    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row):
            if cell is None or str(cell).strip() == "":
                continue
            label = str(cell).strip().lower()
            schema_path = FIELD_MAP.get(label)
            if not schema_path:
                continue

            # Search right in same row first, then below
            candidates = []
            for look_col in range(col_idx + 1, min(col_idx + 5, len(row))):
                candidates.append(row[look_col])
            for look_row in range(row_idx + 1, min(row_idx + 3, len(rows))):
                if col_idx < len(rows[look_row]):
                    candidates.append(rows[look_row][col_idx])

            for candidate in candidates:
                num = _parse_number(candidate)
                if num is not None:
                    _set_nested(partial, schema_path, num)
                    sources[schema_path] = "csv"
                    logger.debug(f"CSV: {label} → {schema_path} = {num}")
                    break

    logger.info(f"CSV extraction: {len(sources)} fields from {path.name}")
    return partial, sources
