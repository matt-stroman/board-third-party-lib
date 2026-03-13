# board-enthusiasts

A solution for third party developers for the Board ecosystem to use to register and share their games with the public.

Current implementation status:

- the maintained backend runtime now lives in the [`backend`](backend) submodule as Supabase + Cloudflare Workers
- the maintained executable API contract now lives in the [`api`](api) submodule and targets the Workers/Supabase surface only
- the maintained frontend runtime now lives in the [`frontend`](frontend) submodule as a React + TypeScript SPA

## Table of Contents

- [Getting started in this repository](#getting-started-in-this-repository)
- [Docs](#docs)
- [Planning](#planning)
- [Developer Automation](#developer-automation)

## Getting started in this repository

This repository currently tracks backend and frontend as git submodules.

Quick start (maintained local stack from the repository root):

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --hot-reload
```

This starts local Supabase services, the maintained Workers backend, and the SPA.
If the local Supabase volume is empty, the `api` and `web` entrypoints automatically seed the deterministic demo catalog before the backend starts.
If the running local Supabase schema is missing required checked-in tables from newer migrations, `api` and `web` automatically reset the local database and reseed before continuing.
Run `python ./scripts/dev.py seed-data` whenever you want to refresh the full checked-in local demo catalog fixture set after seed changes.

Quick start (backend API only):

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py api
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
  - Maintained stack overview: [`docs/maintained-stack.md`](docs/maintained-stack.md)
- Backend-specific developer docs (in backend submodule):
  - Backend local runbook: [`backend/docs/workers-backend-local-runbook.md`](backend/docs/workers-backend-local-runbook.md)

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
- root-managed environment files:
  - [`config/.env.local.example`](config/.env.local.example)
  - [`config/.env.staging.example`](config/.env.staging.example)
  - [`config/.env.example`](config/.env.example)

See the dedicated CLI doc for full command coverage and options:

- [`docs/developer-cli.md`](docs/developer-cli.md)

Examples:

```bash
python ./scripts/dev.py doctor
python ./scripts/dev.py bootstrap
python ./scripts/dev.py database up
python ./scripts/dev.py auth up
python ./scripts/dev.py api
python ./scripts/dev.py api down
python ./scripts/dev.py api down --include-dependencies
python ./scripts/dev.py web --hot-reload
python ./scripts/dev.py web status
python ./scripts/dev.py web status --include-dependencies
python ./scripts/dev.py web down
python ./scripts/dev.py web down --include-dependencies
python ./scripts/dev.py all-tests
python ./scripts/dev.py verify --skip-contract-tests
python ./scripts/dev.py api-lint
python ./scripts/dev.py api-test --start-workers
python ./scripts/dev.py test
python ./scripts/dev.py contract-smoke --start-workers
python ./scripts/dev.py workers-smoke --start-stack
python ./scripts/dev.py parity-test
python ./scripts/dev.py deploy-staging --dry-run
python ./scripts/dev.py env staging --copy-example
python ./scripts/dev.py env staging --open
```

The supported root-managed environment files live under [`config/`](config):

- `config/.env.local`: local developer overrides used by the root CLI for local runtime workflows
- `config/.env.staging`: staging deployment/operator values used by `deploy-staging`
- `config/.env`: reserved for future production deployment/operator values

Do not commit those live `.env` files. Only the checked-in `*.example` templates should be tracked.
