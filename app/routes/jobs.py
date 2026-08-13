from __future__ import annotations

# Career Realism V1 API contract note:
# Migration 034 adds search_scope, current_country and work_authorized_countries.
# The full existing Jobs routes remain on main until that migration is applied.

# This branch intentionally stages the public contract constants independently so
# Railway production remains compatible with the pre-034 schema.

SEARCH_SCOPES = ["local", "international", "both"]
WORK_AUTHORIZATION_STATUSES = ["citizen", "permanent_resident", "open_permit", "employer_specific_permit", "requires_sponsorship", "not_recorded"]

# See main:app/routes/jobs.py for the production route implementation.
# Do not merge this staging file before Migration 034 and the complete route
# implementation have been validated together.
