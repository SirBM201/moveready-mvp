# B14 — Smart alerts and critical monitoring

## Delivered contract

`GET /api/account/smart-alerts` is a verified-account, read-only alert inbox with contract version `b14-v1`.

It consolidates and ranks actionable signals already held by MoveReady:

- official-source job monitoring and private job follow-ups;
- application deadlines and follow-ups;
- passport, visa and other document expiry metadata;
- relevant reviewed watchlist openings, deadlines and source-review changes;
- optional language-review reminders;
- stale evidence-pack refresh reminders.

Stable SHA-256 alert keys remove duplicates without creating a second alert database. Critical signals rank before high, medium and low signals; alerts at the same level use the nearest deadline first.

## Preference controls

The existing `relocation_account_preferences.metadata` JSON column now stores a bounded `smart_alerts` object. This is migration-free and preserves all unrelated metadata.

Defaults are deliberately quiet:

- job, application follow-up and evidence refresh alerts are enabled;
- language reminders are opt-in;
- the in-app master switch and existing source, opportunity, application and document switches remain authoritative;
- configurable day thresholds are validated and bounded server-side.

`PUT /api/account/preferences` accepts `smart_alert_preferences` and records consent version `moveready-account-preferences-v2`.

## Safety boundary

B14 does not:

- upload or expose a raw document or complete document/reference number;
- scrape a private authority account;
- create or submit an application;
- treat source freshness as proof that a rule is unchanged;
- treat a reminder as an official deadline or decision;
- activate email, WhatsApp, SMS, Telegram, push or any other external delivery.

Partial upstream failures return stable `source_unavailable` markers. Raw database errors are logged server-side and are not returned to the browser.

## Deployment check

After Railway deploys the merged backend commit:

```powershell
$Build = Invoke-RestMethod "https://moveready-mvp-production.up.railway.app/api/build-info"
$Build.contract_versions.smart_alerts
$Build.route_contract.ok
```

Expected results are `b14-v1` and `True`. The authenticated alert inbox is then exercised by the B14 frontend.
