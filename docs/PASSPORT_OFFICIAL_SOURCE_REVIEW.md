# Passport official-source review lifecycle

Stage 2F.5D.3 turns the Passport Index official-source layer into a controlled review system.

## Trust rule

A provider response is never promoted to official evidence. Only a mapping to an active `government` or `embassy` record in `relocation_trusted_sources` can become MoveReady-verified.

Mappings remain `pending_review` until a controlled review decision is recorded. A verified mapping carries a review deadline; once that deadline passes it must fail closed to `needs_review` before being represented as verified.

## Verification checklist

Before choosing `verified`, the reviewer must confirm all of the following:

1. The URL is HTTPS and is the exact URL stored on the mapped trusted-source record.
2. The publisher is a government department, ministry, immigration authority, embassy, or an official platform explicitly linked/endorsed by that authority.
3. The page materially covers the mapping purpose (for example entry requirements or visa requirements).
4. The page is reachable and current enough to support the Passport destination result.
5. The evidence note identifies what was checked; a bare statement such as `looks valid` is not sufficient.

Use `needs_review` when authority, ownership, scope, freshness, or URL continuity cannot be established. Use `retired` when the mapping should no longer be served.

## Seed review checkpoint — 2026-08-17

The 037 seed created four candidates: Canada, Germany, Benin, and Seychelles. Independent authority checks on 2026-08-17 established strong evidence for Canada, Germany, and Seychelles. Benin remains intentionally `pending_review` until the official ownership/authority chain for the seeded e-Visa URL can be established to the same standard.

No migration silently promotes these rows. Promotion must occur through `relocation_review_passport_official_source_mapping`, which records the reviewer, evidence note, exact URL, previous state, decision, timestamp, and next review deadline.

## Operational cadence

Run `relocation_expire_passport_official_source_reviews()` from a backend/service-role governance job before or during source-governance checks. It converts overdue `verified` mappings to `needs_review`. The public Passport response already treats only `verification_status=verified` as MoveReady-verified.
