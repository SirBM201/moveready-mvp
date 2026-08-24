from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_application_analytics import CONTRACT_VERSION, attribution_breakdown, metrics
from app.services.job_application_portfolio_loader import load_account_portfolio

bp = Blueprint("job_application_analytics", __name__)
ALLOWED_DIMENSIONS = ("country", "occupation", "employer", "source")


def _account():
    email = get_verified_session_email()
    if not email:
        return None, (jsonify({"ok": False, "error": "verified_session_required"}), 401)
    return email, None


@bp.get("/application-analytics")
def application_analytics():
    email, error = _account()
    if error:
        return error
    items = load_account_portfolio(email)
    result = metrics(items)
    return jsonify({
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "metrics": result,
        "portfolio_count": len(items),
        "safety": {
            "descriptive_only": True,
            "employer_feedback_inferred": False,
            "ranking_modified": False,
            "application_submission_performed": False,
        },
    })


@bp.get("/application-analytics/attribution")
def application_analytics_attribution():
    email, error = _account()
    if error:
        return error
    dimension = str(request.args.get("dimension") or "source").strip().lower()
    if dimension not in ALLOWED_DIMENSIONS:
        return jsonify({"ok": False, "error": "unsupported_attribution_dimension", "allowed": list(ALLOWED_DIMENSIONS)}), 400
    items = load_account_portfolio(email)
    return jsonify({
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "dimension": dimension,
        "breakdown": attribution_breakdown(items, dimension),
        "portfolio_count": len(items),
    })


@bp.get("/application-analytics/funnel")
def application_analytics_funnel():
    email, error = _account()
    if error:
        return error
    items = load_account_portfolio(email)
    result = metrics(items)
    return jsonify({
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "funnel": result["funnel"],
        "rates": result["rates"],
        "terminal_outcomes": result["terminal_outcomes"],
        "applications_tracked": result["applications_tracked"],
    })
