# board-enthusiasts

A solution for third party developers for the Board ecosystem to use to register and share their games with the public.

Current implementation status:

- the maintained backend runtime now lives in the [`backend`](backend) submodule as Supabase + Cloudflare Workers
- the maintained executable API contract now lives in the [`api`](api) submodule and targets the Workers/Supabase surface only
- the current SPA under [`apps/spa`](apps/spa) is still an in-progress migration shell; Wave 3 remains responsible for the full frontend cutover
- the current migration wave is Wave 2 platform and API cutover for the Cloudflare, Supabase, and Workers conversion plan

## Table of Contents

- [Getting started in this repository](#getting-started-in-this-repository)
- [Docs](#docs)
- [Planning](#planning)
- [Developer Automation](#developer-automation)

## Getting started in this repository

This repository currently tracks backend and frontend as git submodules.

Quick start (maintained local migration stack from the root workspace):

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web
```

This starts local Supabase services, the maintained Workers backend, and the migration SPA.

Quick start (backend API only):

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

See the dedicated CLI doc for full command coverage and options:

- [`docs/developer-cli.md`](docs/developer-cli.md)

Examples:

```bash
python ./scripts/dev.py doctor
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web
python ./scripts/dev.py web-status
python ./scripts/dev.py web-stop --down-dependencies
python ./scripts/dev.py frontend
python ./scripts/dev.py up
python ./scripts/dev.py all-tests
python ./scripts/dev.py verify --skip-contract-tests
python ./scripts/dev.py api-lint
python ./scripts/dev.py api-test --start-workers
python ./scripts/dev.py test
python ./scripts/dev.py down
python ./scripts/dev.py spa run
python ./scripts/dev.py workers run
python ./scripts/dev.py supabase status
python ./scripts/dev.py contract-smoke --start-workers
python ./scripts/dev.py workers-smoke --start-stack
python ./scripts/dev.py parity-test
python ./scripts/dev.py deploy-staging --dry-run
```
