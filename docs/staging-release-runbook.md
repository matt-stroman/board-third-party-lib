# Staging Release Runbook

This runbook is the step-by-step guide for preparing and deploying the full BE library/index experience to `staging`.

Use it together with:

- [docs/maintained-stack.md](./maintained-stack.md)
- [docs/data-operations.md](./data-operations.md)
- [docs/analytics.md](./analytics.md)
- [planning/mvp-release-audit.md](../planning/mvp-release-audit.md)

## Table of Contents

- [Release Goal](#release-goal)
- [Pre-Deployment Checks](#pre-deployment-checks)
- [Staging Environment Preparation](#staging-environment-preparation)
- [Deployment Steps](#deployment-steps)
- [Post-Deploy Validation](#post-deploy-validation)
- [Rollback Mindset](#rollback-mindset)

## Release Goal

The current staging target is the full library/index experience with:

- `VITE_LANDING_MODE=false`
- public browse, studio, title, offerings, install, and support pages
- email/password auth plus Google, GitHub, and Discord OAuth
- player, developer, and moderator workflows
- backend-mediated media uploads
- launch-phase analytics enabled

## Pre-Deployment Checks

Run these locally from the root repository:

```bash
python ./scripts/dev.py bootstrap
python ./scripts/dev.py all-tests --start-workers
python ./scripts/dev.py api-test --start-workers --skip-lint
python ./scripts/dev.py parity-test
```

Also confirm:

1. The latest root validation is green.
2. The latest frontend validation is green.
3. The latest backend validation is green after the current workflow fix lands.
4. The local working tree is clean or contains only intentional release changes.

## Staging Environment Preparation

Open the staging environment file:

```bash
python ./scripts/dev.py env staging --open
```

Confirm `config/.env.staging` contains the real hosted values for:

- `BOARD_ENTHUSIASTS_SPA_BASE_URL`
- `BOARD_ENTHUSIASTS_WORKERS_BASE_URL`
- `SUPABASE_URL`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_PASSWORD`
- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_AVATARS_BUCKET`
- `SUPABASE_CARD_IMAGES_BUCKET`
- `SUPABASE_HERO_IMAGES_BUCKET`
- `SUPABASE_LOGO_IMAGES_BUCKET`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `VITE_TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`
- `BREVO_API_KEY`
- `BREVO_SIGNUPS_LIST_ID`
- `ALLOWED_WEB_ORIGINS`
- `SUPPORT_REPORT_RECIPIENT`
- `SUPPORT_REPORT_SENDER_EMAIL`
- `SUPPORT_REPORT_SENDER_NAME`
- `DEPLOY_SMOKE_SECRET`
- `DEPLOY_SMOKE_USER_PASSWORD`
- `DEPLOY_SMOKE_PLAYER_EMAIL`
- `DEPLOY_SMOKE_DEVELOPER_EMAIL`
- `DEPLOY_SMOKE_MODERATOR_EMAIL`
- `VITE_LANDING_MODE=false`

### Staging Demo Seed and Smoke Accounts

The maintained staging deploy now seeds the hosted demo catalog additively as part of the deploy flow:

- `staging` is seeded with the checked-in demo studios, titles, media, reports, and helper users
- `production` is not seeded
- rerunning the staging deploy adds any missing maintained fixtures without clearing existing staging data

Keep the staging smoke users pointed at the seeded staging accounts:

- `DEPLOY_SMOKE_PLAYER_EMAIL=testing+staging-player@boardenthusiasts.com`
- `DEPLOY_SMOKE_DEVELOPER_EMAIL=testing+staging-developer@boardenthusiasts.com`
- `DEPLOY_SMOKE_MODERATOR_EMAIL=testing+staging-moderator@boardenthusiasts.com`

Set `DEPLOY_SMOKE_USER_PASSWORD` to the shared password you want the deploy to assign to those seeded staging auth users.

### OAuth Preparation

Confirm the staging Supabase project has:

- Google provider enabled
- GitHub provider enabled
- Discord provider enabled

And confirm the upstream provider apps all include the Supabase callback URL for the staging project.

### GitHub Environment Sync

Publish the current staging env file into the matching GitHub Environment:

```bash
python ./scripts/dev.py env staging --sync-github-environment
```

This keeps:

- runtime-safe values in GitHub Environment vars
- sensitive values in GitHub Environment secrets

## Deployment Steps

### 1. Preflight

```bash
python ./scripts/dev.py deploy --staging --preflight-only
```

This should pass before you continue.

Cloudflare note:

- The `CLOUDFLARE_API_TOKEN` used for deploys must be scoped to the same Cloudflare account as `CLOUDFLARE_ACCOUNT_ID`.
- The token should include at least:
  - `Account | Cloudflare Pages | Edit`
  - `Account | Workers Scripts | Edit`
  - `Zone | DNS | Edit`
  - `Zone | Zone | Read`
- `--preflight-only` now checks Cloudflare Pages access directly against the Cloudflare API so account/token mismatches fail before a real publish starts.

### 2. Dry Run

```bash
python ./scripts/dev.py deploy --staging --dry-run-only
```

Use this to confirm:

- Pages config renders correctly
- Workers config renders correctly
- required env values are present
- Cloudflare account/token access is valid for Pages and Workers
- deploy smoke prerequisites are satisfied

### 3. Real Staging Deploy

```bash
python ./scripts/dev.py deploy --staging
```

This should:

- push the hosted Supabase auth/provider configuration for staging
- provision or validate hosted Supabase schema state
- provision or validate typed storage buckets
- seed the hosted staging demo catalog additively when deploying `staging`
- deploy the Workers API
- deploy the Pages frontend
- run the configured hosted smoke checks

## Post-Deploy Validation

After the deployment succeeds, manually validate the hosted staging site.

### Public Flows

Check:

- `/`
- `/offerings`
- `/browse`
- public studio detail
- public title detail
- `/install`
- `/support`

Verify:

- header and footer links look correct
- copy is current and user-friendly
- search and filters behave correctly
- quick view and title detail pages load
- `Get Title` links open the expected external destination

### Auth Flows

Check:

- email/password sign-up
- email confirmation
- email/password sign-in
- password recovery
- Google sign-in
- GitHub sign-in
- Discord sign-in
- sign-out

Verify:

- the right buttons show on sign-in and registration
- OAuth providers return to the expected route
- connected-account setup looks correct in account settings

### Player Flows

Check:

- profile read and update
- account settings and password flow
- connected accounts
- library
- wishlist
- title reporting

### Developer Flows

Check:

- self-enrollment
- studio create/update/delete
- studio links
- studio media uploads
- title create/update/delete
- metadata versioning
- title media
- releases and activation

### Moderator Flows

Check:

- developer verification
- report review
- moderation messaging
- validate/invalidate decisions

### Analytics Validation

After using staging manually, query the staging analytics dataset and confirm at least a few known events landed:

- `page_view`
- `oauth_started`
- `oauth_completed`
- `account_created`
- `browse_filters_applied`
- `title_quick_view_opened`
- `title_detail_viewed`
- `title_get_clicked`

See [docs/analytics.md](./analytics.md) for query examples.

## Rollback Mindset

If the staging deploy reveals a serious issue:

1. stop using staging as the sign-off candidate
2. capture the error details, affected route, and any failing payloads
3. open or update the tracking issue
4. fix forward with a new deploy instead of patching the hosted environment manually where possible

If the issue is data-related, follow [docs/data-operations.md](./data-operations.md).

## Current Final Gate Recommendation

Do not treat staging as ready until all of the following are true:

- root validation is green
- frontend validation is green
- backend validation is green
- local full-suite validation passes
- hosted staging smoke passes
- manual hosted browser QA passes across public, auth, player, developer, and moderator flows
