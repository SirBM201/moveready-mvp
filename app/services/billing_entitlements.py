from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.supabase_client import get_supabase

PRODUCT_CODE = "moveready"
ACTIVE_SUBSCRIPTION_STATES = {"active", "trialing"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def get_or_create_customer(email: str) -> Dict[str, Any]:
    normalized = str(email or "").strip().lower()
    if not normalized:
        raise ValueError("billing_customer_email_required")
    db = get_supabase()
    found = db.table("billing_customers").select("*").eq("account_email", normalized).maybe_single().execute().data
    if found:
        return found
    response = db.table("billing_customers").insert({"account_email": normalized}).execute()
    rows = response.data or []
    if not rows:
        # Concurrent creation can win the unique constraint; resolve canonical row.
        found = db.table("billing_customers").select("*").eq("account_email", normalized).maybe_single().execute().data
        if found:
            return found
        raise RuntimeError("billing_customer_creation_failed")
    return rows[0]


def list_active_entitlements(email: str, product_code: str = PRODUCT_CODE) -> List[Dict[str, Any]]:
    customer = get_or_create_customer(email)
    rows = (
        get_supabase().table("billing_entitlements").select("*")
        .eq("customer_id", customer["id"])
        .eq("product_code", product_code)
        .eq("status", "active")
        .execute().data or []
    )
    now = _now()
    return [row for row in rows if not _parse_time(row.get("ends_at")) or _parse_time(row.get("ends_at")) > now]


def has_entitlement(email: str, feature_code: str, product_code: str = PRODUCT_CODE) -> bool:
    feature = str(feature_code or "").strip()
    if not feature:
        return False
    return any(str(row.get("feature_code")) == feature for row in list_active_entitlements(email, product_code))


def account_billing_state(email: str) -> Dict[str, Any]:
    customer = get_or_create_customer(email)
    db = get_supabase()
    subscriptions = (
        db.table("billing_subscriptions").select("*,billing_plans(code,name)")
        .eq("customer_id", customer["id"])
        .order("created_at", desc=True).limit(20).execute().data or []
    )
    entitlements = list_active_entitlements(email)
    active = next((s for s in subscriptions if str(s.get("status")) in ACTIVE_SUBSCRIPTION_STATES), None)
    return {
        "customer_id": customer["id"],
        "account_email": customer["account_email"],
        "active_subscription": active,
        "subscriptions": subscriptions,
        "entitlements": entitlements,
        "feature_codes": sorted({str(row.get("feature_code")) for row in entitlements if row.get("feature_code")}),
    }
