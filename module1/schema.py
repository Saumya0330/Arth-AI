"""
अर्थAI — Module 1: Financial Statement JSON Schema

Represents an Indian company's financial statements in Schedule III format
(Companies Act 2013). All amounts in INR (₹).

Design principles:
- Every field is Optional so partial extraction never breaks the pipeline
- All downstream modules consume this same schema — never change field names
- New statement types (cash flow, notes) can be added without breaking existing code
"""

from typing import Optional
from dataclasses import dataclass, field, asdict
import json


@dataclass
class ShareholdersEquity:
    share_capital: Optional[float] = None
    reserves_and_surplus: Optional[float] = None
    money_received_against_share_warrants: Optional[float] = None

    @property
    def total(self) -> Optional[float]:
        vals = [self.share_capital, self.reserves_and_surplus,
                self.money_received_against_share_warrants]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None


@dataclass
class NonCurrentLiabilities:
    long_term_borrowings: Optional[float] = None
    deferred_tax_liabilities: Optional[float] = None
    other_long_term_liabilities: Optional[float] = None
    long_term_provisions: Optional[float] = None

    @property
    def total(self) -> Optional[float]:
        vals = [self.long_term_borrowings, self.deferred_tax_liabilities,
                self.other_long_term_liabilities, self.long_term_provisions]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None


@dataclass
class CurrentLiabilities:
    short_term_borrowings: Optional[float] = None
    trade_payables: Optional[float] = None
    other_current_liabilities: Optional[float] = None
    short_term_provisions: Optional[float] = None

    @property
    def total(self) -> Optional[float]:
        vals = [self.short_term_borrowings, self.trade_payables,
                self.other_current_liabilities, self.short_term_provisions]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None


@dataclass
class NonCurrentAssets:
    fixed_assets_tangible: Optional[float] = None
    fixed_assets_intangible: Optional[float] = None
    capital_wip: Optional[float] = None
    long_term_investments: Optional[float] = None
    deferred_tax_assets: Optional[float] = None
    long_term_loans_and_advances: Optional[float] = None
    other_non_current_assets: Optional[float] = None

    @property
    def total(self) -> Optional[float]:
        vals = [self.fixed_assets_tangible, self.fixed_assets_intangible,
                self.capital_wip, self.long_term_investments,
                self.deferred_tax_assets, self.long_term_loans_and_advances,
                self.other_non_current_assets]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None


@dataclass
class CurrentAssets:
    inventories: Optional[float] = None
    trade_receivables: Optional[float] = None
    cash_and_cash_equivalents: Optional[float] = None
    short_term_loans_and_advances: Optional[float] = None
    other_current_assets: Optional[float] = None

    @property
    def total(self) -> Optional[float]:
        vals = [self.inventories, self.trade_receivables,
                self.cash_and_cash_equivalents, self.short_term_loans_and_advances,
                self.other_current_assets]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None


@dataclass
class BalanceSheet:
    # Equity & Liabilities
    shareholders_equity: ShareholdersEquity = field(default_factory=ShareholdersEquity)
    non_current_liabilities: NonCurrentLiabilities = field(default_factory=NonCurrentLiabilities)
    current_liabilities: CurrentLiabilities = field(default_factory=CurrentLiabilities)
    # Assets
    non_current_assets: NonCurrentAssets = field(default_factory=NonCurrentAssets)
    current_assets: CurrentAssets = field(default_factory=CurrentAssets)

    @property
    def total_equity_and_liabilities(self) -> Optional[float]:
        vals = [self.shareholders_equity.total,
                self.non_current_liabilities.total,
                self.current_liabilities.total]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None

    @property
    def total_assets(self) -> Optional[float]:
        vals = [self.non_current_assets.total, self.current_assets.total]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None

    @property
    def is_balanced(self) -> Optional[bool]:
        if self.total_equity_and_liabilities is None or self.total_assets is None:
            return None
        return abs(self.total_equity_and_liabilities - self.total_assets) < 1.0


@dataclass
class ProfitAndLoss:
    revenue_from_operations: Optional[float] = None
    other_income: Optional[float] = None
    cost_of_materials: Optional[float] = None
    employee_benefits_expense: Optional[float] = None
    finance_costs: Optional[float] = None
    depreciation: Optional[float] = None
    other_expenses: Optional[float] = None
    exceptional_items: Optional[float] = None
    tax_expense: Optional[float] = None
    profit_after_tax: Optional[float] = None

    @property
    def total_revenue(self) -> Optional[float]:
        vals = [self.revenue_from_operations, self.other_income]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None

    @property
    def total_expenses(self) -> Optional[float]:
        vals = [self.cost_of_materials, self.employee_benefits_expense,
                self.finance_costs, self.depreciation, self.other_expenses]
        present = [v for v in vals if v is not None]
        return sum(present) if present else None


@dataclass
class FinancialStatement:
    """Root object — one per company per financial year."""
    # Identity
    company_name: Optional[str] = None
    cin: Optional[str] = None                        # Corporate Identity Number
    pan: Optional[str] = None
    registered_address: Optional[str] = None
    financial_year_end: Optional[str] = None         # e.g. "2023-03-31"
    currency: str = "INR"
    auditor_name: Optional[str] = None
    auditor_firm_reg: Optional[str] = None

    # Statements
    balance_sheet: BalanceSheet = field(default_factory=BalanceSheet)
    profit_and_loss: ProfitAndLoss = field(default_factory=ProfitAndLoss)

    # Extraction metadata — never used in downstream ML, only for traceability
    source_file: Optional[str] = None
    extraction_method: Optional[str] = None         # "text" | "ocr"
    extraction_confidence: Optional[float] = None   # 0.0 – 1.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, d: dict) -> "FinancialStatement":
        bs_data = d.pop("balance_sheet", {})
        pl_data = d.pop("profit_and_loss", {})
        fs = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        fs.balance_sheet = BalanceSheet(
            shareholders_equity=ShareholdersEquity(**bs_data.get("shareholders_equity", {})),
            non_current_liabilities=NonCurrentLiabilities(**bs_data.get("non_current_liabilities", {})),
            current_liabilities=CurrentLiabilities(**bs_data.get("current_liabilities", {})),
            non_current_assets=NonCurrentAssets(**bs_data.get("non_current_assets", {})),
            current_assets=CurrentAssets(**bs_data.get("current_assets", {})),
        )
        fs.profit_and_loss = ProfitAndLoss(**pl_data)
        return fs
