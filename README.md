# board-enthusiasts

A solution for third party developers for the Board ecosystem to use to register and share their games with the public.

Current implementation status:

- the maintained API/backend/frontend surface includes the Keycloak-backed identity and health foundation, self-service developer access enrollment, verified developer role moderation endpoints, player library and wishlist flows, title reporting with moderator and developer threads, and in-app notifications
- EF Core migrations for `users`, `user_board_profiles`, `studios`, `studio_memberships`, `studio_links`, `titles`, `title_metadata_versions`, `title_media_assets`, `title_releases`, `release_artifacts`, `supported_publishers`, `integration_connections`, `title_integration_bindings`, `player_owned_titles`, `player_wishlist_entries`, `title_reports`, `title_report_messages`, `user_notifications`, and `user_platform_roles` are implemented
- Wave 7 delivered the shared workspace shells, in-place developer studio workflows, deterministic local seed data, shared browse/studio catalog UX, and studio public-branding/link management
- Wave 8 delivered player personalization and moderation follow-up workflows for wishlist, My Games, title reports, and notifications
- the current migration wave is Wave 2 platform and API cutover for the Cloudflare, Supabase, and Workers conversion plan
- the next product wave after the migration branch resumes is Wave 9 unified commerce and entitlements

## Table of Contents

- [Getting started in this repository](#getting-started-in-this-repository)
- [Docs](#docs)
- [Planning](#planning)
- [Developer Automation](#developer-automation)

## Getting started in this repository

This repository currently tracks backend and frontend as git submodules.

Quick start (full local web stack from the root workspace):

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --hot-reload
```

This starts local Docker dependencies, the backend API, the frontend web app with Razor hot reload, and opens the frontend URL in your browser.
On Windows, the CLI will also try to launch Docker Desktop automatically if it is installed but not already running, trust the local .NET HTTPS development certificate, export localhost TLS material for Keycloak and local PostgreSQL, create a local TLS certificate for Mailpit, and launch the local web stack on secure endpoints. The browser-facing services run on HTTPS, local PostgreSQL connections are TLS-enforced, and Keycloak verification emails are captured locally in Mailpit at [`https://localhost:8025`](https://localhost:8025).

Quick start (backend API + local PostgreSQL + Keycloak only):

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py up
```

Initialize them after clone:

```bash
git submodule update --init --recursive
```

Check that submodules are initialized (no leading `-` in status output):

```bash
git submodule status
```

## Docs

- Project-wide developer docs:
  - Developer CLI (root automation commands): [`docs/developer-cli.md`](docs/developer-cli.md)
  - Wave 1 migration foundation: [`docs/cloudflare-supabase-workers-wave-1.md`](docs/cloudflare-supabase-workers-wave-1.md)
  - Wave 2 platform/API cutover: [`docs/cloudflare-supabase-workers-wave-2.md`](docs/cloudflare-supabase-workers-wave-2.md)
- Backend-specific developer docs (in backend submodule):
  - Backend phase 1 (PostgreSQL local setup): [`backend/docs/backend-phase-1-postgres-setup.md`](backend/docs/backend-phase-1-postgres-setup.md)
  - New developer setup / quick start (current backend MVP): [`backend/docs/new-developer-setup.md`](backend/docs/new-developer-setup.md)
  - Auth and data ownership boundary: [`backend/docs/auth-data-ownership.md`](backend/docs/auth-data-ownership.md)
  - Current title/catalog schema, lifecycle, media, and release model: [`backend/docs/title-catalog-schema.md`](backend/docs/title-catalog-schema.md)

## Planning

- Current planning and implementation alignment:
  - Current architecture and wave alignment: [`planning/current-state-and-wave-plan.md`](planning/current-state-and-wave-plan.md)
  - Cloudflare/Supabase/Workers conversion plan: [`planning/cloudflare-supabase-workers-conversion-plan.md`](planning/cloudflare-supabase-workers-conversion-plan.md)
  - Product realignment implementation sequencing: [`planning/product-realignment-implementation-plan.md`](planning/product-realignment-implementation-plan.md)
  - Backend schema implementation plan: [`backend/planning/mvp-schema-implementation-plan.md`](backend/planning/mvp-schema-implementation-plan.md)
  - Wave 5 publisher/platform research notes: [`planning/wave-5-publisher-research-notes.md`](planning/wave-5-publisher-research-notes.md)
  - Technology recommendation: [`planning/technology-fit-recommendation.md`](planning/technology-fit-recommendation.md)
- Historical planning context:
  - Initial data schema plan: [`api/planning/initial-data-schema-plan.md`](api/planning/initial-data-schema-plan.md)

## Developer Automation

Primary root script entry point:

- [`scripts/dev.py`](scripts/dev.py)

See the dedicated CLI doc for full command coverage and options:

- [`docs/developer-cli.md`](docs/developer-cli.md)

Examples:

```bash
python ./scripts/dev.py doctor
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --hot-reload
python ./scripts/dev.py web-status
python ./scripts/dev.py web-stop --down-dependencies
python ./scripts/dev.py frontend --hot-reload
python ./scripts/dev.py up
python ./scripts/dev.py all-tests
python ./scripts/dev.py verify --skip-contract-tests
python ./scripts/dev.py api-lint
python ./scripts/dev.py api-test --start-backend
python ./scripts/dev.py test
python ./scripts/dev.py down
python ./scripts/dev.py spa run
python ./scripts/dev.py workers run
python ./scripts/dev.py supabase status
python ./scripts/dev.py contract-smoke --target migration --start-workers
python ./scripts/dev.py workers-smoke --start-stack
python ./scripts/dev.py parity-test --start-stack
python ./scripts/dev.py deploy-staging --dry-run
```
