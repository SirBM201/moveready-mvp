# MoveReady Account and Login Design

Date: 2026-06-19
Status: MVP design note

## Purpose

MoveReady should treat account identity as the layer that connects a user's relocation profile, saved routes, watchlist alerts, timeline events, generated reports, and service requests.

The product should not feel like a visa agent or shortcut platform. Account features must remain consent-first, source-aware, and transparent about risk.

## Phase 1: Contact-Based Identity

Use email or phone lookup for the MVP.

This is already useful because users can:

- save a relocation profile;
- retrieve saved routes by email or phone;
- retrieve readiness reports by report reference, email, or phone;
- create watchlist alerts with consent;
- create timeline events with reminder preferences;
- submit service requests with consent.

Rules:

- require either email or phone before saving user-owned records;
- require consent before contacting the user or sending alerts;
- do not expose service requests, documents, or private profile data publicly;
- keep admin-only access protected by the admin key until a proper admin login exists.

## Phase 2: Email OTP Login

Add backend-managed email OTP login.

Recommended flow:

1. User enters email.
2. Backend creates a short-lived login code.
3. Backend sends code by approved email provider.
4. User submits code.
5. Backend verifies code and creates a session token.
6. Frontend stores the session token and uses it for account-owned requests.

Recommended records to connect to verified identity:

- relocation profiles;
- saved routes;
- watchlist subscriptions;
- timeline events;
- generated reports;
- service requests;
- future payments and report refresh history.

Security rules:

- never expose Supabase service-role keys in the frontend;
- hash or safely store OTP codes;
- expire OTP codes quickly;
- rate-limit OTP requests and verification attempts;
- allow session revocation;
- keep admin endpoints separate from normal user sessions unless/until role-based admin login is designed.

## Phase 3: Paid Account Features

After login is stable, add commercial account features:

- paid readiness reports;
- premium watchlist monitoring;
- expert review requests;
- provider handoff tracking;
- report refresh history;
- downloadable PDF report exports;
- service request status history.

Paid features must still avoid approval guarantees. Reports and service flows should show source version, risk label, generated date, and any review due date where relevant.

## Account Center Product Map

The `/dashboard` page should operate as the Account Center.

It should connect:

1. Relocation profile
2. Saved routes
3. Watchlist alerts
4. Timeline
5. My reports
6. Service requests

Preferred user journey:

Profile -> route -> report -> alert -> service

## Trust Controls

Every account feature should follow these controls:

- no visa, admission, lottery, ballot, or job approval guarantees;
- official-source-first guidance;
- visible risk labels and report generated dates;
- source confidence and source review due dates where available;
- provider screening before handoff;
- opt-in alerts only;
- private user records should never be exposed publicly.
