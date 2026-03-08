# Maintained Stack

The maintained Board Enthusiasts stack consists of:

- a React + TypeScript SPA in [`frontend`](../frontend)
- a Cloudflare Workers API in [`backend/apps/workers-api`](../backend/apps/workers-api)
- Supabase Auth, Postgres, and Storage configured under [`backend/supabase`](../backend/supabase)

## Local Workflow

Use the root CLI for all routine local work:

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --hot-reload
```

That starts:

- local Supabase services
- the Workers API
- the Vite SPA dev server

Other maintained runtime entrypoints:

```bash
python ./scripts/dev.py database up
python ./scripts/dev.py auth up
python ./scripts/dev.py api
python ./scripts/dev.py seed-data
python ./scripts/dev.py api-test --start-workers
python ./scripts/dev.py verify --start-workers
```

Useful notes:

- `database`, `auth`, `api`, and `web` are the supported local runtime profiles.
- `web --hot-reload` keeps the SPA and Workers API in watch-mode development.
- `api down` and `web down` stop only the named service by default; add `--include-dependencies` to stop lower-level services as well.
- `api status` and `web status` report only the named service by default; add `--include-dependencies` to include dependencies.

## Maintained Surface

The maintained application surface includes:

- public catalog and studio browsing
- Supabase Auth sign-in and sign-out
- player profile and developer enrollment
- developer studio CRUD, studio link CRUD, and studio media uploads
- moderation developer verification

## Validation

Primary validation paths:

```bash
python ./scripts/dev.py all-tests
python ./scripts/dev.py contract-smoke --start-workers
python ./scripts/dev.py workers-smoke --start-stack
python ./scripts/dev.py parity-test
```
