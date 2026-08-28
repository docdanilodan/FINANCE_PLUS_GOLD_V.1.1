from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MandateInputs:
    requested_amount: float = 0.0
    approved_amount: float = 0.0
    fee_pct: float = 0.0
    fixed_fee: float = 0.0
    vat_pct: float = 0.0
    withholding_pct: float = 0.0


def calculate_mandate(i: MandateInputs) -> dict:
    """Deterministic fee simulator; tax percentages are user inputs, never assumptions."""
    fee_base = i.approved_amount if i.approved_amount > 0 else i.requested_amount
    variable_fee = max(0.0, fee_base) * max(0.0, i.fee_pct)
    taxable_fee = variable_fee + max(0.0, i.fixed_fee)
    vat = taxable_fee * max(0.0, i.vat_pct)
    withholding = taxable_fee * max(0.0, i.withholding_pct)
    total_due = taxable_fee + vat - withholding
    return {
        "fee_base": round(fee_base, 2),
        "variable_fee": round(variable_fee, 2),
        "fixed_fee": round(max(0.0, i.fixed_fee), 2),
        "taxable_fee": round(taxable_fee, 2),
        "vat": round(vat, 2),
        "withholding": round(withholding, 2),
        "total_due": round(total_due, 2),
    }
