# MVP Release Audit

## Table of Contents

- [Purpose](#purpose)
- [Audit Date](#audit-date)
- [Scope Assumption](#scope-assumption)
- [Current Delivered Surface](#current-delivered-surface)
- [Remaining Release Concerns](#remaining-release-concerns)
- [Remaining MVP Waves](#remaining-mvp-waves)
- [QA And Staging Preparation](#qa-and-staging-preparation)
- [Planning Cleanup Outcome](#planning-cleanup-outcome)

## Purpose

This document is the current planning source of truth for preparing the library/index MVP for release to `staging`.

It replaces older root planning documents as the active release-planning reference because several earlier plans still describe the pre-Supabase, pre-Workers, or landing-page-only phases of the project.

## Audit Date

This audit was completed on March 21, 2026.

## Scope Assumption

This audit assumes the near-term release target is the MVP of the library/index experience:

- public catalog and studio browsing
- authenticated player account bootstrap and profile flows
- player library, wishlist, and title-report workflows
- developer self-enrollment plus studio/title/release management
- moderation workflows needed to review developers and title reports

Important boundary:

- if MVP still means the full original platform vision with unified checkout, entitlements, and Board-native install delivery, the product is not MVP-ready yet
- unified commerce and Board-native install are still deferred work

## Current Delivered Surface

The repository currently delivers all of the following in code:

- React SPA with public browse, public title detail, public studio detail, player workspace, developer workspace, moderation workspace, hosted landing page, privacy page, and sign-in or recovery flows
- Cloudflare Workers API with public catalog, identity, player library, wishlist, title reports, developer studio and title management, release management, moderation review, marketing signup, and support issue routes
- Supabase Auth, Postgres, and Storage integration
- deterministic local seed data, seeded auth users, and seeded media fixtures
- local smoke coverage for Workers flows, contract smoke coverage via the shared maintained route list, frontend Vitest coverage, and parity screenshot coverage
- hosted deploy orchestration for Pages plus Workers through `python ./scripts/dev.py deploy ...`

## Remaining Release Concerns

### 1. Hosted staging still needs real environment values and smoke accounts

The checked-in staging template now targets the full library/index experience with:

- `VITE_LANDING_MODE=false`

Hosted deploy smoke also now branches by that toggle:

- landing-mode deploys still validate marketing signup and support issue reporting
- full-MVP deploys use staged smoke accounts to validate browse, identity, player, developer, and moderator flows

Remaining requirement:

- populate `config/.env.staging` with the real hosted values, including the new full-MVP smoke-account entries

### 2. The maintained public contract is aligned, but internal-only landing endpoints remain intentionally undocumented

The maintained OpenAPI surface now covers the public MVP routes that were previously missing, including:

- `GET /genres`
- `GET /age-rating-authorities`
- `GET /identity/user-name-availability`
- the expanded `GET /catalog` filters and sort values
- Board-profile write and delete operations

Intentionally excluded from the maintained public contract:

- `POST /marketing/signups`
- `POST /support/issues`

Those routes are still runtime-accessible for internal web-client usage and landing-mode deploy smoke, but they are not part of the documented public MVP contract.

### 3. Local automation is in place, but hosted browser-level QA is still required before staging sign-off

Local automation is now stronger:

- `python ./scripts/dev.py all-tests --start-workers` passes on March 21, 2026
- `python ./scripts/dev.py contract-smoke --start-workers` passes
- `python ./scripts/dev.py workers-smoke --start-stack` passes
- `python ./scripts/dev.py api-test --start-workers --skip-lint` passes
- CI now runs root CLI validation, contract smoke, Workers smoke, and the Postman contract run

Remaining manual validation:

- parity screenshots with `python ./scripts/dev.py parity-test`
- hosted sign-in, recovery, and role-routed workspace checks against staging
- confirmation that hosted smoke accounts and redirect configuration behave correctly outside local seed data

### 4. The MVP scope is now explicitly library/index only

Confirmed MVP scope:

- release publishing is modeled only as a per-release `acquisitionUrl`

Deferred beyond MVP:

- unified commerce or entitlement orchestration
- Board-native download and install delivery

## Remaining MVP Waves

### Completed Foundations

- the maintained OpenAPI surface now matches the public library/index MVP routes
- route-wide contract smoke now validates the shared maintained route inventory
- local Workers smoke now exercises player, developer, and moderator CRUD paths
- root validation CI now includes contract smoke, Workers smoke, and a live Postman run
- obsolete root and submodule planning artifacts were removed from the active tree

### Wave 1: Hosted Staging Configuration

- populate the real staging environment values, including full-MVP smoke-account credentials
- confirm hosted Supabase redirect and recovery URLs for the maintained SPA routes
- configure hosted Supabase Google and GitHub auth providers plus their upstream OAuth app callback URLs
- confirm Turnstile, Brevo, support-report sender, and allowed-origin values in hosted staging

### Wave 2: Hosted MVP Smoke And Browser QA

- run hosted deploy smoke with `VITE_LANDING_MODE=false` and verify full-MVP route coverage
- run hosted browser QA for browse, auth, player, developer, and moderator paths
- verify landing-only internal flows still behave correctly when the toggle is enabled for non-MVP environments

### Wave 3: Release Gate Enforcement

- keep `python ./scripts/dev.py all-tests --start-workers` as the local full-suite gate
- keep `python ./scripts/dev.py api-test --start-workers --skip-lint` in the release checklist so the Postman collection stays executable
- require green CI for root validation, contract smoke, Workers smoke, and Postman before staging promotion
- decide whether parity screenshots are blocking for staging or a required human sign-off step

### Deferred Beyond MVP

- unified commerce and entitlement orchestration
- Board-native download and install delivery

## QA And Staging Preparation

### Local Validation Checklist

- run `python ./scripts/dev.py bootstrap`
- run `python ./scripts/dev.py all-tests --start-workers`
- run `python ./scripts/dev.py api-test --start-workers --skip-lint`
- run `python ./scripts/dev.py parity-test`
- manually verify sign-in, signup confirmation, password recovery, player library, wishlist, reporting, developer studio create or edit, title create or edit, media upload, release publish, and moderation verification flows

### Hosted Staging Preparation Checklist

- populate hosted staging values in `config/.env.staging`
- keep `VITE_LANDING_MODE=false` for the maintained staging target
- confirm Supabase hosted redirect URLs include the maintained sign-in and recovery callback routes
- populate `SUPABASE_AUTH_GITHUB_CLIENT_ID` / `SUPABASE_AUTH_GITHUB_CLIENT_SECRET` and `SUPABASE_AUTH_GOOGLE_CLIENT_ID` / `SUPABASE_AUTH_GOOGLE_CLIENT_SECRET` for staging
- register the staging Supabase auth callback URL with both GitHub and Google OAuth apps
- confirm the hosted sign-in page shows the expected social sign-in buttons once those client IDs are present
- confirm Turnstile, Brevo, support-report sender configuration, and allowed web origins are correct for hosted staging
- keep storage upload authorization in the Workers API for this release; do not treat browser `storage.objects` RLS policies as a staging blocker unless a direct browser-to-Supabase upload path is introduced
- run `python ./scripts/dev.py deploy --staging --preflight-only`
- run `python ./scripts/dev.py deploy --staging --dry-run-only`
- run `python ./scripts/dev.py deploy --staging`

### Hosted Staging QA Checklist

- verify public landing or home route renders the expected shell for the chosen mode
- verify browse search, filters, and title detail data match the hosted API behavior
- verify email sign-in, Google sign-in, GitHub sign-in, confirmation, recovery, and sign-out flows against hosted Supabase Auth
- verify player library, wishlist, and reporting flows
- verify developer enrollment, studio CRUD, title CRUD, metadata, media, and release workflows
- verify moderator developer verification and title-report resolution workflows
- verify any retained landing-page signup and support issue flows

### Release Gate Recommendation

Do not promote the full library/index MVP to hosted staging until all of the following are true:

- staging configuration is aligned to the intended product surface
- deploy smoke coverage includes full MVP workflows
- the local release gate passes:
  `python ./scripts/dev.py all-tests --start-workers`
- the executable Postman run passes:
  `python ./scripts/dev.py api-test --start-workers --skip-lint`
- CI passes for root validation, contract smoke, Workers smoke, and Postman
- hosted browser QA signs off on browse, auth, player, developer, and moderator workflows

## Planning Cleanup Outcome

The following planning artifacts were removed from the active tree during MVP release cleanup:

- `planning/current-state-and-wave-plan.md`
- `planning/product-realignment-implementation-plan.md`
- `planning/cloudflare-supabase-workers-conversion-plan.md`
- `planning/technology-fit-recommendation.md`
- `planning/landing-page-*.md`
- `backend/planning/mvp-schema-implementation-plan.md`
- `frontend/planning/adr-0001-web-ui-foundation.md`
- `frontend/planning/web-ui-mvp-brief.md`
- `frontend/planning/web-ui-wireframes.md`

Use this audit plus the maintained runtime docs as the active reference set for MVP release preparation. If any of the removed material is ever needed for historical context, use Git history rather than restoring it to the active planning surface.
