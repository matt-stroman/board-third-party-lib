# Cloudflare, Supabase, and Workers Wave 3 Frontend Cutover

Wave 3 replaces the maintained frontend runtime with the React SPA in the [`frontend`](../frontend) submodule and removes the legacy Blazor frontend from the active local workflow.

## Scope

Wave 3 delivers:

- the maintained SPA route surface for `/`, `/browse`, public studio/title detail, `/player`, `/develop`, and `/moderate`
- Supabase Auth sign-in and sign-out for the maintained local and staging frontend flows
- developer studio create/update/delete, link CRUD, and studio media upload from the SPA
- moderation verification workflow from the SPA
- root developer automation pointed at the `frontend` submodule instead of the removed root `apps/spa` scaffold

## Local Commands

Default local workflow after cutover:

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py web --hot-reload
```

That path starts:

- local Supabase services
- the Workers API
- the Vite SPA dev server from [`frontend`](../frontend)

Other common local commands:

```bash
python ./scripts/dev.py database up
python ./scripts/dev.py auth up
python ./scripts/dev.py api
python ./scripts/dev.py web down
python ./scripts/dev.py seed-data
python ./scripts/dev.py verify --start-workers
python ./scripts/dev.py api-test --start-workers
python ./scripts/dev.py parity-test
```

Helpful notes:

- `database`, `auth`, `api`, and `web` are the maintained local runtime entrypoints after cutover.
- `web --hot-reload` keeps the Vite SPA and Wrangler backend in their watch-based local development mode.
- `seed-data` now reads checked-in media from [`frontend/public/seed-catalog`](../frontend/public/seed-catalog).
- `verify` now includes maintained frontend tests in addition to backend, root CLI, and API validation.

## Local Frontend Verification

Verified locally during Wave 3 implementation:

```bash
npm run typecheck --prefix frontend
npm run test --prefix frontend
python -m unittest discover -s tests/root_cli -p "test_*.py"
```

## Cutover Outcome

After Wave 3:

- the maintained frontend lives only in [`frontend`](../frontend)
- the root repo no longer maintains a duplicate SPA shell under `apps/spa`
- the old Blazor frontend runtime and test project are removed from the frontend submodule
