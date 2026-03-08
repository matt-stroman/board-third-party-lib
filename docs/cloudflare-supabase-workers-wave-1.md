# Cloudflare, Supabase, and Workers Wave 1 Foundation

Wave 1 establishes the migration workspace and verification baseline without cutting over runtime behavior yet.

## Local Tooling

Required for Wave 1 migration scaffolding:

- `node`
- `npm`
- `supabase` CLI
- `wrangler`

The current .NET and Docker toolchain remains required for the legacy stack and parity baseline runs.

## Workspace Layout

- `apps/spa`: React + TypeScript Cloudflare Pages shell
- `apps/workers-api`: Cloudflare Workers API shell
- `packages/migration-contract`: shared maintained route and contract metadata
- `supabase/`: local Supabase configuration and Wave 1 placeholder seed
- `cloudflare/`: Pages and Workers config templates
- `config/migration.*.env.example`: local and staging environment layouts
- `docs/parity/wave-1/`: frozen UX parity reference artifacts

## Root CLI Commands

Migration-specific commands added in Wave 1:

```bash
python ./scripts/dev.py spa install
python ./scripts/dev.py spa build
python ./scripts/dev.py spa run
python ./scripts/dev.py workers install
python ./scripts/dev.py workers build
python ./scripts/dev.py workers run
python ./scripts/dev.py supabase start
python ./scripts/dev.py supabase status
python ./scripts/dev.py supabase db-reset
python ./scripts/dev.py contract-smoke --start-backend
python ./scripts/dev.py parity-test --start-stack
python ./scripts/dev.py capture-parity-baseline --start-stack
python ./scripts/dev.py deploy-staging --dry-run
```

## Verification Baseline

Wave 1 adds three baseline layers:

- route and copy parity artifacts under [`docs/parity/wave-1`](./parity/wave-1/README.md)
- Playwright smoke and screenshot comparison coverage under [`tests/parity`](../tests/parity)
- maintained API contract smoke coverage under [`tests/contract-smoke`](../tests/contract-smoke)

## Provider Templates

Wave 1 does not commit live provider secrets or live deployment config.

Committed templates:

- [`cloudflare/pages/wrangler.template.jsonc`](../cloudflare/pages/wrangler.template.jsonc)
- [`cloudflare/workers/wrangler.template.jsonc`](../cloudflare/workers/wrangler.template.jsonc)
- [`config/migration.local.env.example`](../config/migration.local.env.example)
- [`config/migration.staging.env.example`](../config/migration.staging.env.example)
- [`supabase/config.toml`](../supabase/config.toml)

Copy the example env files into ignored local files before real provider wiring.
