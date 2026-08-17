from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit


CONTRACT_VERSION = "b09-v1"
PLANNING_CATEGORIES = (
    "fees",
    "tuition",
    "relocation",
    "flight",
    "accommodation",
    "settlement_reserve",
)

CATEGORY_ALIASES = {
    "visa_fee": "fees",
    "application_fee": "fees",
    "document": "fees",
    "courier": "fees",
    "translation": "fees",
    "notarization": "fees",
    "insurance": "relocation",
    "other": "relocation",
    "settlement": "settlement_reserve",
}


class FinancialReadinessInputError(ValueError):
    def __init__(self, code: str, field: str):
        super().__init__(code)
        self.code = code
        self.field = field


def _money(value: Any, field: str, *, optional: bool = False) -> Optional[Decimal]:
    if value is None or value == "":
        return None if optional else Decimal("0")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise FinancialReadinessInputError("invalid_non_negative_amount", field) from None
    if not amount.is_finite() or amount < 0:
        raise FinancialReadinessInputError("invalid_non_negative_amount", field)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _output_money(value: Optional[Decimal]) -> Optional[float]:
    return None if value is None else float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _currency(value: Any, field: str = "currency") -> str:
    token = str(value or "USD").strip().upper()
    if len(token) != 3 or not token.isalpha():
        raise FinancialReadinessInputError("invalid_currency", field)
    return token


def _non_negative_int(value: Any, field: str, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise FinancialReadinessInputError("invalid_non_negative_integer", field) from None
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise FinancialReadinessInputError("invalid_non_negative_integer", field)
    return int(number)


def _date(value: Any, field: str) -> Optional[date]:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise FinancialReadinessInputError("invalid_iso_date", field) from None


def _optional_https_url(value: Any, field: str) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None
    parsed = urlsplit(token)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise FinancialReadinessInputError("https_source_url_required", field)
    return token


def _months_until(target: date, today: date) -> int:
    if target <= today:
        return 0
    months = (target.year - today.year) * 12 + target.month - today.month
    if target.day > today.day:
        months += 1
    return max(months, 1)


def _category(value: Any) -> Optional[str]:
    token = str(value or "").strip().lower()
    token = CATEGORY_ALIASES.get(token, token)
    return token if token in PLANNING_CATEGORIES else None


def _cost_items(payload: Dict[str, Any], currency: str) -> List[Dict[str, Any]]:
    raw_items: List[Tuple[Any, bool]] = []
    supplied = payload.get("cost_items")
    if isinstance(supplied, list):
        raw_items.extend((item, True) for item in supplied)

    supplied_costs = payload.get("costs")
    if isinstance(supplied_costs, dict):
        for category, value in supplied_costs.items():
            if isinstance(value, dict):
                raw_items.append(({"category": category, **value}, False))
            else:
                raw_items.append(({"category": category, "amount": value}, False))

    for category in PLANNING_CATEGORIES:
        if category in payload:
            raw_items.append(({"category": category, "amount": payload.get(category)}, False))

    normalized: List[Dict[str, Any]] = []
    for index, (item, trusted_metadata) in enumerate(raw_items):
        if not isinstance(item, dict):
            raise FinancialReadinessInputError("invalid_cost_item", f"cost_items[{index}]")
        category = _category(item.get("category") or item.get("item_category"))
        if not category:
            raise FinancialReadinessInputError("unsupported_cost_category", f"cost_items[{index}].category")
        amount = _money(
            item.get("amount", item.get("planning_amount")),
            f"cost_items[{index}].amount",
        )
        item_currency = _currency(item.get("currency") or item.get("currency_code") or currency, f"cost_items[{index}].currency")
        normalized.append({
            "category": category,
            "label": str(item.get("label") or item.get("name") or category.replace("_", " ").title()).strip(),
            "amount": amount,
            "currency": item_currency,
            "source_type": str(item.get("source_type") or "route_estimate").strip().lower() if trusted_metadata else "user_entered",
            "source_url": _optional_https_url(item.get("source_url"), f"cost_items[{index}].source_url"),
            "source_title": str(item.get("source_title") or "").strip() or None,
            "source_checked_at": str(item.get("source_checked_at") or "").strip() or None,
            "amount_basis": str(item.get("amount_basis") or "route_estimated_maximum").strip().lower() if trusted_metadata else "entered_amount",
            "notes": str(item.get("notes") or "").strip() or None,
        })
    return normalized


def _sum_money(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def assess_financial_readiness(payload: Dict[str, Any], *, today: Optional[date] = None) -> Dict[str, Any]:
    currency = _currency(payload.get("currency") or payload.get("available_funds_currency") or "USD")
    savings = _money(
        payload.get("savings", payload.get("available_funds", payload.get("available_funds_amount"))),
        "savings",
    )
    expected_funding = _money(payload.get("expected_funding"), "expected_funding")

    family_size = _non_negative_int(payload.get("family_size"), "family_size", 1)
    if family_size == 0:
        raise FinancialReadinessInputError("family_size_must_include_applicant", "family_size")

    proof = payload.get("proof_of_funds") if isinstance(payload.get("proof_of_funds"), dict) else {}
    proof_amount = _money(
        proof.get(
            "amount",
            payload.get("proof_of_funds_required", payload.get("required_funds_amount")),
        ),
        "proof_of_funds.amount",
        optional=True,
    )
    proof_currency = _currency(proof.get("currency") or currency, "proof_of_funds.currency")
    proof_source_url = _optional_https_url(
        proof.get("source_url") or payload.get("proof_of_funds_source_url"),
        "proof_of_funds.source_url",
    )
    proof_source_title = str(proof.get("source_title") or payload.get("proof_of_funds_source_title") or "").strip() or None
    proof_source_checked_at = str(proof.get("source_checked_at") or payload.get("proof_of_funds_source_checked_at") or "").strip() or None

    costs = _cost_items(payload, currency)
    mismatches = []
    if proof_amount is not None and proof_currency != currency:
        mismatches.append({"field": "proof_of_funds", "currency": proof_currency})
    for item in costs:
        if item["amount"] and item["currency"] != currency:
            mismatches.append({"field": f"costs.{item['category']}", "currency": item["currency"]})

    category_totals = {
        category: _sum_money(item["amount"] for item in costs if item["category"] == category)
        for category in PLANNING_CATEGORIES
    }
    cost_total = _sum_money(category_totals.values())
    resource_total = _sum_money([savings or Decimal("0"), expected_funding or Decimal("0")])

    target_date = _date(payload.get("target_date"), "target_date")
    timeline_months = None
    target_status = "not_provided"
    if target_date:
        timeline_months = _months_until(target_date, today or date.today())
        target_status = "elapsed" if timeline_months == 0 else "active"
    elif payload.get("target_timeline_months") not in (None, ""):
        timeline_months = _non_negative_int(payload.get("target_timeline_months"), "target_timeline_months", 0)
        target_status = "active" if timeline_months > 0 else "elapsed"

    combined_target: Optional[Decimal] = None
    gap: Optional[Decimal] = None
    surplus: Optional[Decimal] = None
    monthly_target: Optional[Decimal] = None
    if proof_amount is not None and not mismatches:
        combined_target = _sum_money([proof_amount, cost_total])
        gap = max(Decimal("0"), combined_target - resource_total)
        surplus = max(Decimal("0"), resource_total - combined_target)
        if timeline_months and timeline_months > 0:
            monthly_target = (gap / Decimal(timeline_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    proof_status = "requirement_not_provided"
    if proof_amount is not None:
        proof_status = "user_supplied_source" if proof_source_url else "source_required"

    if mismatches:
        status = "currency_mismatch"
    elif proof_amount is None:
        status = "requirements_needed"
    elif not proof_source_url:
        status = "source_review_required"
    elif gap == 0:
        status = "ready_on_entered_figures"
    else:
        status = "funding_gap"

    warnings = []
    if proof_amount is None:
        warnings.append("Enter the current proof-of-funds requirement for the exact route and family size; MoveReady will not invent it.")
    elif not proof_source_url:
        warnings.append("Add the official source URL for the entered proof-of-funds requirement before relying on this plan.")
    if family_size > 1:
        warnings.append("Family size is recorded but does not trigger a MoveReady multiplier; use the authority's exact dependant requirement as the sourced input.")
    if expected_funding:
        warnings.append("Expected funding is shown separately from current savings and should be counted only when its amount, timing, and conditions are reliable.")
    if any(item["source_type"] == "route_estimate" for item in costs):
        warnings.append("Route-estimate costs are planning figures, not official fees or proof-of-funds thresholds.")
    if mismatches:
        warnings.append("Currencies differ, so no combined target, funding gap, or monthly target was calculated. MoveReady does not guess exchange rates.")
    if target_status == "elapsed" and gap:
        warnings.append("The target date or timeline has elapsed while a funding gap remains.")

    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "currency": currency,
        "household": {
            "family_size": family_size,
            "calculation_rule": "context_only_no_invented_multiplier",
        },
        "resources": {
            "savings": _output_money(savings),
            "expected_funding": _output_money(expected_funding),
            "total": _output_money(resource_total),
        },
        "proof_of_funds": {
            "amount": _output_money(proof_amount),
            "currency": proof_currency,
            "status": proof_status,
            "provenance": {
                "source_url": proof_source_url,
                "source_title": proof_source_title,
                "source_checked_at": proof_source_checked_at,
                "representation": "user_supplied_reference_not_moveready_verification" if proof_source_url else "missing",
            },
        },
        "planned_costs": {
            "items": [{**item, "amount": _output_money(item["amount"])} for item in costs],
            "by_category": {category: _output_money(amount) for category, amount in category_totals.items()},
            "total": _output_money(cost_total),
            "overlap_rule": "entered proof-of-funds and planned costs are added; confirm with the source whether any amounts overlap",
        },
        "target": {
            "date": target_date.isoformat() if target_date else None,
            "status": target_status,
            "months_remaining": timeline_months,
        },
        "assessment": {
            "status": status,
            "combined_target": _output_money(combined_target),
            "funding_gap": _output_money(gap),
            "surplus": _output_money(surplus),
            "monthly_savings_target": _output_money(monthly_target),
            "currency_mismatch": bool(mismatches),
            "currency_mismatches": mismatches,
            "planning_only": True,
        },
        "warnings": warnings,
        "safety_note": "This is a planning calculation based on entered and route-estimate figures, not proof of eligibility or approval. Verify current official requirements, family rules, acceptable evidence, holding periods, and whether cost categories overlap before applying, paying, booking, or moving money.",
    }
