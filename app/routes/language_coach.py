from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.language_coach import build_learning_plan

bp = Blueprint("language_coach", __name__)


@bp.get("/catalog")
def catalog():
    return jsonify({
        "ok": True,
        "language_choices": ["english", "french", "both"],
        "allocation_presets": [
            {"english": 50, "french": 50},
            {"english": 70, "french": 30},
            {"english": 30, "french": 70},
        ],
        "initial_exams": {"english": ["IELTS General"], "french": ["TEF Canada"]},
        "architecture_ready_for": {"english": ["CELPIP", "PTE Core"], "french": ["TCF Canada"]},
        "v1_capabilities": ["diagnostic", "personalized_plan", "microlearning", "practice_bank", "mistakes_bank", "spaced_repetition", "adaptive_difficulty", "progress_tracking", "CLB/NCLC_targets"],
    })


@bp.post("/plan")
def plan():
    payload = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "plan": build_learning_plan(payload)})
