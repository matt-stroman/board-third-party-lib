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
- [Maintained Stack Workflows](#maintained-stack-workflows)
- [Configuration Overrides](#configuration-overrides)
- [Notes](#notes)

## Purpose

The developer CLI orchestrates common local development tasks from the repository root:

- bootstrap submodules and install maintained workspace dependencies
- run the maintained local runtime profiles for database, auth, API, and full web UI testing
- run maintained backend verification
- run all major validation checks in one pass (maintained backend tests + root CLI tests + frontend tests + API lint + API contract)
- authenticate Postman CLI when Postman workspace or mock operations are needed
- lint the Git-tracked OpenAPI specification with Redocly CLI
- run API contract tests
- provision/sync Postman mocks and workspace artifacts
- run environment diagnostics
- seed deterministic local auth/catalog sample data for UI/UX testing
- run parity baselines, seeded Supabase data, and staging deployment wrappers

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

This starts local Supabase services, the maintained Workers backend, and the SPA, then opens the frontend URL in your default browser.

If you only want the API stack:

```bash
python ./scripts/dev.py api
```

If you want to run API contract tests from the same terminal session without manually keeping the Workers stack open, use:

```bash
python ./scripts/dev.py api-test --start-workers --skip-lint
```

### Run the maintained local runtime profiles

```bash
python ./scripts/dev.py database up
python ./scripts/dev.py auth up
python ./scripts/dev.py api
python ./scripts/dev.py web --hot-reload
```

These map directly to the supported local testing scenarios:

- `database up|down|status`: PostgreSQL only
- `auth up|down|status`: PostgreSQL + Supabase Auth
- `api up|down|status`: PostgreSQL + Supabase Auth + Workers backend
- `web [up]|down|status`: PostgreSQL + Supabase Auth + Workers backend + SPA

For `down` and `status`, add `--include-dependencies` when you want the command to traverse the dependency chain instead of operating only on the named service.

The maintained frontend runs through the Vite SPA dev server, while the maintained backend runs through Wrangler against local Supabase services.

Useful `web` flags:

- `--no-browser`
- `--skip-install`
- `--hot-reload`
- `--include-dependencies` for `web down` and `web status`

### Seed local sample data for the maintained stack

```bash
python ./scripts/dev.py seed-data
```

This command:

- ensures local Supabase services are running
- provisions/updates deterministic local Supabase auth users
- validates the checked-in title and studio media bundles under `frontend/public/seed-catalog`
- repopulates local Supabase studio/title/media data used by the maintained Workers surface
- seeds public studio banners plus studio support/social links alongside the studio records

The seed data references those static local asset URLs directly, so rerunning the command refreshes the database state without regenerating art at runtime.
Title card/hero/logo media should be checked-in PNGs, while studio logos remain SVGs. Studio banners use checked-in PNGs when available and otherwise fall back to the checked-in SVG variants.

Useful flags:

- `--seed-password`

## Maintained Stack Workflows

Reference doc:

- [`docs/maintained-stack.md`](./maintained-stack.md)

### Start the maintained local runtime profiles

```bash
python ./scripts/dev.py database up
python ./scripts/dev.py auth up
python ./scripts/dev.py api
python ./scripts/dev.py web --hot-reload
```

The profile commands are the maintained entrypoints for local runtime work. Use the matching `down` and `status` actions when needed:

```bash
python ./scripts/dev.py database status
python ./scripts/dev.py auth down
python ./scripts/dev.py api status
python ./scripts/dev.py web down
python ./scripts/dev.py api down --include-dependencies
python ./scripts/dev.py web status --include-dependencies
```

Profile notes:

- `database up` uses `supabase db start` to launch PostgreSQL only.
- `auth up` uses a filtered `supabase start -x ...` profile that keeps only the services needed for auth testing.
- `api` and `web` use filtered Supabase profiles plus the maintained Workers and SPA dev servers.
- `web --hot-reload` keeps Vite and Wrangler in their watch-based local development mode.
- `api down` stops the backend service only by default; add `--include-dependencies` to also stop auth and database services.
- `web down` stops the frontend service only by default; add `--include-dependencies` to also stop API, auth, and database services.
- `status` reports only the named service by default; add `--include-dependencies` to include dependency status output.

### Seed the local stack

```bash
python ./scripts/dev.py seed-data
```

### Run the maintained API contract smoke harness

```bash
python ./scripts/dev.py contract-smoke --start-workers
```

This uses the maintained smoke harness under `tests/contract-smoke`.

For local runs, the CLI automatically fetches seeded role-appropriate Supabase tokens:

- developer token for player/developer endpoints
- moderator token for moderation endpoints

Useful flags:

- `--start-workers`
- `--developer-token`
- `--moderator-token`
- `--seed-user-email`
- `--moderator-email`
- `--seed-user-password`

### Run the Workers flow smoke suite

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

### Check local tool and environment status

```bash
python ./scripts/dev.py doctor
python ./scripts/dev.py database status
python ./scripts/dev.py web status
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
- the committed environment template keeps only the maintained variables for the current contract surface

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
- `database up|down|status`
- `auth up|down|status`
- `api up|down|status`
- `web [up]|down|status`
- `api down|status --include-dependencies`
- `web down|status --include-dependencies`
- `seed-data --seed-password <value>`
- `contract-smoke --start-workers`
- `workers-smoke --start-stack`
- `parity-test`
- `capture-parity-baseline`
- `deploy-staging --dry-run`

For live API contract execution, the default environment template is:

- `api/postman/environments/board-enthusiasts_local.postman_environment.json`

The root CLI can populate the maintained authenticated contract checks automatically for the local Workers stack by resolving seeded developer and moderator tokens.

## Notes

- The maintained local runtime entrypoints are `database`, `auth`, `api`, and `web`.
- The maintained stack expects `node`, `npm`, `supabase`, and `wrangler`.
- VS Code tasks in this repo call the Python CLI directly.
- The supported developer entry point for this repository is `python ./scripts/dev.py ...`; API-local helper scripts under `api/scripts/` are implementation details for CI and the root CLI.
- Tool executables are resolved from each developer's `PATH`; the CLI does not assume fixed install directories for `node`, `npx`, `postman`, `supabase`, `wrangler`, `docker`, or other required tools.
- Migration workspace dependency installs are cached by lockfile fingerprint so routine commands do not reinstall the entire npm workspace unnecessarily.


