# board-third-party-lib

A solution for third party developers for the Board ecosystem to use to register and share their games with the public.

Current implementation status:

- the maintained API/backend surface is a Keycloak-backed identity and health foundation
- EF Core migrations and application-owned persistence waves are planned next, not already implemented

## Table of Contents

- [Getting started in this repository](#getting-started-in-this-repository)
- [Docs](#docs)
- [Planning](#planning)
- [Developer Automation](#developer-automation)

## Getting started in this repository

This repository currently tracks backend and frontend as git submodules.

Quick start (backend API + local PostgreSQL + Keycloak via automation):

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
- Backend-specific developer docs (in backend submodule):
  - Backend phase 1 (PostgreSQL local setup): [`backend/docs/backend-phase-1-postgres-setup.md`](backend/docs/backend-phase-1-postgres-setup.md)
  - New developer setup / quick start (current backend MVP): [`backend/docs/new-developer-setup.md`](backend/docs/new-developer-setup.md)
  - Auth and data ownership boundary: [`backend/docs/auth-data-ownership.md`](backend/docs/auth-data-ownership.md)

## Planning

- Project-wide planning and recommendation artifacts:
  - Current architecture and wave alignment: [`planning/current-state-and-wave-plan.md`](planning/current-state-and-wave-plan.md)
  - Technology recommendation: [`planning/technology-fit-recommendation.md`](planning/technology-fit-recommendation.md)
- Backend planning artifacts:
  - Backend schema implementation plan: [`backend/planning/mvp-schema-implementation-plan.md`](backend/planning/mvp-schema-implementation-plan.md)
- API planning artifacts:
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
python ./scripts/dev.py up
python ./scripts/dev.py test
python ./scripts/dev.py down
```
