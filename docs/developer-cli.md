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

### Inspect or bootstrap the root-managed environment files

```bash
python ./scripts/dev.py env local --copy-example
python ./scripts/dev.py env local --open
python ./scripts/dev.py env staging --copy-example
python ./scripts/dev.py env staging --open
python ./scripts/dev.py env staging --sync-github-environment
```

The maintained root CLI owns the shared environment-file layout under [`config/`](../config):

- [`config/.env.local.example`](../config/.env.local.example) -> copy to `config/.env.local` for local CLI/runtime overrides
- [`config/.env.staging.example`](../config/.env.staging.example) -> copy to `config/.env.staging` for staging deployment inputs
- [`config/.env.example`](../config/.env.example) -> copy to `config/.env` for future production deployment inputs

The live `.env` files are intentionally ignored and must not be committed.

You can also publish the current staging or production env file directly into the matching GitHub Environment:

```bash
python ./scripts/dev.py env staging --sync-github-environment
python ./scripts/dev.py env production --sync-github-environment
```

Useful flags:

- `--github-environment <name>` to override the target GitHub Environment name
- `--repo <owner/name>` to target a specific repo with `gh`

The sync command uses the same maintained variable/secret split documented for the GitHub Actions deploy workflow:

- public/runtime-safe values become GitHub Environment `vars`
- server-only values become GitHub Environment `secrets`

Blank values are skipped rather than published.

When you run a local hosted deploy, preflight now also validates that the matching GitHub Environment stays in sync with the checked-out root env file:

- `deploy --staging` checks GitHub Environment `staging` against `config/.env.staging`
- `deploy` checks GitHub Environment `production` against `config/.env`

Current limitation:

- GitHub exposes Environment variable values and secret names
- GitHub does not expose secret values back to clients
- so preflight can prove:
  - variable values match
  - required secret names exist
- but it cannot prove the current secret values still match the local file

### First-time setup + run

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --hot-reload
```

This starts local Supabase services, the maintained Workers backend, and the SPA, then opens the frontend URL in your default browser.
If the local Supabase volume is empty, `api` and `web` automatically seed the deterministic demo catalog before the backend starts.

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
- `--landing-mode`
- `--include-dependencies` for `web down` and `web status`

For the landing-page-only production wave, you can run the local SPA in the same mode with:

```bash
python ./scripts/dev.py web --hot-reload --landing-mode
```

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
- `api` and `web` automatically seed deterministic demo data when the local Supabase stack has no catalog rows yet.
- `api` and `web` also detect when the running local Supabase schema is missing required checked-in tables from newer migrations; in that case they automatically run the local reset/reseed flow before startup continues.
- `web --hot-reload` keeps Vite and Wrangler in their watch-based local development mode.
- `web --landing-mode` starts the SPA in the production landing-page-only mode while keeping the same local Workers and Supabase stack behind it.
- `api down` stops the backend service only by default; add `--include-dependencies` to also stop auth and database services.
- `web down` stops the frontend service only by default; add `--include-dependencies` to also stop API, auth, and database services.
- `status` reports only the named service by default; add `--include-dependencies` to include dependency status output.
- Local auth-facing profiles keep the Supabase email catcher available for signup and recovery flows. When `auth`, `api`, or `web` is running, open [http://127.0.0.1:55424](http://127.0.0.1:55424) to inspect local confirmation and recovery emails.
- The maintained local Supabase config sets the sender to `Board Enthusiasts <noreply@boardenthusiasts.com>` in [`backend/supabase/config.toml`](../backend/supabase/config.toml). The checked-in branded HTML templates live under [`backend/supabase/templates/`](../backend/supabase/templates/). If a hosted Supabase project is used for staging or production, mirror both that sender identity and those template bodies in the hosted Auth email settings.
- Hosted Supabase Auth redirect allowlists must include the maintained SPA callback routes, not just the site origin. At minimum mirror the local pattern for `/auth/signin` and `/auth/signin?mode=recovery` on each hosted frontend origin.
- The maintained web UI now supports both the email link and the Supabase `{code}` value for signup confirmation and password recovery, and the checked-in templates surface both paths in the branded message body.
- Signup persists `firstName` and `lastName` into Supabase auth user metadata, and the maintained email templates greet the recipient by first name when that metadata is present.
- Hosted frontend runtime configuration must use HTTPS for both `VITE_SUPABASE_URL` and `VITE_API_BASE_URL`. The SPA only permits plain HTTP for loopback local development endpoints.
- On Windows, Docker-backed Supabase commands attempt to launch Docker Desktop automatically when the daemon is unavailable. If `supabase stop` stalls, the CLI falls back to project-scoped Docker container cleanup instead of waiting indefinitely.

### Seed the local stack

```bash
python ./scripts/dev.py seed-data
```

This refreshes the running local Supabase stack with the full checked-in demo catalog fixture set, including the broader browse/studio seed data used by the maintained UI.
Use it when you intentionally want to refresh demo rows after changing seed definitions or media; you should not need it just to pick up newly pulled local migrations when starting `api` or `web`.

The maintained local seed roster currently includes 24 users:
- player coverage across the full roster
- 6 developer-capable users
- 2 moderators
- 1 admin
- 1 super admin

Primary seeded accounts:
- developer: `emma.torres@boardtpl.local`
- moderator/admin: `alex.rivera@boardtpl.local`
- password: `ChangeMe!123`

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

### Run hosted deploy validation and publish flows

```bash
python ./scripts/dev.py deploy --staging --preflight-only
python ./scripts/dev.py deploy --staging --dry-run-only
python ./scripts/dev.py deploy --staging
python ./scripts/dev.py deploy
python ./scripts/dev.py deploy --staging --source-branch staging
```

`deploy` automatically loads the target environment file before running the hosted deploy flow:

- `python ./scripts/dev.py deploy --staging` uses `config/.env.staging`
- `python ./scripts/dev.py deploy` uses `config/.env`

The environment file is the canonical operator-owned input source for hosted deploy values such as:

- `BOARD_ENTHUSIASTS_SPA_BASE_URL`
- `BOARD_ENTHUSIASTS_WORKERS_BASE_URL`
- `SUPABASE_URL`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_PASSWORD`
- `SUPABASE_ACCESS_TOKEN`
- `VITE_TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`
- `BREVO_API_KEY`
- `BREVO_SIGNUPS_LIST_ID`
- `DEPLOY_SMOKE_SECRET`

`SUPABASE_URL` remains supported everywhere. When `SUPABASE_URL` is blank and `SUPABASE_PROJECT_REF` is set, the root CLI infers the default hosted URL as `https://<project-ref>.supabase.co`.

Precedence rules:

- explicit `SUPABASE_URL` wins
- otherwise the CLI infers the default hosted URL from `SUPABASE_PROJECT_REF`
- local development should keep an explicit local `SUPABASE_URL`
- custom domains and vanity subdomains should keep an explicit `SUPABASE_URL`

`deploy` always runs the following sequence for the selected target:

1. preflight checks
2. dry-run validation
3. resumable transactional deploy stages
4. post-deploy smoke tests

The transactional stages currently cover:

- hosted Supabase schema migration
- hosted Supabase bucket provisioning
- Cloudflare Pages project creation
- Cloudflare Worker deploy
- Cloudflare Pages deploy

Completed deploy stages are tracked locally under `.dev-cli-logs/deploy-<target>-state.json`.
If a later rerun uses the same source fingerprint, the CLI skips already completed stages and reruns the smoke tests.

Use these flags when needed:

- `--force`: rerun every deploy stage from scratch
- `--upgrade`: replace a saved stage-state fingerprint with the current source fingerprint
- `--preflight-only`: stop after provider/config validation
- `--dry-run-only`: stop after preflight plus dry-run validation
- `--source-branch <name>`: override the Git branch name attached to the hosted Pages deploy metadata

When `deploy` runs a real Workers deployment, it also syncs the Cloudflare Worker secrets from that same root environment file before deploying the Worker bundle, including `DEPLOY_SMOKE_SECRET` for the post-deploy signup smoke.

### Run hosted deploys from the GitHub web UI

The root repo also exposes the same deploy workflow through GitHub Actions:

- open `Actions` in GitHub
- select `Manual Deploy`
- choose the target environment:
  - `staging`
  - `production`
- optionally enable:
  - `force`
  - `upgrade`
  - `preflight_only`
  - `dry_run_only`

The workflow writes the matching root environment file on the runner and then calls the maintained CLI:

- `python ./scripts/dev.py deploy --staging` for `staging`
- `python ./scripts/dev.py deploy` for `production`

The manual workflow also passes the triggering Git ref name into the CLI, so Pages deploys are attached to the actual release branch you launched from instead of always being recorded against `main`.

The workflow expects GitHub Environment-scoped configuration named exactly like the root `.env` keys. Recommended setup:

- GitHub Environment `staging`
- GitHub Environment `production`

Typical Environment `vars`:

- `BOARD_ENTHUSIASTS_SPA_BASE_URL`
- `BOARD_ENTHUSIASTS_WORKERS_BASE_URL`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_AVATARS_BUCKET`
- `SUPABASE_CARD_IMAGES_BUCKET`
- `SUPABASE_HERO_IMAGES_BUCKET`
- `SUPABASE_LOGO_IMAGES_BUCKET`
- `CLOUDFLARE_ACCOUNT_ID`
- `VITE_TURNSTILE_SITE_KEY`
- `BREVO_SIGNUPS_LIST_ID`
- `ALLOWED_WEB_ORIGINS`
- `SUPPORT_REPORT_RECIPIENT`
- `SUPPORT_REPORT_SENDER_EMAIL`
- `SUPPORT_REPORT_SENDER_NAME`
- `VITE_LANDING_MODE`

For Worker deploys that use a custom API hostname from `BOARD_ENTHUSIASTS_WORKERS_BASE_URL`, the root CLI now renders a Worker custom-domain route automatically. Do not create a standalone Cloudflare DNS record for that hostname ahead of time; preflight will fail until the conflicting DNS record is removed because the Worker custom domain needs to own the hostname directly.

For Pages deploys that use a custom SPA hostname from `BOARD_ENTHUSIASTS_SPA_BASE_URL`, the root CLI now attaches the Pages custom domain through Cloudflare and keeps the proxied CNAME pointed at the current branch alias for the target project. Do not configure that hostname as a Cloudflare Email Routing subdomain, and do not keep multiple DNS records on the same hostname. The deploy flow expects zero or one proxied CNAME record for the SPA hostname.

Typical Environment `secrets`:

- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_PASSWORD`
- `SUPABASE_ACCESS_TOKEN`
- `CLOUDFLARE_API_TOKEN`
- `TURNSTILE_SECRET_KEY`
- `BREVO_API_KEY`
- `DEPLOY_SMOKE_SECRET`

Optional future hosted-auth values can also be provided there when needed:

- `SUPABASE_AUTH_GITHUB_CLIENT_ID`
- `SUPABASE_AUTH_GITHUB_CLIENT_SECRET`
- `SUPABASE_AUTH_GOOGLE_CLIENT_ID`
- `SUPABASE_AUTH_GOOGLE_CLIENT_SECRET`

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
It also runs the maintained workspace-wide TypeScript typecheck before the backend and frontend suites.

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
It also covers the maintained workspace-wide TypeScript typecheck, frontend tests, and the root Python CLI tests.

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
- `deploy --staging --dry-run-only`
- `env <local|staging|production> [--copy-example] [--open]`

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
- The root-managed `.env` files are operator/developer inputs for the root CLI. Hosted runtime secrets still live in provider secret/config stores such as Cloudflare Workers secrets and hosted Supabase provider settings.


