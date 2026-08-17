# MoveReady B07 — Language Coach backend completion

Status: implementation and acceptance contract.

## Batch boundary

B07 completes the current Language Coach backend without wholesale-merging stale PR #10. The canonical `relocation_language_*` tables and existing authenticated routes are preserved. The stale PR's parallel `language_*` schema is not introduced.

B08 live frontend integration and UX acceptance remain outside this batch.

## B07 contract

- User choice remains `english`, `french`, or `both`.
- `both` uses the supported 50/50, 70/30, or 30/70 allocation presets.
- Launch exam foundations remain IELTS General and TEF Canada.
- Diagnostic completion requires at least six distinct answered questions before an internal placement level can be stored.
- Saving a profile cannot self-award or overwrite diagnostic placement.
- Practice, adaptive practice, daily challenge, attempts, mistakes, review, progress, and qualification actions require a verified account session.
- Question-fetch routes never expose answer keys or explanations before an answer is recorded.
- Practice content must be MoveReady-original or a permitted official release with HTTPS provenance.
- Recalled, leaked, or reconstructed live exam content is prohibited.
- Placement, readiness, momentum, and accuracy are internal practice indicators, not official IELTS, TEF, CLB, or NCLC results.

The public options response exposes `contract_version=b07-v1` and the answer-key, content, allocation, and score boundaries.

## Canonical API

Public, non-mutating contract routes:

- `GET /api/language-coach/options`
- `GET /api/language-coach/catalog`
- `POST /api/language-coach/plan`

Verified-account routes:

- `GET|PUT|PATCH /api/language-coach/profile`
- `GET /api/language-coach/diagnostic`
- `POST /api/language-coach/diagnostic/complete`
- `GET /api/language-coach/practice`
- `GET /api/language-coach/adaptive-practice`
- `GET /api/language-coach/daily-challenge`
- `POST /api/language-coach/attempts`
- `GET /api/language-coach/mistakes`
- `GET /api/language-coach/review`
- `GET /api/language-coach/progress`
- `GET /api/language-coach/qualification-actions`

## Database decision

Migration `039_language_coach_backend_completion.sql` hardens the existing schema rather than creating a duplicate data model. It:

- verifies that the five canonical Language Coach tables exist;
- keeps row-level security enabled;
- revokes direct `public`, `anon`, and `authenticated` table privileges;
- grants the backend `service_role` access;
- constrains saved allocations, question choice shape, official-release HTTPS provenance, and response-duration bounds;
- adds no anonymous or user-table policies.

Apply prerequisites `034_language_coach_v1.sql` and `035_language_coach_starter_bank.sql` only if the five canonical tables or starter questions are absent. Then apply migration 039 once. Do not apply stale PR #10's `035_language_coach_v1.sql` because it creates a conflicting schema.

No Railway environment variable or new secret is required for B07.

## Automated acceptance

Run:

```bash
python -m compileall -q app
python -m unittest discover -s tests -p "test_language_coach*.py" -v
```

GitHub Actions workflow `Language Coach Integration` also verifies:

- registered B07 routes and build-info contract;
- anonymous privacy barriers;
- allocation and payload validation;
- conservative diagnostic completion;
- answer-key withholding and runtime content provenance;
- canonical schema use;
- migration 039 RLS, privilege, provenance, and duration safeguards.

## Production acceptance to perform later

1. Confirm the five canonical tables and at least one active English and French original practice question.
2. Apply migration 039 after its prerequisites are present.
3. Sign in with a controlled verified account.
4. Save English, French, and Both plans, including each supported allocation.
5. Confirm an incomplete diagnostic cannot store placement.
6. Complete at least six diagnostic answers and confirm an internal 0–5 placement is stored.
7. Confirm practice, one wrong-answer mistake, due review, adaptive practice, daily challenge, and progress load without exposing another account's records.
8. Confirm the UI never represents an internal indicator as an official exam result.

Do not paste an OTP, session token, answer history, or private account data into chat, screenshots, issues, logs, or repository files.
