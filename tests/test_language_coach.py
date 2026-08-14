from app.services.language_coach import build_learning_plan


def test_both_languages_respects_user_allocation():
    plan = build_learning_plan({"language_selection": "both", "allocation": {"english": 70}, "daily_minutes": 20, "diagnostic": {"english": 5, "french": 3}, "targets": {"english": 7, "french": 7}})
    assert plan["allocation"] == {"english": 70, "french": 30}
    assert [item["exam"] for item in plan["languages"]] == ["IELTS General", "TEF Canada"]
    assert plan["languages"][0]["gap"] == 2
    assert plan["languages"][1]["gap"] == 4


def test_french_is_never_forced_for_english_choice():
    plan = build_learning_plan({"language_selection": "english", "allocation": {"english": 30}, "diagnostic": {"english": 7, "french": 10}})
    assert plan["allocation"] == {"english": 100, "french": 0}
    assert len(plan["languages"]) == 1
    assert plan["languages"][0]["language"] == "english"


def test_missed_day_policy_is_non_punitive():
    plan = build_learning_plan({"language_selection": "french"})
    assert "does not erase" in plan["momentum_policy"]
