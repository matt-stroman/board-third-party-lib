# Cloudflare And Supabase Conversion Plan

## Table of Contents

- [Purpose](#purpose)
- [Target Architecture](#target-architecture)
- [Non-Negotiable Constraints](#non-negotiable-constraints)
- [UX Parity Boundary](#ux-parity-boundary)
- [Wave 1: Foundation And Parity Baseline](#wave-1-foundation-and-parity-baseline)
- [Wave 2: Platform And API Cutover](#wave-2-platform-and-api-cutover)
- [Wave 3: Frontend Port And Full Cutover](#wave-3-frontend-port-and-full-cutover)
- [Local Developer Workflow Target State](#local-developer-workflow-target-state)
- [Staging Deployment Target State](#staging-deployment-target-state)
- [Decommission Scope](#decommission-scope)

## Purpose

This plan defines the fastest acceptable conversion path from the current .NET and Blazor implementation to a near-zero-cost stack built around Cloudflare and Supabase while preserving the current user-facing experience.

The primary goals are:

- reduce runtime hosting cost toward `$0`
- keep a remotely deployable staging environment
- preserve the maintained workflow surface and API intent
- preserve the current frontend user experience so closely that users should not perceive a change beyond the auth provider itself
- retain a single root developer entrypoint via `python ./scripts/dev.py ...`

This plan is intentionally separate from the current product-wave plan because it is a platform migration plan, not a feature-delivery plan.

## Target Architecture

- frontend: `React` + `TypeScript` single-page app hosted on `Cloudflare Pages`
- backend/API: `Cloudflare Workers`
- auth: `Supabase Auth`
- relational application data: `Supabase Postgres`
- uploaded media: `Supabase Storage`
- dns, tls, proxy, and static hosting: `Cloudflare`
- staging domains:
  - `staging.boardenthusiasts.com`
  - `api.staging.boardenthusiasts.com`

The SPA must keep route parity for current user-facing experiences such as `/player`, `/develop`, `/moderate`, `/browse`, and public studio/title pages.

## Non-Negotiable Constraints

- User-facing workflow behavior must remain materially unchanged.
- Visual design, layout, copy hierarchy, information scent, and interaction flow must remain materially unchanged.
- Existing API contract semantics should be preserved where still aligned to maintained behavior, even if the implementation substrate changes.
- Local development and automated verification must remain accessible through `python ./scripts/dev.py ...`.
- Each migration wave must update the committed local developer run instructions so contributors can still run the relevant stack from the repository root.
- Staging deployment must be reproducible and scriptable.
- New provider-managed capabilities must not leak provider-specific behavior into the visible UX unless the product explicitly wants that change.

## UX Parity Boundary

The current frontend experience can be preserved closely enough that end users should not be able to tell the application was replatformed, but that does **not** mean the literal generated HTML, CSS, or JavaScript bytes will remain identical.

That exact byte-level identity is not a realistic requirement because:

- Blazor server rendering and a React SPA do not produce identical DOM lifecycle behavior
- component hydration, event wiring, and runtime bootstrapping differ by framework
- auth/session plumbing changes when moving from server-side cookie flows to browser token flows

What **is** realistic and required is parity at the user-perceived contract level:

- same routes
- same layout and navigation structure
- same content hierarchy and labels
- same loading, empty, success, and error states
- same filtering, fuzzy find, and in-place workflow behavior
- same or tighter response-time expectations in normal staging use

Conversion work must therefore treat the current UI as a reference implementation and gate completion on visual and behavioral parity rather than framework identity.

## Wave 1: Foundation And Parity Baseline

Status: implemented on March 8, 2026

Objective: lock the migration target, capture the current UX contract, and establish local/staging scaffolding before feature porting begins.

### Chunk 1: Reference Capture And Scope Freeze

- identify the minimum maintained surface required for staging demo:
  - auth and current-user bootstrap
  - `/player`
  - `/develop`
  - `/moderate`
  - `/browse`
  - public studio page
  - public title detail page
  - implemented studio and moderation workflows used by those routes
- capture current route inventory, page screenshots, key interaction recordings, and copy snapshots for parity reference
- define authoritative parity checklist for:
  - navigation
  - route visibility by access level
  - fuzzy-search and filter behavior
  - mutation success and validation states
  - empty-state and error-state messaging

### Chunk 2: Repository And Tooling Foundation

- add new app workspaces for:
  - SPA frontend
  - Workers API
  - shared TypeScript contract/model package if needed
- keep existing implementation in place until cutover is complete
- add root-level configuration templates for:
  - Cloudflare Pages
  - Cloudflare Workers
  - local and staging env var layouts
  - Supabase project wiring

### Chunk 3: Developer Automation Reset

- evolve `python ./scripts/dev.py ...` so it remains the only required routine entrypoint
- add commands for:
  - local SPA install/build/run
  - local Workers run
  - local Supabase start/stop/status
  - local seed/reset
  - staging deploy for Pages and Workers
- keep current commands working during the transition where practical
- document required local tools:
  - `node`
  - `npm`
  - `supabase` CLI
  - `wrangler`
- publish a Wave 1 local runbook describing exactly how to run:
  - the legacy stack
  - the migration shells
  - the baseline parity and contract verification commands

### Chunk 4: Verification Baseline

- add visual-regression or screenshot-comparison coverage for primary routes
- add route-level browser smoke tests against the current implementation to serve as parity baseline
- add contract smoke harness for the minimum maintained API surface that the new stack must preserve

### Wave 1 Test Gate

- parity reference artifacts committed
- root automation can start local new-stack dependencies and app shells
- browser smoke tests execute against the current implementation baseline
- committed docs explain the local run path for the legacy and migration scaffolding stacks
- staging configuration templates exist for Cloudflare and Supabase targets

## Wave 2: Platform And API Cutover

Status: implemented locally on March 8, 2026; live remote staging validation pending provider credentials

Objective: replace Keycloak, PostgreSQL app access patterns, local file storage, and .NET backend behavior with Supabase and Workers while keeping the frontend migration unblocked.

### Chunk 1: Auth And Identity Migration

- replace Keycloak with Supabase Auth
- implement supported social-login provider strategy for staging:
  - email/password
  - GitHub
  - Google
- move application authorization state into application-owned tables and/or claims-backed read models:
  - users
  - board profiles
  - developer access state
  - moderator-visible verification state
  - studio memberships
- preserve current user-facing role semantics even if internal storage changes

### Chunk 2: Database And Storage Migration

- map existing relational model to Supabase Postgres
- create migration strategy for implemented Waves 1 through 7 entities needed by the demo surface
- replace local filesystem media storage with Supabase Storage
- update media URL generation and access rules for public and authenticated assets

### Chunk 3: Workers API Implementation

- implement the minimum maintained API surface in Cloudflare Workers
- keep route shapes and payload shapes aligned to the maintained contract where feasible
- start with endpoints required by the staging demo workflows:
  - current-user bootstrap and profile reads/writes
  - developer enrollment
  - moderation developer search and verification mutation
  - browse and public catalog reads
  - studio CRUD and media/link management needed by `/develop`
- define a thin service boundary so Workers code is not coupled directly to Cloudflare request handlers

### Chunk 4: Local Data, Seeding, And Test Infrastructure

- port `seed-data` to seed Supabase local state and storage fixtures deterministically
- provide local auth fixture provisioning for demo/test accounts
- ensure local reset/reseed is idempotent and fast enough for routine test use
- keep contract and browser tests runnable against either old or new stack during the transition
- publish a Wave 2 local runbook describing:
  - required local dependencies
  - how to reset and seed Supabase locally
  - how to run the Workers API locally
  - how to execute contract smoke and Workers flow smoke locally

### Chunk 5: Staging Provider Wiring

- create staging deployment scripts for:
  - Cloudflare Pages
  - Cloudflare Workers
  - Supabase project configuration
- configure Cloudflare DNS and route split for staging
- configure secure env-var handling and secrets for local and staging use

### Wave 2 Test Gate

- local new-stack backend/auth/storage flows pass against seeded data
- staging environment is remotely reachable on Cloudflare/Supabase infrastructure
- contract smoke tests for the minimum maintained demo surface pass against Workers
- image upload and retrieval flows work in local and staging environments
- committed docs explain the local Supabase + Workers workflow for the maintained Wave 2 surface

## Wave 3: Frontend Port And Full Cutover

Status: planned

Objective: replace the current Blazor UI with a static-hosted SPA that is visually and behaviorally indistinguishable to users, then retire the obsolete stack.

### Chunk 1: SPA Shell And Shared Layout Port

- recreate the current application shell, navigation, route structure, and layout tokens in the SPA
- preserve responsive behavior, visual spacing, typography choices, icons, and interaction sequencing
- preserve current loading and status messaging patterns

### Chunk 2: Workflow Port

- port `/player`, `/develop`, `/moderate`, `/browse`, public studio, and public title flows
- preserve in-place workflow switching and no-reload interactions
- preserve current fuzzy-finding and live-filter behavior on the client
- preserve form validation, optimistic updates where present, and mutation feedback

### Chunk 3: Auth UX Port

- replicate sign-in, sign-out, session-expiry, and account-management entry flows using Supabase Auth
- keep auth-provider changes isolated so the surrounding application UX remains familiar
- ensure route protection and access-state gating match the current visible behavior

### Chunk 4: Final Cutover And Cleanup

- switch root workflows and CI/test automation to the new stack as primary
- remove obsolete .NET and Keycloak runtime dependencies after parity sign-off
- update docs, agent guidance, and root automation help text to reflect the new default stack
- publish a Wave 3 local runbook describing the post-cutover default local development path with the legacy runtime removed

### Wave 3 Test Gate

- primary route screenshots and browser flows match parity baseline within agreed tolerances
- maintained demo workflows pass in local and staging environments
- root developer automation defaults to the new stack
- obsolete stack can be removed without breaking maintained workflows
- committed docs explain the final local developer workflow after cutover

## Local Developer Workflow Target State

The target developer workflow remains rooted in `python ./scripts/dev.py ...`.

Expected commands after conversion:

- `python ./scripts/dev.py bootstrap`
- `python ./scripts/dev.py up`
- `python ./scripts/dev.py down`
- `python ./scripts/dev.py status`
- `python ./scripts/dev.py web --hot-reload`
- `python ./scripts/dev.py frontend --hot-reload`
- `python ./scripts/dev.py api-test`
- `python ./scripts/dev.py test`
- `python ./scripts/dev.py verify`
- `python ./scripts/dev.py seed-data`
- `python ./scripts/dev.py deploy-staging`

Expected local behavior:

- `bootstrap` installs JavaScript and CLI prerequisites or validates their presence
- `up` starts local Supabase services and any local Worker support services
- `web --hot-reload` runs the SPA dev server and local Worker runtime together
- `seed-data` provisions deterministic database rows, auth users, and storage fixtures
- `verify` runs unit, integration, contract, and browser smoke coverage for the migrated stack

## Staging Deployment Target State

- Cloudflare Pages serves the SPA on `staging.boardenthusiasts.com`
- Cloudflare Workers serves the API on `api.staging.boardenthusiasts.com`
- Supabase hosts auth, relational data, and storage
- Cloudflare manages DNS and TLS termination
- deployment is scriptable from the root repository
- staging secrets and provider IDs are documented and injected without committed secret material

## Decommission Scope

After successful cutover, remove or archive obsolete platform-specific assets that are no longer part of the maintained stack, including:

- ASP.NET backend runtime implementation
- Blazor server frontend runtime implementation
- Keycloak local realm and related bootstrap material
- PostgreSQL Docker runtime used only for the old stack
- Mailpit and local auth-provider dependencies used only by the old stack

Do not remove historical planning or contract artifacts that remain useful for tracing feature intent and migration history.
