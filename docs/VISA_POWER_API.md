# Visa Power API

## Purpose

Visa Power and Travel Benefits checks whether visas a user already holds may create extra travel opportunities in third countries.

This supports the MoveReady passport-index direction without turning the product into a generic travel site.

## Endpoints

### GET `/api/visa-power/options`

Returns accepted existing-visa codes and a safety note.

### POST `/api/visa-power/check`

Example payload:

```json
{
  "passport_country": "Nigeria",
  "held_visas": ["canada_visitor"],
  "multiple_entry_confirmed": true,
  "visa_used_before_confirmed": false
}
```

Returns:

- Passport country
- Held visa codes
- Visa opportunity score
- Matched destination count
- Matched rules
- Official source name and URL
- Last verified date
- Conditions
- Safety note

## Starter rule records

The current static API includes starter records for:

- Mexico
- Dominican Republic
- Panama
- Costa Rica

These records must still be treated as official-source-first planning guidance, not travel approval.

## Important safety rule

The API must never say that entry is guaranteed.

Every result should preserve this logic:

- Confirm official destination rules before travel.
- Confirm airline and transit requirements before buying tickets.
- Confirm visa validity, multiple-entry status, and previous-use conditions where applicable.
- Border officers still decide entry.

## Future database direction

Move the static rule records into Supabase tables when the feature becomes a paid product:

- `visa_power_documents`
- `visa_power_destination_rules`
- `visa_power_rule_sources`
- `visa_power_user_checks`
- `visa_power_watchlist`

Each rule should include reviewer status, last verified date, source URL, confidence level, and change history.
