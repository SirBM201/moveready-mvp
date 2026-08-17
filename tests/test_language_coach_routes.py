from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from app.routes import language_coach, language_coach_extension


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.columns = "*"
        self.filters = []
        self.order_column = None
        self.order_desc = False
        self.limit_value = None
        self.operation = "select"
        self.values = None

    def select(self, columns):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        return self

    def is_(self, column, value):
        self.filters.append(("is", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, set(values)))
        return self

    def order(self, column, desc=False):
        self.order_column = column
        self.order_desc = desc
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def insert(self, values):
        self.operation = "insert"
        self.values = dict(values)
        return self

    def update(self, values):
        self.operation = "update"
        self.values = dict(values)
        return self

    def _matches(self, row):
        for operation, column, value in self.filters:
            actual = row.get(column)
            if operation == "eq" and actual != value:
                return False
            if operation == "lte" and (actual is None or actual > value):
                return False
            if operation == "is" and value == "null" and actual is not None:
                return False
            if operation == "in" and actual not in value:
                return False
        return True

    def _project(self, rows):
        if self.columns == "*":
            return [deepcopy(row) for row in rows]
        columns = [column.strip() for column in self.columns.split(",")]
        return [
            {column: deepcopy(row.get(column)) for column in columns}
            for row in rows
        ]

    def execute(self):
        table = self.database.rows.setdefault(self.table_name, [])
        if self.operation == "insert":
            row = deepcopy(self.values)
            self.database.counter += 1
            row.setdefault("id", f"{self.table_name}-{self.database.counter}")
            if self.table_name == "relocation_language_attempts":
                row.setdefault("attempted_at", datetime.now(timezone.utc).isoformat())
            table.append(row)
            return SimpleNamespace(data=[deepcopy(row)])

        matches = [row for row in table if self._matches(row)]
        if self.operation == "update":
            updated = []
            for row in matches:
                row.update(deepcopy(self.values))
                updated.append(deepcopy(row))
            return SimpleNamespace(data=updated)

        if self.order_column:
            matches.sort(
                key=lambda row: (row.get(self.order_column) is not None, row.get(self.order_column)),
                reverse=self.order_desc,
            )
        if self.limit_value is not None:
            matches = matches[: self.limit_value]
        return SimpleNamespace(data=self._project(matches))


class FakeSupabase:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.counter = 100

    def table(self, table_name):
        return FakeQuery(self, table_name)


def question(index, difficulty):
    return {
        "id": f"question-{index}",
        "language": "english",
        "exam": "IELTS General",
        "skill": "grammar" if index % 2 else "reading",
        "difficulty": difficulty,
        "prompt": f"Original practice question {index}",
        "choices": ["Correct", "Incorrect"],
        "correct_answer": "Correct",
        "explanation": "Original MoveReady explanation.",
        "content_origin": "moveready_original",
        "source_url": None,
        "is_active": True,
    }


class LanguageCoachRouteTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeSupabase({
            "relocation_language_profiles": [],
            "relocation_language_questions": [
                question(1, 1),
                question(2, 1),
                question(3, 2),
                question(4, 2),
                question(5, 3),
                question(6, 3),
                {
                    **question(7, 1),
                    "content_origin": "official_released",
                    "source_url": "http://untrusted.example/question",
                },
            ],
            "relocation_language_attempts": [],
            "relocation_language_mistakes": [],
            "relocation_language_daily_progress": [],
        })
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="b07-route-tests")
        self.app.register_blueprint(language_coach.bp, url_prefix="/api/language-coach")
        self.app.register_blueprint(language_coach_extension.bp, url_prefix="/api/language-coach")
        self.client = self.app.test_client()
        self.patchers = [
            patch.object(language_coach, "get_supabase", lambda: self.database),
            patch.object(language_coach_extension, "get_supabase", lambda: self.database),
            patch.object(language_coach, "get_verified_session_email", lambda: "learner@example.com"),
            patch.object(language_coach_extension, "get_verified_session_email", lambda: "learner@example.com"),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()

    def test_catalog_exposes_b07_contract_and_plan_validation(self):
        options = self.client.get("/api/language-coach/options")
        self.assertEqual(options.status_code, 200)
        payload = options.get_json()
        self.assertEqual(payload["contract_version"], "b07-v1")
        self.assertEqual(payload["language_choices"], ["english", "french", "both"])
        self.assertEqual(payload["answer_key_policy"], "withheld_until_answer_recorded")

        invalid = self.client.post(
            "/api/language-coach/plan",
            json={
                "language_selection": "both",
                "allocation": {"english": 60, "french": 40},
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["error"], "unsupported_allocation")

    def test_private_routes_reject_anonymous_requests(self):
        with patch.object(language_coach, "get_verified_session_email", lambda: None), patch.object(
            language_coach_extension,
            "get_verified_session_email",
            lambda: None,
        ):
            for path in (
                "/api/language-coach/profile",
                "/api/language-coach/practice",
                "/api/language-coach/diagnostic",
                "/api/language-coach/adaptive-practice",
                "/api/language-coach/daily-challenge",
                "/api/language-coach/mistakes",
                "/api/language-coach/review",
                "/api/language-coach/progress",
            ):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 401)

    def test_profile_update_cannot_self_award_diagnostic_placement(self):
        self.database.rows["relocation_language_profiles"].append({
            "id": "profile-1",
            "email": "learner@example.com",
            "language_selection": "english",
            "english_allocation": 100,
            "french_allocation": 0,
            "daily_minutes": 20,
            "english_current_level": 2,
            "french_current_level": 0,
            "english_target_level": 7,
            "french_target_level": 7,
        })
        response = self.client.put(
            "/api/language-coach/profile",
            json={
                "language_selection": "english",
                "diagnostic": {"english": 12},
                "targets": {"english": 8},
            },
        )
        self.assertEqual(response.status_code, 200)
        saved = response.get_json()["profile"]
        self.assertEqual(saved["english_current_level"], 2)
        self.assertEqual(saved["english_target_level"], 8)

    def test_question_fetch_withholds_answers_and_filters_bad_provenance(self):
        response = self.client.get(
            "/api/language-coach/practice?language=english&difficulty=1"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["answer_key_withheld"])
        self.assertEqual(len(payload["questions"]), 2)
        self.assertNotIn("correct_answer", payload["questions"][0])
        self.assertNotIn("explanation", payload["questions"][0])

        invalid = self.client.get(
            "/api/language-coach/practice?language=english&difficulty=hard"
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["error"], "invalid_difficulty")

    def test_diagnostic_fails_closed_until_minimum_is_attempted(self):
        diagnostic = self.client.get("/api/language-coach/diagnostic?language=english").get_json()
        question_ids = [item["id"] for item in diagnostic["questions"]]
        self.assertEqual(len(question_ids), 6)
        first = self.client.post(
            "/api/language-coach/attempts",
            json={"question_id": question_ids[0], "answer": "Correct"},
        )
        self.assertEqual(first.status_code, 200)

        incomplete = self.client.post(
            "/api/language-coach/diagnostic/complete",
            json={"language": "english", "question_ids": question_ids},
        )
        self.assertEqual(incomplete.status_code, 400)
        self.assertEqual(incomplete.get_json()["error"], "diagnostic_incomplete")
        self.assertEqual(incomplete.get_json()["required_attempts"], 6)
        self.assertEqual(self.database.rows["relocation_language_profiles"], [])

    def test_completed_diagnostic_persists_internal_placement(self):
        diagnostic = self.client.get("/api/language-coach/diagnostic?language=english").get_json()
        question_ids = [item["id"] for item in diagnostic["questions"]]
        for question_id in question_ids:
            attempt = self.client.post(
                "/api/language-coach/attempts",
                json={
                    "question_id": question_id,
                    "answer": "Correct",
                    "response_seconds": 30,
                },
            )
            self.assertEqual(attempt.status_code, 200)

        completed = self.client.post(
            "/api/language-coach/diagnostic/complete",
            json={"language": "english", "question_ids": question_ids},
        )
        self.assertEqual(completed.status_code, 200)
        payload = completed.get_json()
        self.assertEqual(payload["placement_level"], 5)
        self.assertIn("not_official", payload["purpose"])
        profile = self.database.rows["relocation_language_profiles"][0]
        self.assertEqual(profile["english_current_level"], 5)


if __name__ == "__main__":
    unittest.main()
