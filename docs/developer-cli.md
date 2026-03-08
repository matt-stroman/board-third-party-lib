# Developer CLI (`scripts/dev.py`)

Supplemental documentation for the root developer automation CLI.

Primary documentation for commands, arguments, and usage should live in the CLI help output:

```bash
python ./scripts/dev.py --help
python ./scripts/dev.py <command> --help
```

This document provides quick guidance, common workflows, and project-specific notes.

## Table of Contents

- [Purpose](#purpose)
- [Primary Entry Point](#primary-entry-point)
- [Common Workflows](#common-workflows)
- [Migration Workflows](#migration-workflows)
- [Database Backup and Restore](#database-backup-and-restore)
- [Configuration Overrides](#configuration-overrides)
- [Notes](#notes)

## Purpose

The developer CLI orchestrates common local development tasks from the repository root:

- bootstrap submodules and restore backend dependencies
- run the full local web stack from the repository root
- inspect/stop the locally launched root web stack
- run the frontend web UI from the repository root
- start/stop/reuse local PostgreSQL, Mailpit, and Keycloak via Docker Compose
- run the backend API
- validate backend XML documentation coverage
- run backend tests
- run all major validation checks in one pass (backend docs + backend/frontend tests + API lint + API contract)
- authenticate Postman CLI when Postman workspace or mock operations are needed
- lint the Git-tracked OpenAPI specification with Redocly CLI
- run API contract tests
- provision/sync Postman mocks and workspace artifacts
- run environment diagnostics
- create/restore local PostgreSQL SQL backups
- seed deterministic local auth/catalog sample data for UI/UX testing
- run Wave 1 migration workspace commands for the React SPA, Workers API, Supabase local stack, parity baselines, and staging deployment wrappers

## Primary Entry Point

Command:

```bash
python ./scripts/dev.py <command> [options]
```

## Common Workflows

### First-time setup + run

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --hot-reload
```

This starts Docker dependencies, the backend API, the frontend web app with Razor hot reload, and then opens the frontend URL in your default browser. On Windows, if Docker Desktop is installed but not already running, the CLI will try to launch it automatically and wait for the daemon before continuing. The root workflow is HTTPS-first for frontend, backend, Keycloak, and the local Mailpit UI, and it also exports TLS material for the local PostgreSQL container and Mailpit SMTP STARTTLS. It will launch the frontend at `https://localhost:7277`, the backend at `https://localhost:7085`, Keycloak at `https://localhost:8443`, and Mailpit at `https://localhost:8025`, while local PostgreSQL rejects non-TLS TCP connections.

The frontend reconnect modal now retries automatically when the browser tab becomes visible again, when the window regains focus, when the page is restored, and when the client comes back online. If the Blazor circuit cannot be resumed, the page reloads instead of leaving the UI in a dead-click state.

Local registration and verification emails are captured in Mailpit:

```bash
https://localhost:8025
```

If you only want to run the frontend from the root workspace:

```bash
python ./scripts/dev.py frontend --hot-reload
```

If you want to run API contract tests from the same terminal session without manually keeping the backend open, use:

```bash
python ./scripts/dev.py api-test --start-backend --skip-lint
```

### Run the full local web stack

```bash
python ./scripts/dev.py web
python ./scripts/dev.py web --hot-reload
```

The frontend part of this workflow now runs through `dotnet watch`, so `.razor`, `.cs`, and other supported web-app edits hot reload without restarting the stack. `--hot-reload` also starts live Tailwind rebuilds.

Useful flags:

- `--hot-reload`
- `--no-browser`
- `--skip-backend-restore`
- `--skip-npm-install`
- `--skip-css-build`
- `--skip-frontend-restore`
- `--backend-url`
- `--frontend-url`

### Check or stop the local web stack

```bash
python ./scripts/dev.py web-status
python ./scripts/dev.py web-stop
python ./scripts/dev.py web-stop --down-dependencies
```

Use `web-stop` when a previous `web` session was interrupted and left the backend/frontend processes running.

### Start only local dependencies (no API)

```bash
python ./scripts/dev.py up --dependencies-only
```

### Seed local sample data for Wave 7 UI/UX testing

```bash
python ./scripts/dev.py seed-data --reset-media
```

This command:

- ensures local Keycloak + PostgreSQL dependencies are running
- provisions/updates deterministic local users in Keycloak (including role assignments)
- validates the checked-in title and studio media bundles under `frontend/src/Board.ThirdPartyLibrary.Frontend.Web/wwwroot/test-images/seed-catalog`
- repopulates local PostgreSQL studio/title/media/release/integration data used by current player/developer/moderation workflows
- seeds public studio banners plus studio support/social links alongside the studio records

The seed data references those static local asset URLs directly, so rerunning the command refreshes the database state without regenerating art at runtime.
Title card/hero/logo media should be checked-in PNGs, while studio logos remain SVGs. Studio banners use checked-in PNGs when available and otherwise fall back to the checked-in SVG variants.

Useful flags:

- `--reset-media` clears the obsolete legacy generated-media cache before validation
- `--seed-password`

### Run the frontend web UI

```bash
python ./scripts/dev.py frontend
python ./scripts/dev.py frontend --hot-reload
```

This standalone frontend workflow also uses `dotnet watch` for Razor hot reload.

Useful flags:

- `--hot-reload`
- `--skip-npm-install`
- `--skip-css-build`
- `--skip-restore`

## Migration Workflows

Wave 1 adds a parallel migration workspace without replacing the current .NET runtime yet.

Reference doc:

- [`docs/cloudflare-supabase-workers-wave-1.md`](./cloudflare-supabase-workers-wave-1.md)

### Install, build, or run the React SPA shell

```bash
python ./scripts/dev.py spa install
python ./scripts/dev.py spa build
python ./scripts/dev.py spa run
```

### Install, build, or run the Workers API shell

```bash
python ./scripts/dev.py workers install
python ./scripts/dev.py workers build
python ./scripts/dev.py workers run
```

### Start, stop, inspect, or reset local Supabase services

```bash
python ./scripts/dev.py supabase start
python ./scripts/dev.py supabase status
python ./scripts/dev.py supabase db-reset
python ./scripts/dev.py supabase stop
```

### Run the maintained API contract smoke harness

```bash
python ./scripts/dev.py contract-smoke --start-backend
```

This uses the Wave 1 smoke harness under `tests/contract-smoke`. If you provide a bearer token with `--token`, the harness also validates authenticated maintained endpoints.

### Run browser parity smoke and screenshot comparison coverage

```bash
python ./scripts/dev.py parity-test --start-stack
```

This command starts the current .NET backend/frontend stack if requested, signs into the seeded local Keycloak realm, and runs the Playwright-based parity suite under `tests/parity`.

### Refresh the committed screenshot baselines

```bash
python ./scripts/dev.py capture-parity-baseline --start-stack
```

### Run staging deployment wrappers for Pages and Workers

```bash
python ./scripts/dev.py deploy-staging --dry-run
python ./scripts/dev.py deploy-staging --pages-only
python ./scripts/dev.py deploy-staging --workers-only
```

### Stop dependencies

```bash
python ./scripts/dev.py down
```

### Check local tool and environment status

```bash
python ./scripts/dev.py doctor
python ./scripts/dev.py status
```

### Run backend tests

```bash
python ./scripts/dev.py test
python ./scripts/dev.py test --skip-integration
```

### Run one-stop full validation

```bash
python ./scripts/dev.py all-tests
```

This command runs backend XML docs validation, backend unit/integration tests, frontend tests, OpenAPI lint, and API contract tests in one pass.

If you are already running the API manually:

```bash
python ./scripts/dev.py all-tests --no-start-backend
```

### Run the main repository verification workflow

```bash
python ./scripts/dev.py verify --skip-contract-tests
```

Include the maintained contract tests in the same pass:

```bash
python ./scripts/dev.py verify --start-backend
```

This workflow validates backend XML docs, runs backend tests, lints the OpenAPI spec, and optionally executes the Postman contract suite.
It restores the backend solution up front, so it works from a fresh clone without a separate manual `dotnet restore`.

### Authenticate Postman CLI for workspace or mock operations

```bash
python ./scripts/dev.py api-login --postman-api-key <your-postman-api-key>
```

If you prefer not to keep a separate login step, `api-mock` and `api-sync` also accept `--postman-api-key` directly.

### Lint the API contract

```bash
python ./scripts/dev.py api-lint
```

### Run API contract tests against the local backend

```bash
python ./scripts/dev.py api-test
```

Important for live local runs:

- the committed local environment file contains placeholder values for authenticated and persistence-backed success paths such as `accessToken`, `studioId`, `studioSlug`, `titleId`, and `titleSlug`
- the committed local environment file also leaves `studioLinkId` as a placeholder for studio-link update/delete flows
- the collection skips those success-path assertions until you replace the placeholders with real local values
- health and unauthenticated/public catalog coverage still runs with the committed template as-is

If the backend is not already running, start it automatically for the test run:

```bash
python ./scripts/dev.py api-test --start-backend --skip-lint
```

### Run API contract tests against a mock URL

```bash
python ./scripts/dev.py api-test --base-url https://example.mock.pstmn.io --contract-execution-mode mock
```

### Provision a shared Postman mock from the Git-tracked contract collection

```bash
python ./scripts/dev.py api-mock --mode shared --postman-api-key <your-postman-api-key>
```

### Push Native Git API artifacts to Postman Cloud

```bash
python ./scripts/dev.py api-sync --postman-api-key <your-postman-api-key>
```

### Push Native Git artifacts without reprovisioning the shared mock

```bash
python ./scripts/dev.py api-sync --skip-mock --postman-api-key <your-postman-api-key>
```

## Database Backup and Restore

The CLI includes PostgreSQL helpers that operate against the local Dockerized database container.

### Create a backup (timestamped default path)

```bash
python ./scripts/dev.py db-backup
```

Default output location:

- `./backups/<database>-<utc-timestamp>.sql`

### Create a backup at a specific path

```bash
python ./scripts/dev.py db-backup ./backups/dev-before-migration.sql
```

### Restore a backup

```bash
python ./scripts/dev.py db-restore ./backups/dev-before-migration.sql
```

Notes:

- The PostgreSQL container must already be running (`up` or `up --dependencies-only`).
- `db-backup` creates a plain SQL dump (`pg_dump`) with cleanup statements (`--clean --if-exists`).
- `db-restore` replays the SQL using `psql` against the configured database.

## Configuration Overrides

Most commands accept shared overrides (see `--help` for full details), including:

- `--compose-file`
- `--postgres-container-name`
- `--postgres-user`
- `--postgres-database`
- `--keycloak-container-name`
- `--keycloak-ready-url`
- `--backend-project`
- `--backend-solution`

Example (non-default DB name):

```bash
python ./scripts/dev.py status --postgres-database my_local_db
```

API workflow commands also expose workflow-specific overrides. Common examples:

- `api-test --environment <path>`
- `api-test --base-url <url>`
- `api-test --contract-execution-mode live|mock`
- `api-lint`
- `api-mock --mode shared|ephemeral`
- `api-sync --skip-mock`
- `web --hot-reload`
- `web-status`
- `web-stop --down-dependencies`
- `frontend --hot-reload`
- `seed-data --seed-password <value>`
- `spa install|build|run`
- `workers install|build|run`
- `supabase start|stop|status|db-reset`
- `contract-smoke --start-backend`
- `parity-test --start-stack`
- `capture-parity-baseline --start-stack`
- `deploy-staging --dry-run`

For live API contract execution, the default environment template is:

- `api/postman/environments/board-enthusiasts_local.postman_environment.json`

Populate the placeholder auth and resource IDs in a private copy when you want full authenticated create/update coverage against a local backend.

## Notes

- The `up`, `down`, and `status` commands manage the local PostgreSQL, Mailpit, and Keycloak containers together.
- The Wave 1 migration scaffolding expects `node`, `npm`, `supabase`, and `wrangler` in addition to the existing .NET/Docker toolchain.
- The `down` command uses `docker compose down` and does **not** remove named volumes. Your local Postgres data persists unless you explicitly remove volumes.
- VS Code tasks in this repo call the Python CLI directly.
- The supported developer entry point for this repository is `python ./scripts/dev.py ...`; API-local helper scripts under `api/scripts/` are implementation details for CI and the root CLI.
- Tool executables are resolved from each developer's `PATH`; the CLI does not assume fixed install directories for `dotnet`, `node`, `npx`, `postman`, `docker`, or other required tools.


