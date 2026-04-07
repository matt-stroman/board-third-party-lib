# Production Release Runbook

This runbook is the step-by-step guide for preparing and deploying the live Board Enthusiasts experience to `production`.

Use it together with:

- [docs/developer-cli.md](./developer-cli.md)
- [docs/data-operations.md](./data-operations.md)
- [docs/analytics.md](./analytics.md)
- [docs/support-playbook.md](./support-playbook.md)
- [docs/staging-release-runbook.md](./staging-release-runbook.md)

## Table of Contents

- [Release Goal](#release-goal)
- [Production Data Policy](#production-data-policy)
- [Pre-Deployment Checks](#pre-deployment-checks)
- [Production Environment Preparation](#production-environment-preparation)
- [Fallback Pages Preparation](#fallback-pages-preparation)
- [Cloudflare Branded Error Pages](#cloudflare-branded-error-pages)
- [Manual Maintenance Fallback](#manual-maintenance-fallback)
- [Deploy Steps](#deploy-steps)
- [Post-Deploy Validation](#post-deploy-validation)
- [First-Run Admin Bootstrap](#first-run-admin-bootstrap)
- [If Staging Data Must Be Promoted](#if-staging-data-must-be-promoted)

## Release Goal

The production target is the live BE site with:

- `VITE_LANDING_MODE=false`
- the public browse, studio, title, offerings, install, and support surfaces
- player, developer, and moderator workflows enabled
- analytics enabled
- no demo content seeded into production

## Production Data Policy

Production is intentionally different from staging:

- `staging` stays seeded with the maintained mock/demo catalog and smoke users
- `production` must not be seeded with demo users, demo studios, demo titles, demo media, or demo reports
- the only initial bootstrap account should be the operator super admin

The recommended initial operator bootstrap is:

- the real operator-owned email address
- a strong operator-owned password entered only at the secure prompt during bootstrap

The maintained bootstrap flow no longer accepts the password on the command line or in committed docs/examples.
Public access to this repository does not grant hosted-environment access by itself; privileged operator workflows still require the production provider credentials and secret material that live outside git. Even so, the public runbooks intentionally omit copy-pasteable privileged bootstrap invocations.

## Pre-Deployment Checks

Run these locally from the root repository:

```bash
python ./scripts/dev.py all-tests --start-workers
python ./scripts/dev.py api-test --start-workers --skip-lint
python ./scripts/dev.py parity-test
```

Also confirm:

1. The root CLI/unit test suite is green.
2. The frontend test suite is green.
3. The backend test suite is green.
4. The contract smoke and workers smoke suites are green.
5. The working tree contains only intentional release changes.

## Production Environment Preparation

Open the production environment file:

```bash
python ./scripts/dev.py env production --open
```

Confirm `config/.env` contains the real hosted values for:

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
- `VITE_LANDING_MODE=false`

Important note:

- `DEPLOY_SMOKE_PLAYER_EMAIL`
- `DEPLOY_SMOKE_DEVELOPER_EMAIL`
- `DEPLOY_SMOKE_MODERATOR_EMAIL`
- `DEPLOY_SMOKE_USER_PASSWORD`

are optional in production unless you intentionally provision dedicated production smoke accounts. If those are omitted, the maintained deploy flow falls back to public-route smoke.

### GitHub Environment Sync

Publish the current production env file into the matching GitHub Environment:

```bash
python ./scripts/dev.py env production --sync-github-environment
```

## Fallback Pages Preparation

The repository now includes a standalone fallback site under [`cloudflare/fallback-pages`](../cloudflare/fallback-pages/README.md).

Use that site for two separate protections:

- a manual maintenance / placeholder page
- branded Cloudflare custom error pages for `500` and `1000` class failures

Preview the fallback site from your current branch:

```bash
python ./scripts/dev.py deploy-fallback-pages --project-name board-enthusiasts-fallback
```

After you review the preview alias and merge to `main`, publish the production fallback site:

```bash
python ./scripts/dev.py deploy-fallback-pages --project-name board-enthusiasts-fallback --source-branch main
```

The maintained production URLs are then:

- `https://board-enthusiasts-fallback.pages.dev/`
- `https://board-enthusiasts-fallback.pages.dev/cloudflare/5xx.html`
- `https://board-enthusiasts-fallback.pages.dev/cloudflare/1xxx.html`

Optional but recommended:

- attach a dedicated custom domain such as `status.boardenthusiasts.com` to the fallback Pages project after the first publish
- if you do that, substitute the custom-domain URLs below in place of `board-enthusiasts-fallback.pages.dev`

## Cloudflare Branded Error Pages

In the Cloudflare dashboard for the production zone:

1. Open `Error Pages`.
2. Set `500 class errors` to the deployed BE fallback page:
   `https://board-enthusiasts-fallback.pages.dev/cloudflare/5xx.html`
3. Set `1000 class errors` to the deployed BE fallback page:
   `https://board-enthusiasts-fallback.pages.dev/cloudflare/1xxx.html`
4. Confirm the pages render correctly in Cloudflare's preview.

Important:

- these pages are fetched and cached by Cloudflare
- whenever you update either error-page HTML, use Cloudflare's `Fetch custom page again` action so the new version is picked up

## Manual Maintenance Fallback

For a release that needs extra repair time, keep a disabled temporary redirect rule ready in Cloudflare.

Recommended setup:

1. In the production zone, open `Rules` and create a redirect rule that targets the BE hostnames you want to pause.
2. Use a temporary redirect so the fallback can be enabled and disabled cleanly during an incident.
3. Point the redirect destination at:
   `https://board-enthusiasts-fallback.pages.dev/`
4. Leave the rule disabled during normal operation.
5. If a production release goes sideways, enable the rule to move visitors onto the branded fallback page immediately.
6. Disable the rule again once production traffic is healthy.

Notes:

- the maintained fallback pages include the same footer and independence disclaimer language as the live site
- the fallback site is static and Cloudflare-hosted, so it does not depend on the BE SPA, Workers API, or Supabase runtime to render
- this redirect-based maintenance mode changes the visitor URL to the fallback hostname; if we later want same-URL maintenance handling, we can add a small Cloudflare Worker or Snippet in front of the zone

## Deploy Steps

### 1. Preflight

```bash
python ./scripts/dev.py deploy --preflight-only
```

### 2. Dry Run

```bash
python ./scripts/dev.py deploy --dry-run-only
```

### 3. Real Production Deploy

```bash
python ./scripts/dev.py deploy
```

This should:

- push the hosted Supabase auth/provider configuration for production
- provision or validate hosted Supabase schema state
- provision or validate typed storage buckets
- skip demo seeding for production
- deploy the Workers API
- deploy the Pages frontend
- run the configured hosted smoke checks

## Post-Deploy Validation

After the deployment succeeds, manually validate the live production site.

### Public Flows

Check:

- `/`
- `/offerings`
- `/browse`
- `/studios`
- `/install`
- `/support`

Verify:

- the site shell renders correctly
- copy is current and user-friendly
- public browse/search behave correctly
- no demo content is present unless it was intentionally promoted

### Account Flows

After the operator account is bootstrapped, verify:

- sign-in works
- `/player` loads
- `/developer` loads
- moderation access is present

## First-Run Admin Bootstrap

Run the maintained privileged operator bootstrap workflow once against production after the first successful deploy, from a trusted checkout that already has the production environment loaded securely.

This command is idempotent. It creates or repairs:

- the Supabase Auth user
- the BE `app_users` projection
- the full elevated role set needed for end-to-end access

Operational guidance:

- use the real operator-owned email address
- enter the password only through the secure runtime prompt
- do not paste privileged bootstrap commands into shared tickets, docs, chat, or screenshots
- do not run the workflow from CI, shared shells, or untrusted machines

## If Staging Data Must Be Promoted

If preview users created real data in staging that should become production baseline data, do not improvise the import.

Use [docs/data-operations.md](./data-operations.md), especially:

- [Staging To Production Promotion Options](./data-operations.md#staging-to-production-promotion-options)
- [Selective Promotion Checklist](./data-operations.md#selective-promotion-checklist)

Recommended order of preference:

1. Fresh production with no promotion
2. Whole-environment baseline promotion before launch
3. Selective promotion only with a reviewed inventory and import plan
