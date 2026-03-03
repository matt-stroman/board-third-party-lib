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
- [Database Backup and Restore](#database-backup-and-restore)
- [Configuration Overrides](#configuration-overrides)
- [Notes](#notes)

## Purpose

The developer CLI orchestrates common local development tasks from the repository root:

- bootstrap submodules and restore backend dependencies
- run the full local web stack from the repository root
- inspect/stop the locally launched root web stack
- run the frontend web UI from the repository root
- start/stop/reuse local PostgreSQL and Keycloak via Docker Compose
- run the backend API
- validate backend XML documentation coverage
- run backend tests
- authenticate Postman CLI when Postman workspace or mock operations are needed
- lint the Git-tracked OpenAPI specification with Redocly CLI
- run API contract tests
- provision/sync Postman mocks and workspace artifacts
- run environment diagnostics
- create/restore local PostgreSQL SQL backups

## Primary Entry Point

Command:

```bash
python ./scripts/dev.py <command> [options]
```

## Common Workflows

### First-time setup + run

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --watch-css
```

This starts Docker dependencies, the backend API, the frontend web app, and then opens the frontend URL in your default browser. On Windows, if Docker Desktop is installed but not already running, the CLI will try to launch it automatically and wait for the daemon before continuing. The root workflow is HTTPS-first for frontend, backend, and Keycloak, and it also exports localhost TLS material for the local PostgreSQL container. It will launch the frontend at `https://localhost:7277`, the backend at `https://localhost:7085`, and Keycloak at `https://localhost:8443`, while local PostgreSQL rejects non-TLS TCP connections.

If you only want to run the frontend from the root workspace:

```bash
python ./scripts/dev.py frontend --watch-css
```

If you want to run API contract tests from the same terminal session without manually keeping the backend open, use:

```bash
python ./scripts/dev.py api-test --start-backend --skip-lint
```

### Run the full local web stack

```bash
python ./scripts/dev.py web
python ./scripts/dev.py web --watch-css
```

Useful flags:

- `--watch-css`
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

### Run the frontend web UI

```bash
python ./scripts/dev.py frontend
python ./scripts/dev.py frontend --watch-css
```

Useful flags:

- `--watch-css`
- `--skip-npm-install`
- `--skip-css-build`
- `--skip-restore`

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

- the committed local environment file contains placeholder values for authenticated and persistence-backed success paths such as `accessToken`, `organizationId`, `organizationSlug`, `titleId`, and `titleSlug`
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
- `web --watch-css`
- `web-status`
- `web-stop --down-dependencies`
- `frontend --watch-css`

For live API contract execution, the default environment template is:

- `api/postman/environments/board-third-party-library_local.postman_environment.json`

Populate the placeholder auth and resource IDs in a private copy when you want full authenticated create/update coverage against a local backend.

## Notes

- The `up`, `down`, and `status` commands manage the local PostgreSQL and Keycloak containers together.
- The `down` command uses `docker compose down` and does **not** remove named volumes. Your local Postgres data persists unless you explicitly remove volumes.
- VS Code tasks in this repo call the Python CLI directly.
- The supported developer entry point for this repository is `python ./scripts/dev.py ...`; API-local helper scripts under `api/scripts/` are implementation details for CI and the root CLI.
- Tool executables are resolved from each developer's `PATH`; the CLI does not assume fixed install directories for `dotnet`, `node`, `npx`, `postman`, `docker`, or other required tools.
