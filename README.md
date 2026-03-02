# board-third-party-lib

A solution for third party developers for the Board ecosystem to use to register and share their games with the public.

Current implementation status:

- the maintained API/backend surface includes the Keycloak-backed identity and health foundation plus Wave 1 persistence, Wave 2 organizations/memberships, Wave 3 titles/versioned metadata, and Wave 4 media/releases/APK artifact metadata
- EF Core migrations for `users`, `user_board_profiles`, `organizations`, `organization_memberships`, `titles`, `title_metadata_versions`, `title_media_assets`, `title_releases`, and `release_artifacts` are implemented
- the next planned implementation wave is Wave 5 external acquisition bindings

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
  - Current title/catalog schema, lifecycle, media, and release model: [`backend/docs/title-catalog-schema.md`](backend/docs/title-catalog-schema.md)

## Planning

- Current planning and implementation alignment:
  - Current architecture and wave alignment: [`planning/current-state-and-wave-plan.md`](planning/current-state-and-wave-plan.md)
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
python ./scripts/dev.py up
python ./scripts/dev.py api-lint
python ./scripts/dev.py api-test --start-backend
python ./scripts/dev.py test
python ./scripts/dev.py down
```
