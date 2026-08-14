from app.services.language_coach import adaptive_difficulty, build_learning_plan, placement_level


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


def test_placement_is_conservative_and_bounded():
    assert placement_level(0, 0) == 0
    assert placement_level(2, 10) == 1
    assert placement_level(4, 10) == 2
    assert placement_level(6, 10) == 3
    assert placement_level(8, 10) == 4
    assert placement_level(9, 10) == 5


def test_adaptive_difficulty_moves_up_after_strong_recent_work():
    attempts = [{"difficulty": 2, "is_correct": True} for _ in range(8)] + [{"difficulty": 2, "is_correct": False} for _ in range(2)]
    assert adaptive_difficulty(attempts) == 3


def test_adaptive_difficulty_moves_down_after_weak_recent_work():
    attempts = [{"difficulty": 4, "is_correct": False} for _ in range(6)] + [{"difficulty": 4, "is_correct": True} for _ in range(4)]
    assert adaptive_difficulty(attempts) == 3


def test_adaptive_difficulty_never_exceeds_bounds():
    assert adaptive_difficulty([{"difficulty": 5, "is_correct": True} for _ in range(10)]) == 5
    assert adaptive_difficulty([{"difficulty": 1, "is_correct": False} for _ in range(10)]) == 1
