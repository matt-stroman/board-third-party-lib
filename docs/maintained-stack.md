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

To run the landing-page-only production mode locally:

```bash
python ./scripts/dev.py web --hot-reload --landing-mode
```

That starts:

- local Supabase services
- the Workers API
- the Vite SPA dev server

If the local Supabase volume is empty, the `api` and `web` entrypoints auto-seed the deterministic demo catalog before the Workers API starts.

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
- `web --landing-mode` switches the SPA into the landing-page-only production wave while keeping the same local backend stack running.
- `api` and `web` automatically seed deterministic demo data when the local Supabase stack has no catalog rows yet.
- `seed-data` refreshes the full checked-in local demo catalog fixture set, including the broader browse/studio sample surface.
- the maintained seed roster includes 24 local users, including player-heavy coverage plus developer, moderator, admin, and super-admin accounts.
- `api down` and `web down` stop only the named service by default; add `--include-dependencies` to stop lower-level services as well.
- `api status` and `web status` report only the named service by default; add `--include-dependencies` to include dependencies.
- Root-managed environment files live under [`config/`](../config). Use [`python ./scripts/dev.py env ...`](../scripts/dev.py) to inspect or bootstrap `config/.env.local`, `config/.env.staging`, and `config/.env`.

## Maintained Surface

The maintained application surface includes:

- public catalog and studio browsing
- Supabase Auth sign-in and sign-out
- player profile and developer enrollment
- developer studio CRUD, studio link CRUD, and studio media uploads
- moderation developer verification

## Credential Handling

- The maintained sign-in, registration, confirmation, and password-recovery forms submit credentials directly from the browser to Supabase Auth through [`@supabase/supabase-js`](../frontend/src/auth.tsx).
- User passwords are not sent to the maintained Workers API routes, are not stored in the application database, and are not re-emitted by the frontend API helpers.
- The SPA runtime now rejects non-HTTPS hosted values for `VITE_SUPABASE_URL` and `VITE_API_BASE_URL`; only local loopback `http://localhost`, `http://127.0.0.1`, and `http://[::1]` endpoints are allowed for local development.
- The maintained frontend expects `VITE_SUPABASE_PUBLISHABLE_KEY` for the browser-facing Supabase client key, while the maintained Workers backend expects `SUPABASE_SECRET_KEY` for privileged server-side access.
- This stack intentionally does not add client-side password hashing on top of Supabase Auth. Without a challenge-based protocol, that would only replace the password with another replayable secret. Transport confidentiality is provided by HTTPS in hosted environments.

## Validation

Primary validation paths:

```bash
python ./scripts/dev.py all-tests
python ./scripts/dev.py contract-smoke --start-workers
python ./scripts/dev.py workers-smoke --start-stack
python ./scripts/dev.py parity-test
```

`all-tests` and `verify` both include the maintained workspace-wide TypeScript typecheck so contract, Workers, and SPA packages are checked together before the rest of the validation flow runs.
