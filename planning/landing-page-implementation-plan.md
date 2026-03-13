# Production Landing Page Implementation Plan

## Table of Contents

- [Purpose](#purpose)
- [Project Context](#project-context)
- [Wave Goal](#wave-goal)
- [Non-Goals](#non-goals)
- [Architecture Decision Summary](#architecture-decision-summary)
- [IaC And Automation Strategy](#iac-and-automation-strategy)
- [Public Product Surface For This Wave](#public-product-surface-for-this-wave)
- [Backend And API Plan](#backend-and-api-plan)
- [Data Model Plan](#data-model-plan)
- [Supabase Auth Strategy](#supabase-auth-strategy)
- [Production And Staging Data Strategy](#production-and-staging-data-strategy)
- [Seed And Reset Guardrails](#seed-and-reset-guardrails)
- [Email And Mailing Integration Plan](#email-and-mailing-integration-plan)
- [Testing And Verification Plan](#testing-and-verification-plan)
- [Implementation Sequence](#implementation-sequence)
- [Open Decisions For Review](#open-decisions-for-review)
- [Reference Links](#reference-links)

## Purpose

This document defines the technical implementation plan for the production landing-page-only wave for Board Enthusiasts.

It is written for the implementation owner and any async engineering collaborators who need enough context to make compatible changes without re-reading the full repository history.

## Project Context

Board Enthusiasts (BE) is building an independent platform for third-party Board developers and players.

Current maintained stack:

- frontend: React + TypeScript SPA in `frontend/`
- backend: Cloudflare Workers API in `backend/apps/workers-api/`
- auth, relational data, storage: Supabase in `backend/supabase/`
- repo orchestration: `python ./scripts/dev.py ...`

Current repository rules that matter here:

- new externally visible features follow API-first and TDD ordering
- backend-visible behavior starts in the contract and tests
- keep the maintained stack aligned to Cloudflare + Supabase + React
- avoid throwaway parallel systems that will have to be removed immediately after launch

## Wave Goal

Ship a production landing page on `boardenthusiasts.com` that:

- reuses the current BE visual system
- exposes only landing-page content, not the full in-progress app navigation
- captures email signups for launch updates and future MVP invites
- stores those signups in a product-owned model that can later connect to real BE accounts
- integrates with BE email infrastructure and marketing tooling without locking the app into a dead-end data model

## Non-Goals

This wave should not:

- release the full authenticated product experience publicly
- expose catalog/developer/player navigation on production
- create a complete internal admin CRM
- build a full marketing automation engine
- turn waitlist signups into full product accounts immediately
- mirror the entire production auth system into staging automatically

## Architecture Decision Summary

Recommended direction:

- landing page lives in the existing frontend app
- production uses a landing-only mode flag so the site can expand later without a separate codebase
- signup submission is a maintained backend feature, not a third-party embedded form
- waitlist and marketing interest data lives in the BE database
- Brevo is an integration target for campaign sending, not the system of record

Important decision:

- do **not** create Supabase Auth users at landing-page signup time

Rationale:

- the current `app_users` table requires a real `auth_user_id`
- waitlist signups are not yet product accounts
- pre-creating auth users for everyone adds account-lifecycle complexity before users have chosen to join
- unsubscribe, deletion, resend, and staging/test flows are all cleaner when a signup remains a marketing/contact record until invite or conversion

Supabase does support later invitation flows through the admin API. That capability should be used when a waitlist contact is selected for staging or MVP onboarding, not at initial signup.

## IaC And Automation Strategy

Use the repo as the control plane wherever practical after the initial provider bootstrap.

### Keep In Repository

- frontend landing page source and environment gating
- OpenAPI/Postman contract additions for the public signup endpoint
- backend Worker endpoint and service-layer behavior
- Supabase SQL migrations and policies
- Supabase email templates
- deployment templates and root deployment orchestration
- integration tests, browser smoke tests, and contract tests
- provisioning scripts for Brevo list/contact sync and optionally campaign/template bootstrap

### Manual Bootstrap Only

- provider account creation
- Cloudflare zone onboarding
- Supabase project creation
- Brevo account/domain verification
- Gmail alias verification

### Pragmatic Recommendation

Do not introduce Terraform in this wave unless the team explicitly wants to manage Cloudflare DNS and Email Routing that way immediately.

Reason:

- the repo already has Cloudflare and Supabase deployment templates, Wrangler configuration, and root automation
- Terraform would be additive operational complexity right when speed matters most
- account bootstrap and Gmail verification remain manual either way

If infrastructure drift becomes painful after launch, add a small targeted IaC layer later rather than blocking this wave on a new stack.

## Public Product Surface For This Wave

Production route behavior should be intentionally narrow.

Recommended public production surface:

- `/` landing page
- `/updates` or equivalent static content route if ready
- footer legal/privacy routes if required

Recommended behavior:

- hide or disable internal app navigation in production landing mode
- keep the shared shell, tokens, fonts, and background system
- link out to Discord and the public GPT
- expose one waitlist/signup form

Implementation suggestion:

- add a runtime config flag such as `VITE_LANDING_MODE=true` for production
- keep staging and local environments able to exercise the full SPA when needed

## Backend And API Plan

This wave adds one maintained landing-page signup capability:

- BE-owned website waitlist/marketing signup submission

Recommended web-only surface:

- `POST /marketing/signups`

This route should not be treated as part of the third-party developer-facing public API. It is an internal browser-facing endpoint intended only for the BE web properties.

Recommended request fields:

- `email`
- `firstName` optional
- `source`
- `consentTextVersion`
- `turnstileToken`
- `utm` object optional

Recommended response shape:

- `accepted`
- `duplicate`
- `message`

Behavior:

1. Validate the email and normalize it.
2. Verify Turnstile server-side.
3. Upsert the contact into a BE-owned table.
4. Record consent metadata and source metadata.
5. Best-effort sync the contact into Brevo.
6. Optionally send a notification email to `matt@mattstroman.com`.
7. Return a success response that does not leak unnecessary internals.

Recommendation:

- treat duplicate signups as success
- update timestamps/source metadata instead of erroring on repeat submissions

## Data Model Plan

### Core Decision

Do not store waitlist signups in `public.app_users`.

Current reality:

- `public.app_users.auth_user_id` is required and unique
- `public.app_users` represents users who actually exist in Supabase Auth

Waitlist signups need a distinct model.

### Recommended New Tables

#### `public.marketing_contacts`

Purpose:

- canonical system-of-record for people who have subscribed, joined the waitlist, or been targeted for future onboarding

Recommended columns:

- `id uuid primary key default gen_random_uuid()`
- `email text not null`
- `normalized_email text not null unique`
- `first_name text null`
- `last_name text null`
- `display_name text null`
- `status text not null`
- `consented_at timestamptz not null`
- `consent_text_version text not null`
- `source text not null`
- `utm_source text null`
- `utm_medium text null`
- `utm_campaign text null`
- `utm_term text null`
- `utm_content text null`
- `brevo_contact_id text null`
- `brevo_sync_state text not null default 'pending'`
- `brevo_synced_at timestamptz null`
- `converted_app_user_id uuid null references public.app_users(id) on delete set null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Recommended status values:

- `subscribed`
- `unsubscribed`
- `bounced`
- `suppressed`
- `converted`

Recommended source values for this wave:

- `landing_page`
- `discord`
- `gpt`
- `manual_import`

#### `public.marketing_contact_environments`

Purpose:

- track environment-specific invitation and activation state without pretending one auth identity spans all environments

Recommended columns:

- `marketing_contact_id uuid not null references public.marketing_contacts(id) on delete cascade`
- `environment text not null`
- `status text not null`
- `invited_at timestamptz null`
- `auth_user_id uuid null`
- `converted_app_user_id uuid null references public.app_users(id) on delete set null`
- `notes text null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`
- primary key: `(marketing_contact_id, environment)`

Recommended environment values:

- `production`
- `staging`

Recommended status values:

- `none`
- `invited`
- `accepted`
- `revoked`

Why keep this separate:

- production and staging are separate Supabase projects with separate auth user IDs
- this table avoids overloading `marketing_contacts` with environment-specific state
- it gives a durable place to track who was invited to test staging without turning staging into the canonical source of truth

### Minimal-Now / Useful-Later Principle

The proposed model is deliberately small, but it lines up with likely future needs:

- invite campaigns
- beta cohorts
- conversion tracking from waitlist to real account
- environment-scoped testing access
- data export and suppression handling

## Supabase Auth Strategy

### What Not To Do

Do not call `inviteUserByEmail` or `createUser` during the public signup flow.

Reasons:

- a waitlist signup is not a commitment to create an account
- early auth rows create noise and support burden
- conversion state becomes ambiguous
- staging duplication becomes harder

### What To Do Later

When BE is ready to onboard someone:

1. Select a `marketing_contacts` row.
2. Create or refresh the relevant `marketing_contact_environments` row.
3. Use the Supabase admin API for the target environment to invite that email.
4. After invite acceptance and first sign-in, create or update the corresponding `app_users` projection.
5. Backfill `converted_app_user_id` in the marketing tables.

This preserves the current `app_users` design and aligns with Supabase’s intended invite behavior.

## Production And Staging Data Strategy

### Canonical Source

Production owns canonical waitlist and marketing-contact data.

Staging should not be the source of truth for public signups.

### Recommended Flow

1. Public users sign up against production only.
2. Production stores the canonical `marketing_contacts` record.
3. When staging is ready for external testers, BE selects a cohort from production.
4. A controlled import/sync script copies only the necessary contact rows into staging metadata tables or uses them directly to create staging invites.
5. Staging invites are sent only for the selected cohort.

### Why This Is Better Than Dual Signup

- users do not need to sign up twice
- production remains the durable audience list
- staging stays intentionally limited
- invite/tester state remains explicit and auditable

### Recommended Sync Pattern

Do not replicate full production auth into staging.

Instead:

- production exports a selected subset of `marketing_contacts`
- staging imports that subset through an internal script or admin-only endpoint
- staging creates environment-local auth users only when inviting testers

This keeps staging safer and prevents accidental coupling of auth states across environments.

## Seed And Reset Guardrails

The current seed/reset flow is catalog-heavy and should remain safe for demo data work.

New rule for this wave:

- seed and reset commands must not truncate or overwrite production-derived marketing-contact data by default

Recommended implementation:

- exclude `marketing_contacts` and `marketing_contact_environments` from the existing demo reset function
- if a full wipe is ever needed locally, require an explicit opt-in flag
- keep demo seed data for studios, titles, genres, moderators, and other fixture data separate from landing-page contact data

Recommended local-development behavior:

- developers can seed mock marketing contacts locally if needed
- those mock contacts come from dedicated fixture logic, not the production export path

## Email And Mailing Integration Plan

### System Of Record

- database: `marketing_contacts`

### Broadcast And CRM Layer

- Brevo

### Human Conversation Layer

- Gmail aliases backed by Brevo SMTP and Cloudflare Email Routing

### Recommended Sync Behavior

On successful signup:

1. write locally first
2. sync to Brevo second
3. mark sync state
4. retry sync asynchronously or via follow-up tooling if needed

Reason:

- the BE database should remain authoritative
- campaign tooling can change later without losing audience history

## Testing And Verification Plan

### Contract

- add request/response examples for the public signup endpoint
- add mock coverage for valid, duplicate, invalid-email, and Turnstile-failure cases

### Backend

- unit tests for normalization and validation
- integration tests for contact upsert behavior
- integration tests for duplicate signup idempotency
- integration tests for Brevo-sync state transitions using test doubles

### Frontend

- route smoke coverage for landing-only production mode
- form validation tests
- success, duplicate, and error-state tests

### Operational

- manual smoke for production email forwarding
- manual smoke for Gmail send-as aliases
- manual smoke for production signup end-to-end

## Implementation Sequence

1. Add planning/docs updates for this wave.
2. Add internal web contract for `POST /marketing/signups`.
3. Add failing backend tests and data-model tests.
4. Add Supabase migrations for `marketing_contacts` and `marketing_contact_environments`.
5. Implement Worker endpoint and service boundary.
6. Add Brevo integration abstraction and configuration.
7. Add frontend landing-only mode and signup form.
8. Add Turnstile verification flow.
9. Add deployment env wiring and secret templates.
10. Add smoke tests and update root automation/docs.

## Open Decisions For Review

These decisions should be explicitly confirmed during implementation:

- whether `updates@boardenthusiasts.com` should be created in wave 1 or deferred
- whether signup notifications to `matt@mattstroman.com` should be immediate per-signup or batched
- whether double opt-in is required now or can wait until mailing volume grows
- whether staging cohort sync should happen through a script, a protected admin endpoint, or direct SQL export/import
- whether production landing mode should be a build-time flag only or runtime-configurable

## Reference Links

- Cloudflare Pages Functions pricing: [https://developers.cloudflare.com/pages/functions/pricing/](https://developers.cloudflare.com/pages/functions/pricing/)
- Cloudflare Workers pricing: [https://developers.cloudflare.com/workers/platform/pricing/](https://developers.cloudflare.com/workers/platform/pricing/)
- Cloudflare Email Routing docs: [https://developers.cloudflare.com/email-routing/](https://developers.cloudflare.com/email-routing/)
- Cloudflare Turnstile plans: [https://developers.cloudflare.com/turnstile/plans/](https://developers.cloudflare.com/turnstile/plans/)
- Supabase billing overview: [https://supabase.com/docs/guides/platform/billing-on-supabase](https://supabase.com/docs/guides/platform/billing-on-supabase)
- Supabase invite user by email: [https://supabase.com/docs/reference/javascript/auth-admin-inviteuserbyemail](https://supabase.com/docs/reference/javascript/auth-admin-inviteuserbyemail)
- Supabase create user: [https://supabase.com/docs/reference/javascript/auth-admin-createuser](https://supabase.com/docs/reference/javascript/auth-admin-createuser)
- Brevo create contact API: [https://developers.brevo.com/reference/create-contact](https://developers.brevo.com/reference/create-contact)
- Brevo create sender API: [https://developers.brevo.com/reference/createsender](https://developers.brevo.com/reference/createsender)
- Brevo create list API: [https://developers.brevo.com/reference/createlist-1](https://developers.brevo.com/reference/createlist-1)
- Gmail send mail as another address: [https://support.google.com/mail/answer/22370?hl=en](https://support.google.com/mail/answer/22370?hl=en)
