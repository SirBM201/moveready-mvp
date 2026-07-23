# MoveReady Database Trust Invariants

Run `supabase/migrations/026_commercial_and_handoff_invariants.sql` after migrations 023 through 025.

Migration 026 adds database constraints that prevent application code, admin tools, or manual SQL from bypassing the following rules:

- A provider cannot be publicly listed unless its application is approved and privacy, pricing, refund, sensitive-document handling, and affiliate-disclosure controls pass.
- A commercial quote total must equal the service subtotal plus the MoveReady platform fee.
- Accepted, payment-pending, paid, fulfilled, refunded, or disputed quote states require an auditable acceptance record and the relevant lifecycle timestamps.
- A provider handoff cannot reach consent-confirmed or later states without exact-field user consent.
- A provider handoff cannot reach shared or later states without a sharing timestamp, delivery channel, and delivery reference.
- A completed handoff requires a completion timestamp.
- A resolved, rejected, or closed support case requires a written resolution summary and resolution timestamp.

Apply migrations in this order:

1. `023_provider_publication_and_commercial_quotes.sql`
2. `024_private_backend_tables_rls.sql`
3. `025_service_handoffs_and_support_cases.sql`
4. `026_commercial_and_handoff_invariants.sql`

Before applying migration 026 to a database that already contains commercial or handoff records, use the protected admin consoles to repair incomplete legacy records. Existing rows that violate the new constraints will cause PostgreSQL to reject the migration instead of silently accepting unsafe state.
