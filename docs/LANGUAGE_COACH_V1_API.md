# Language Coach V1 API Contract

Planned authenticated endpoints under `/api/language-coach`:

- `GET /options` — English, French, Both; IELTS General and TEF Canada launch exams; future-exam capability.
- `GET /profile` — current learning preferences and targets.
- `PATCH /profile` — save language choice, 50/50 or 70/30 allocation, daily target and CLB/NCLC goals.
- `GET /diagnostic` — diagnostic question set.
- `POST /attempts` — record an answer, explanation result and spaced-review update.
- `GET /practice` — adaptive practice items without exposing answer keys.
- `GET /mistakes` — due/previous mistake review queue.
- `GET /progress` — accuracy, consistency and readiness state.
- `GET /daily` — 1–5 minute daily challenge assembled from due reviews and adaptive new material.

Security rules: account-owned records must be isolated by authenticated account ID; public practice content is read-only; answer keys are never returned by question-fetch endpoints; admin/content workflows must preserve source provenance. V1 content is MoveReady-original or legally permitted official material only.
