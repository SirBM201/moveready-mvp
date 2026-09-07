# V1 — AI Mobility Assistant

Status: **Required for V1 launch**

MoveReady must launch with a context-aware AI Mobility Assistant so users are guided through the Opportunity-to-Mobility journey rather than being left to interpret vacancies, qualification evidence, readiness gaps and execution workflows alone.

## V1 objective

A user should be able to explain a mobility/career goal in ordinary language and receive contextual guidance based on available MoveReady data, with a clear next action.

## V1 minimum capabilities

- Explain discovered opportunities and why they may or may not fit the user's profile.
- Explain qualification evidence, sponsorship evidence and uncertainty without presenting unverified claims as facts.
- Explain readiness gaps and prioritize practical next steps.
- Guide the user through profile/readiness setup, opportunity review, Career Studio, alignment and application workflows available in V1.
- Explain application status, alerts and relevant failure states.
- Use the user's available MoveReady context instead of behaving like a generic relocation chatbot.
- Distinguish informational guidance from legal/immigration advice and surface evidence/source dates where applicable.
- Never fabricate vacancies, sponsorship, eligibility, employer intent or application outcomes.
- Require user authorization before consequential submission or external action.

## Architecture principle

**User ↔ AI Mobility Assistant ↔ MoveReady qualification/readiness/opportunity/execution engines ↔ results/actions**

## V1 AI cost guardrail

MoveReady must route every assistant request through the least expensive reliable path:

**Database/rules → cached/approved knowledge → low-cost AI → advanced AI**

- Deterministic profile, opportunity, status, navigation and stored evidence queries should not consume LLM inference unnecessarily.
- Cache safe reusable explanations where freshness/privacy permit.
- Minimize model context and retrieve only relevant user/opportunity evidence.
- Use economical models for simple guidance/explanation and stronger models only for complex qualification, alignment or reasoning tasks.
- Enforce plan-aware quotas/rate limits and abuse controls.
- Record usage/cost telemetry by user/model/task and support configurable cost ceilings.
- Gracefully fall back to deterministic guidance when AI budget is exhausted.
- Cost optimization must never weaken evidence integrity, qualification safeguards or user safety.

This is a **V1 launch requirement**.

## V1 acceptance

MoveReady V1 is not considered complete if the major user journey is technically available but a normal user can become stranded without contextual in-product guidance. V1 also requires AI cost routing, usage controls and measurable inference-cost telemetry.