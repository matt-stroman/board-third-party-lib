# Cloudflare, Supabase, and Workers Wave 2 Platform/API Cutover

Wave 2 moves the maintained backend surface for the migration branch onto Supabase Auth, Supabase Postgres, Supabase Storage, and Cloudflare Workers.

## Scope

Wave 2 adds:

- Supabase-backed application tables, RLS-enabled schema, and deterministic seed/reset flow
- Supabase Auth seeded identities for local developer, moderator, and player verification
- Supabase Storage-backed media upload and retrieval for studios and catalog content
- Cloudflare Workers implementations for the maintained demo API surface
- role-aware contract smoke coverage for public, player, developer, and moderation routes
- end-to-end Workers smoke coverage for auth, catalog, studio CRUD, moderation, and media flows

Wave 2 does not remove the legacy .NET and Keycloak stack yet. That cleanup remains part of Wave 3 cutover.

## Local Commands

Primary local migration flows:

```bash
python ./scripts/dev.py supabase start
python ./scripts/dev.py supabase db-reset
python ./scripts/dev.py workers run
python ./scripts/dev.py seed-data --target migration
python ./scripts/dev.py contract-smoke --target migration --start-workers
python ./scripts/dev.py workers-smoke --start-stack
python ./scripts/dev.py deploy-staging --dry-run
```

Helpful notes:

- `supabase db-reset` now reseeds deterministic auth, relational, and storage fixtures automatically.
- `workers run` writes local Wrangler bindings from the active local Supabase runtime before starting.
- the root CLI now avoids repeated destructive npm workspace reinstalls when dependencies are already current.

## Seeded Local Identities

Wave 2 local verification uses deterministic Supabase Auth accounts:

- moderator: `alex.rivera@boardtpl.local`
- developer: `emma.torres@boardtpl.local`
- additional developer: `olivia.bennett@boardtpl.local`
- player: `ava.garcia@boardtpl.local`

Default local password:

```text
ChangeMe!123
```

## Verification

Wave 2 verification that passed locally on March 8, 2026:

```bash
python -m unittest discover -s tests/root_cli -p "test_*.py"
npm run typecheck:migration
npm run build:migration
python ./scripts/dev.py contract-smoke --target migration --start-workers
python ./scripts/dev.py workers-smoke --start-stack
python ./scripts/dev.py deploy-staging --dry-run
```

The maintained contract smoke suite now uses seeded role-appropriate principals automatically for local migration runs:

- developer token for player/developer routes
- moderator token for moderation routes

## Staging Status

Wave 2 includes the staging deployment wrappers and configuration templates needed for Cloudflare Pages, Cloudflare Workers, and Supabase.

Validated in this branch:

- local Workers/Supabase runtime
- staging bundle dry-run build path

Not validated in this branch because live provider credentials are not committed:

- live remote Cloudflare deployment
- live remote Supabase project provisioning
- live remote social-provider login callback wiring
