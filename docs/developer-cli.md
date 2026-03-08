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
- [Configuration Overrides](#configuration-overrides)
- [Notes](#notes)

## Purpose

The developer CLI orchestrates common local development tasks from the repository root:

- bootstrap submodules and install maintained workspace dependencies
- run the full local web stack from the repository root
- inspect/stop the locally launched root web stack
- run the maintained SPA frontend from the repository root
- start/stop/reuse local Supabase services
- run the maintained backend API
- run maintained backend verification
- run all major validation checks in one pass (maintained backend tests + root CLI tests + frontend tests + API lint + API contract)
- authenticate Postman CLI when Postman workspace or mock operations are needed
- lint the Git-tracked OpenAPI specification with Redocly CLI
- run API contract tests
- provision/sync Postman mocks and workspace artifacts
- run environment diagnostics
- seed deterministic local auth/catalog sample data for UI/UX testing
- run Wave 1 and Wave 2 migration workspace commands for the React SPA, Workers API, Supabase local stack, parity baselines, seeded Supabase data, and staging deployment wrappers

## Primary Entry Point

Command:

```bash
python ./scripts/dev.py <command> [options]
```

## Common Workflows

### First-time setup + run

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web
```

This starts local Supabase services, the maintained Workers backend, and the migration SPA, then opens the frontend URL in your default browser.

If you only want to run the frontend from the root workspace:

```bash
python ./scripts/dev.py frontend
```

If you want to run API contract tests from the same terminal session without manually keeping the Workers stack open, use:

```bash
python ./scripts/dev.py api-test --start-workers --skip-lint
```

### Run the maintained local web stack

```bash
python ./scripts/dev.py web
```

The maintained frontend part of this workflow runs through the Vite SPA dev server, while the maintained backend runs through Wrangler against local Supabase services.

Useful flags:

- `--no-browser`
- `--skip-backend-restore`
- `--skip-npm-install`
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

### Seed local sample data for the maintained Wave 2 stack

```bash
python ./scripts/dev.py seed-data
```

This command:

- ensures local Supabase services are running
- provisions/updates deterministic local Supabase auth users
- validates the checked-in title and studio media bundles under `frontend/src/Board.ThirdPartyLibrary.Frontend.Web/wwwroot/test-images/seed-catalog`
- repopulates local Supabase studio/title/media data used by the maintained Workers surface
- seeds public studio banners plus studio support/social links alongside the studio records

The seed data references those static local asset URLs directly, so rerunning the command refreshes the database state without regenerating art at runtime.
Title card/hero/logo media should be checked-in PNGs, while studio logos remain SVGs. Studio banners use checked-in PNGs when available and otherwise fall back to the checked-in SVG variants.

Useful flags:

- `--seed-password`

### Run the frontend web UI

```bash
python ./scripts/dev.py frontend
```

This standalone frontend workflow runs the maintained SPA shell through the Vite dev server.

Useful flags:

- `--skip-npm-install`

## Migration Workflows

Wave 1 and Wave 2 establish the maintained Cloudflare Workers + Supabase backend path and the SPA migration shell.

Reference doc:

- [`docs/cloudflare-supabase-workers-wave-1.md`](./cloudflare-supabase-workers-wave-1.md)
- [`docs/cloudflare-supabase-workers-wave-2.md`](./cloudflare-supabase-workers-wave-2.md)

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

`supabase db-reset` now reseeds deterministic Supabase auth users, relational demo data, and storage fixtures for the Wave 2 stack.

### Seed only the migration stack

```bash
python ./scripts/dev.py seed-data
```

### Run the maintained API contract smoke harness

```bash
python ./scripts/dev.py contract-smoke --start-workers
```

This uses the maintained smoke harness under `tests/contract-smoke`.

For local migration runs, the CLI automatically fetches seeded role-appropriate Supabase tokens:

- developer token for player/developer endpoints
- moderator token for moderation endpoints

Useful migration flags:

- `--start-workers`
- `--developer-token`
- `--moderator-token`
- `--seed-user-email`
- `--moderator-email`
- `--seed-user-password`

### Run the Wave 2 Workers flow smoke suite

```bash
python ./scripts/dev.py workers-smoke --start-stack
```

This command verifies the local Supabase + Workers stack end to end, including:

- public catalog list/detail
- current-user bootstrap and profile mutation
- developer enrollment and studio workspace flows
- studio link CRUD
- studio logo upload and retrieval
- moderation developer verification flows

### Run browser parity smoke and screenshot comparison coverage

```bash
python ./scripts/dev.py parity-test
```

This command runs the Playwright-based parity suite under `tests/parity` against an already running reference frontend.

### Refresh the committed screenshot baselines

```bash
python ./scripts/dev.py capture-parity-baseline
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

This command runs maintained backend verification, frontend tests, OpenAPI lint, and API contract tests in one pass.

To include the maintained contract run against the local Supabase + Workers stack:

```bash
python ./scripts/dev.py all-tests --start-workers
```

### Run the main repository verification workflow

```bash
python ./scripts/dev.py verify --skip-contract-tests
```

Include the maintained contract tests in the same pass:

```bash
python ./scripts/dev.py verify --start-workers
```

This workflow validates the maintained backend, lints the OpenAPI spec, and optionally executes the Postman contract suite.

### Authenticate Postman CLI for workspace or mock operations

```bash
python ./scripts/dev.py api-login --postman-api-key <your-postman-api-key>
```

If you prefer not to keep a separate login step, `api-mock` and `api-sync` also accept `--postman-api-key` directly.

### Lint the API contract

```bash
python ./scripts/dev.py api-lint
```

### Run API contract tests against the local Workers stack

```bash
python ./scripts/dev.py api-test --start-workers
```

Important for live local runs:

- the root CLI starts or reuses local Supabase services, reseeds deterministic auth/data/storage fixtures, and starts the Workers API
- the root CLI resolves seeded developer and moderator access tokens automatically for authenticated contract checks
- the committed environment template keeps only the maintained Wave 2 variables for the current contract surface

If the Workers API is already running and seeded:

```bash
python ./scripts/dev.py api-test --skip-lint
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

## Configuration Overrides

Workflow-specific overrides remain available where they still map to the maintained stack. Common examples:

- `api-test --environment <path>`
- `api-test --base-url <url>`
- `api-test --contract-execution-mode live|mock`
- `api-lint`
- `api-mock --mode shared|ephemeral`
- `api-sync --skip-mock`
- `web`
- `web-status`
- `web-stop --down-dependencies`
- `frontend`
- `seed-data --seed-password <value>`
- `spa install|build|run`
- `workers install|build|run`
- `supabase start|stop|status|db-reset`
- `contract-smoke --start-workers`
- `workers-smoke --start-stack`
- `parity-test`
- `capture-parity-baseline`
- `deploy-staging --dry-run`

For live API contract execution, the default environment template is:

- `api/postman/environments/board-enthusiasts_local.postman_environment.json`

The root CLI can populate the maintained authenticated contract checks automatically for the local Workers stack by resolving seeded developer and moderator tokens.

## Notes

- The `up`, `down`, and `status` commands now target the maintained local Supabase dependency path.
- The Wave 1 and Wave 2 migration scaffolding expects `node`, `npm`, `supabase`, and `wrangler`.
- VS Code tasks in this repo call the Python CLI directly.
- The supported developer entry point for this repository is `python ./scripts/dev.py ...`; API-local helper scripts under `api/scripts/` are implementation details for CI and the root CLI.
- Tool executables are resolved from each developer's `PATH`; the CLI does not assume fixed install directories for `node`, `npx`, `postman`, `supabase`, `wrangler`, `docker`, or other required tools.
- Migration workspace dependency installs are now cached by lockfile fingerprint so routine Wave 2 commands do not reinstall the entire npm workspace unnecessarily.


