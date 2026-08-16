from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

def _money(value: Any) -> Decimal:
    try: return max(Decimal("0"), Decimal(str(value or 0)))
    except (InvalidOperation, ValueError): return Decimal("0")

def assess_financial_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    available = _money(payload.get("available_funds"))
    required = _money(payload.get("proof_of_funds_required"))
    relocation = _money(payload.get("estimated_relocation_cost"))
    reserve = _money(payload.get("settlement_reserve"))
    target = required + relocation + reserve
    gap = max(Decimal("0"), target - available)
    surplus = max(Decimal("0"), available - target)
    ratio = Decimal("1") if target == 0 else min(Decimal("1"), available / target)
    score = int((ratio * 100).quantize(Decimal("1")))
    if target == 0: status = "requirements_needed"
    elif gap == 0: status = "ready"
    elif score >= 75: status = "close"
    elif score >= 40: status = "building"
    else: status = "early_stage"
    return {"currency": str(payload.get("currency") or "USD").upper(), "available_funds": float(available), "proof_of_funds_required": float(required), "estimated_relocation_cost": float(relocation), "settlement_reserve": float(reserve), "target_funds": float(target), "funding_gap": float(gap), "surplus": float(surplus), "readiness_score": score, "status": status}
