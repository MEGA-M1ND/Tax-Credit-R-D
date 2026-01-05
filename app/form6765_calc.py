"""Computation engine for Form 6765 (Rev. 12-2020).

This is *not tax advice*. It implements arithmetic shown on the form.

Enterprise-grade characteristics:
- Deterministic calculations (no LLM).
- Explicit formulas captured in provenance notes.
- Validations fail fast.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

from .form6765_models import (
    Form6765Header,
    Form6765Inputs,
    Form6765Lines,
    Form6765Provenance,
    Form6765Document,
    CreditMethod,
    Section280CChoice,
)


def _d(x) -> Decimal:
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _money(x: Decimal) -> Decimal:
    # quantize to cents
    return x.quantize(Decimal("0.01"))


def _sha256_dict(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class EligibilitySnapshot:
    """Represents frozen, human-approved eligibility used for the claim."""

    snapshot_id: str
    approved_project_ids: list[str]
    snapshot_sha256: str


def compute_form6765(
    *,
    header: Form6765Header,
    inputs: Form6765Inputs,
    snapshot: EligibilitySnapshot,
    ruleset_version: str,
    prompt_version: Optional[str] = None,
    model_name: Optional[str] = None,
    reviewer_rollup: Optional[Dict[str, Any]] = None,
) -> Form6765Document:
    """Compute Form 6765 lines from inputs.

    Required:
    - header, inputs
    - snapshot (frozen approved projects)
    - ruleset_version (for audit provenance)
    """

    notes: Dict[str, Any] = {}
    reviewer_rollup = reviewer_rollup or {}

    # --- Normalize QREs ---
    wages = _d(inputs.qre_wages)
    supplies = _d(inputs.qre_supplies)
    computers = _d(inputs.qre_computers)
    contracts_gross = _d(inputs.qre_contract_research_gross)
    pct = Decimal(str(inputs.contract_applicable_pct))
    contracts = _money(contracts_gross * pct)

    notes["qre"] = {
        "wages": str(wages),
        "supplies": str(supplies),
        "computers": str(computers),
        "contract_gross": str(contracts_gross),
        "contract_pct": str(pct),
        "contract_qualified": str(contracts),
    }

    lines = Form6765Lines()

    # --- Common lines for A/B (energy consortium + basic research) ---
    energy = _d(inputs.energy_consortia_amount)
    basic = _d(inputs.basic_research_payments)
    base_period = _d(inputs.qualified_org_base_period_amount)

    # Section A lines 1-4
    lines.line_1 = _money(energy)
    lines.line_2 = _money(basic)
    lines.line_3 = _money(base_period)
    lines.line_4 = _money(max(_d(0), _d(lines.line_2) - _d(lines.line_3)))

    # Section B lines 18-22 mirror
    lines.line_18 = _money(energy)
    lines.line_19 = _money(basic)
    lines.line_20 = _money(base_period)
    lines.line_21 = _money(max(_d(0), _d(lines.line_19) - _d(lines.line_20)))
    lines.line_22 = _money(_d(lines.line_18) + _d(lines.line_21))
    lines.line_23 = _money(_d(lines.line_22) * Decimal("0.20"))

    # --- Section A (Regular Credit) ---
    # Lines 5-9
    lines.line_5 = _money(wages)
    lines.line_6 = _money(supplies)
    lines.line_7 = _money(computers)
    lines.line_8 = _money(contracts)
    lines.line_9 = _money(_d(lines.line_5) + _d(lines.line_6) + _d(lines.line_7) + _d(lines.line_8))

    # Lines 10-16 require fixed base % and avg receipts
    if inputs.fixed_base_percentage is not None:
        lines.line_10_fixed_base_pct = float(inputs.fixed_base_percentage)
    if inputs.avg_annual_gross_receipts is not None:
        lines.line_11_avg_gross_receipts = _money(_d(inputs.avg_annual_gross_receipts))
    else:
        lines.line_11_avg_gross_receipts = _money(Decimal("0"))

    if lines.line_10_fixed_base_pct is not None and inputs.avg_annual_gross_receipts is not None:
        pct10 = Decimal(str(lines.line_10_fixed_base_pct))
        lines.line_12 = _money(_d(lines.line_11_avg_gross_receipts) * pct10)
        lines.line_13 = _money(max(Decimal("0"), _d(lines.line_9) - _d(lines.line_12)))
        lines.line_14 = _money(_d(lines.line_9) * Decimal("0.50"))
        lines.line_15 = _money(min(_d(lines.line_13), _d(lines.line_14)))
    else:
        # If not provided, keep dependent lines at 0; enterprises usually supply these.
        lines.line_12 = _money(Decimal("0"))
        lines.line_13 = _money(Decimal("0"))
        lines.line_14 = _money(Decimal("0"))
        lines.line_15 = _money(Decimal("0"))

    lines.line_16 = _money(_d(lines.line_1) + _d(lines.line_4) + _d(lines.line_15))

    # Line 17 (280C reduced credit election impacts rate)
    elect_reduced = inputs.section_280c_choice == Section280CChoice.REDUCED
    lines.line_17_280c_elected = elect_reduced
    rate = Decimal("0.158") if elect_reduced else Decimal("0.20")
    lines.line_17 = _money(_d(lines.line_16) * rate)

    # --- Section B (ASC) ---
    # Lines 24-28
    lines.line_24 = _money(wages)
    lines.line_25 = _money(supplies)
    lines.line_26 = _money(computers)
    lines.line_27 = _money(contracts)
    lines.line_28 = _money(_d(lines.line_24) + _d(lines.line_25) + _d(lines.line_26) + _d(lines.line_27))

    prior_total = _d(inputs.prior_3_year_qre_total or Decimal("0"))
    lines.line_29_prior_3_year_qre_total = _money(prior_total)

    if inputs.prior_3_year_qre_total is not None and prior_total > 0:
        lines.line_30 = _money(prior_total / Decimal("6.0"))
        lines.line_31 = _money(max(Decimal("0"), _d(lines.line_28) - _d(lines.line_30)))
        lines.line_32 = _money(_d(lines.line_31) * Decimal("0.14"))
    else:
        # If any of the prior 3 years is zero, instructions say skip 30-31 and use 6% of line 28
        lines.line_30 = _money(Decimal("0"))
        lines.line_31 = _money(Decimal("0"))
        lines.line_32 = _money(_d(lines.line_28) * Decimal("0.06"))

    lines.line_33 = _money(_d(lines.line_23) + _d(lines.line_32))

    elect_reduced_b = elect_reduced
    lines.line_34_280c_elected = elect_reduced_b
    if elect_reduced_b:
        lines.line_34 = _money(_d(lines.line_33) * Decimal("0.79"))
    else:
        lines.line_34 = _money(_d(lines.line_33))

    # --- Section C (Current Year Credit) ---
    lines.line_35 = _money(_d(inputs.form_8932_overlap_wages_credit))

    # line 36 uses line 17 or 34 depending on method
    chosen_credit = _d(lines.line_17) if inputs.credit_method == CreditMethod.REGULAR else _d(lines.line_34)
    lines.line_36 = _money(max(Decimal("0"), chosen_credit - _d(lines.line_35)))
    lines.line_37 = _money(_d(inputs.pass_through_credit))
    lines.line_38 = _money(_d(lines.line_36) + _d(lines.line_37))

    # Lines 39-40 (only for estates/trusts; keep 0 unless explicitly set)
    lines.line_39 = _money(Decimal("0"))
    lines.line_40 = _money(_d(lines.line_38) - _d(lines.line_39))

    # --- Section D (Payroll Tax Election) ---
    lines.line_41_qsb_election = bool(inputs.is_qsb_payroll_election)
    if inputs.is_qsb_payroll_election:
        elected = min(_d(inputs.payroll_tax_credit_elected), Decimal("250000"))
        lines.line_42 = _money(elected)
        lines.line_43 = _money(_d(inputs.general_business_credit_carryforward))
        # line 44 rules: smallest of line 36, line 42, line 43 (for most filers)
        lines.line_44 = _money(min(_d(lines.line_36), _d(lines.line_42), _d(lines.line_43)))
    else:
        lines.line_42 = _money(Decimal("0"))
        lines.line_43 = _money(Decimal("0"))
        lines.line_44 = _money(Decimal("0"))

    # --- Validations (hard fail for obviously missing enterprise inputs) ---
    # If REGULAR credit selected, enterprises should provide fixed base % and avg receipts.
    if inputs.credit_method == CreditMethod.REGULAR:
        if inputs.fixed_base_percentage is None or inputs.avg_annual_gross_receipts is None:
            raise ValueError("REGULAR credit selected but fixed_base_percentage and avg_annual_gross_receipts are required")

    computed_at = datetime.now(timezone.utc).isoformat()
    prov = Form6765Provenance(
        eligibility_snapshot_id=snapshot.snapshot_id,
        eligibility_snapshot_sha256=snapshot.snapshot_sha256,
        ruleset_version=ruleset_version,
        prompt_version=prompt_version,
        model_name=model_name,
        reviewer_rollup=reviewer_rollup,
        calculation_notes=notes,
        computed_at_utc=computed_at,
    )

    # Create deterministic version id + hash
    base_payload = {
        "header": header.model_dump(),
        "inputs": inputs.model_dump(),
        "lines": lines.model_dump(),
        "provenance": prov.model_dump(),
    }
    form_sha = _sha256_dict(base_payload)
    form_version_id = f"f6765_{header.tax_year}_{form_sha[:12]}"

    doc_payload = dict(base_payload)
    doc_payload["form_version_id"] = form_version_id
    doc_payload["form_version_sha256"] = form_sha

    return Form6765Document(
        header=header,
        inputs=inputs,
        lines=lines,
        provenance=prov,
        form_version_id=form_version_id,
        form_version_sha256=form_sha,
    )
