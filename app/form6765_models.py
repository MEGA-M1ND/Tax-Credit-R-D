"""Form 6765 data model (IRS Rev. 12-2020).

Goal: represent the *filled form values* in a strict, auditable structure.

Design principles (enterprise-grade):
- One canonical field per IRS line.
- Store computation provenance separately (inputs + formulas + hashes).
- Keep rendering concerns (PDF coordinates) out of this model.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, condecimal


Money = condecimal(max_digits=18, decimal_places=2)


class CreditMethod(str, Enum):
    REGULAR = "REGULAR"  # Section A
    ASC = "ASC"          # Section B


class Section280CChoice(str, Enum):
    REDUCED = "REDUCED"  # elect reduced credit
    FULL = "FULL"        # do not elect reduced credit


class Form6765Header(BaseModel):
    """Top-of-form taxpayer identifiers (not tax advice; just fields)."""

    tax_year: int = Field(..., ge=1990, le=2100)
    name_on_return: str = Field(..., min_length=1, max_length=200)
    identifying_number: str = Field(..., min_length=1, max_length=32, description="EIN/SSN as shown on return")


class Form6765Inputs(BaseModel):
    """Inputs required to compute Form 6765 that typically come from finance/tax data."""

    # QRE totals (current year)
    qre_wages: Money = Field(0)
    qre_supplies: Money = Field(0)
    qre_computers: Money = Field(0)  # rental/lease costs of computers (line 7/26)
    qre_contract_research_gross: Money = Field(0)
    contract_applicable_pct: float = Field(0.65, ge=0.0, le=1.0)  # commonly 65%

    # Section A (Regular) base data
    fixed_base_percentage: Optional[float] = Field(None, ge=0.0, le=0.16)
    avg_annual_gross_receipts: Optional[Money] = None

    # Section B (ASC) historical QREs
    prior_3_year_qre_total: Optional[Money] = None

    # Basic research / energy consortium (often 0)
    energy_consortia_amount: Money = Field(0)
    basic_research_payments: Money = Field(0)
    qualified_org_base_period_amount: Money = Field(0)

    # Section C inputs
    form_8932_overlap_wages_credit: Money = Field(0, description="Line 35")
    pass_through_credit: Money = Field(0, description="Line 37")

    # Section D (Payroll tax election)
    is_qsb_payroll_election: bool = False
    payroll_tax_credit_elected: Money = Field(0)
    general_business_credit_carryforward: Money = Field(0)

    # Credit method choice
    credit_method: CreditMethod = CreditMethod.ASC
    section_280c_choice: Section280CChoice = Section280CChoice.FULL


class Form6765Lines(BaseModel):
    """All numeric lines (1..44) captured explicitly.

    Notes:
    - Some lines are percentages; represent them as floats.
    - Monetary lines are Money.
    """

    # Section A — Regular Credit (lines 1–17)
    line_1: Money = 0
    line_2: Money = 0
    line_3: Money = 0
    line_4: Money = 0
    line_5: Money = 0
    line_6: Money = 0
    line_7: Money = 0
    line_8: Money = 0
    line_9: Money = 0
    line_10_fixed_base_pct: Optional[float] = None
    line_11_avg_gross_receipts: Money = 0
    line_12: Money = 0
    line_13: Money = 0
    line_14: Money = 0
    line_15: Money = 0
    line_16: Money = 0
    line_17: Money = 0
    line_17_280c_elected: Optional[bool] = None

    # Section B — Alternative Simplified Credit (lines 18–34)
    line_18: Money = 0
    line_19: Money = 0
    line_20: Money = 0
    line_21: Money = 0
    line_22: Money = 0
    line_23: Money = 0
    line_24: Money = 0
    line_25: Money = 0
    line_26: Money = 0
    line_27: Money = 0
    line_28: Money = 0
    line_29_prior_3_year_qre_total: Money = 0
    line_30: Money = 0
    line_31: Money = 0
    line_32: Money = 0
    line_33: Money = 0
    line_34: Money = 0
    line_34_280c_elected: Optional[bool] = None

    # Section C — Current Year Credit (lines 35–40)
    line_35: Money = 0
    line_36: Money = 0
    line_37: Money = 0
    line_38: Money = 0
    line_39: Money = 0
    line_40: Money = 0

    # Section D — Payroll Tax Election (lines 41–44)
    line_41_qsb_election: Optional[bool] = None
    line_42: Money = 0
    line_43: Money = 0
    line_44: Money = 0


class Form6765Provenance(BaseModel):
    """Auditability: record where numbers came from."""

    eligibility_snapshot_id: str
    eligibility_snapshot_sha256: str
    ruleset_version: str
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    reviewer_rollup: Dict[str, Any] = Field(default_factory=dict)  # who approved what
    calculation_notes: Dict[str, Any] = Field(default_factory=dict)  # formulas / intermediate values
    computed_at_utc: str


class Form6765Document(BaseModel):
    header: Form6765Header
    inputs: Form6765Inputs
    lines: Form6765Lines
    provenance: Form6765Provenance
    form_version_id: str
    form_version_sha256: str
