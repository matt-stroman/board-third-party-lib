# Production Landing Page DevOps Plan

## Table of Contents

- [Purpose](#purpose)
- [Project Context](#project-context)
- [DevOps Objective](#devops-objective)
- [Scope For This Wave](#scope-for-this-wave)
- [Platform Inventory](#platform-inventory)
- [Environment Model](#environment-model)
- [Ownership Boundaries](#ownership-boundaries)
- [Secrets And Configuration Inventory](#secrets-and-configuration-inventory)
- [Deployment Strategy](#deployment-strategy)
- [CI CD Plan](#ci-cd-plan)
- [Observability And Monitoring](#observability-and-monitoring)
- [Rollback And Recovery Plan](#rollback-and-recovery-plan)
- [Release Checklist](#release-checklist)
- [Post-Launch Operations](#post-launch-operations)
- [Reference Links](#reference-links)

## Purpose

This document defines the async DevOps role for the Board Enthusiasts landing-page production wave.

It is intended to give a delivery or infrastructure owner enough context to manage environments, deployment automation, secrets, release safety, and operational readiness without needing to reconstruct the project architecture from scratch.

## Project Context

Board Enthusiasts (BE) is building an independent platform for the Board ecosystem.

Current maintained stack:

- frontend SPA in `frontend/`
- Cloudflare Workers API in `backend/apps/workers-api/`
- Supabase Auth, Postgres, and Storage in `backend/supabase/`
- root orchestration through `python ./scripts/dev.py ...`

For this wave, production should expose a landing-page-only site on `boardenthusiasts.com` with email signup, while preserving the existing repo and deployment direction for the full product.

## DevOps Objective

The DevOps role should make the landing-page wave:

- reproducible
- low-touch to deploy
- safe to roll back
- explicit about secrets and provider boundaries
- easy to extend when the full MVP is exposed later

The DevOps role should reduce manual setup to the smallest viable set of provider bootstrap steps, then move repeatable tasks into checked-in automation.

## Scope For This Wave

The DevOps owner is responsible for:

- production and staging environment definition
- deployment automation for Pages and Workers
- secret inventory and environment mapping
- safe rollout sequencing
- basic smoke verification
- monitoring and rollback readiness
- keeping provider drift visible

The DevOps owner is not responsible for:

- product copy decisions
- final legal wording
- marketing campaign content
- application feature design beyond operational feasibility concerns

## Platform Inventory

Primary providers for this wave:

- Cloudflare
  - DNS
  - Pages
  - Workers
  - Turnstile
  - Email Routing
- Supabase
  - hosted Auth
  - hosted Postgres
  - hosted Storage
- Brevo
  - subscriber/contact sync target
  - campaign delivery
  - SMTP relay for Gmail aliases
- GitHub
  - source control
  - CI
  - deployment secret storage

Repository-owned automation already exists in these areas:

- root CLI orchestration via [`scripts/dev.py`](../scripts/dev.py)
- Cloudflare deployment templates in [`cloudflare/pages/wrangler.template.jsonc`](../cloudflare/pages/wrangler.template.jsonc) and [`backend/cloudflare/workers/wrangler.template.jsonc`](../backend/cloudflare/workers/wrangler.template.jsonc)
- root validation workflow in [`.github/workflows/root-validation.yml`](../.github/workflows/root-validation.yml)

## Environment Model

Recommended environment set:

- `local`
- `staging`
- `production`

### Local

Purpose:

- day-to-day development
- seeded demo data
- no production secrets

### Staging

Purpose:

- hosted pre-release validation
- smoke tests against real providers
- eventual invite-only tester access

Domains already aligned in planning:

- `staging.boardenthusiasts.com`
- `api.staging.boardenthusiasts.com`

### Production

Purpose:

- public landing-page-only release

Recommended domains:

- `boardenthusiasts.com`
- `www.boardenthusiasts.com`
- `api.boardenthusiasts.com`

Recommendation:

- keep the same environment split after the full MVP opens
- do not create a separate one-off landing-page hosting arrangement

## Ownership Boundaries

### Manual Bootstrap

These remain human-owned:

- provider account creation
- DNS zone onboarding
- Supabase hosted project creation
- Brevo domain authentication
- Gmail alias verification

### Repository-Owned And Automated

These should move into source-controlled automation:

- Pages project config
- Workers config
- Supabase schema and policies
- email templates
- API contract and tests
- landing-page build and deployment
- smoke verification commands
- Brevo provisioning scripts where API support exists

### Practical Rule

If a task is repeatable and does not require a human verification loop, it should be automated.

## Secrets And Configuration Inventory

Recommended hosted environment variables and secrets:

### Frontend Hosted Variables

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`
- `VITE_TURNSTILE_SITE_KEY`
- `VITE_LANDING_MODE`

### Workers Hosted Variables

- `APP_ENV`
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_AVATARS_BUCKET`
- `SUPABASE_CARD_IMAGES_BUCKET`
- `SUPABASE_HERO_IMAGES_BUCKET`
- `SUPABASE_LOGO_IMAGES_BUCKET`
- `BREVO_API_KEY` or equivalent secret form
- `TURNSTILE_SECRET_KEY`
- any landing-page marketing integration config

### Workers Secret Material

- `SUPABASE_SECRET_KEY`
- `BREVO_API_KEY`
- `TURNSTILE_SECRET_KEY`
- SMTP credentials only if a server-side mail path is added

### Repository / CI Secrets

- Cloudflare API token
- Supabase project reference
- Supabase hosted keys required by deployment
- any provider tokens required by deploy or smoke tooling

Guidance:

- do not duplicate secret storage casually across local `.env`, CI, and provider dashboards
- keep a single documented source for each secret owner and rotation path

## Deployment Strategy

### Guiding Principle

Use the current stack and CLI direction already in the repo. Do not create a parallel deployment workflow for the landing page.

### Recommended Production Topology

- Cloudflare Pages serves the SPA at `boardenthusiasts.com`
- Cloudflare Workers serves the API at `api.boardenthusiasts.com`
- Supabase backs auth/database/storage
- Brevo remains an external integration, not the system of record

### Recommended Release Sequence

1. Deploy backend contract and schema changes first.
2. Verify the hosted API and signup behavior.
3. Deploy the frontend landing-page-only build.
4. Run hosted smoke checks.
5. Announce the site only after email forwarding and signup flow are verified.

### Configuration Principle

- production should use the landing-only flag
- staging should be able to test both landing behavior and future app behavior as needed

## CI CD Plan

Current repo state already has:

- root tooling validation
- contract smoke
- staging deployment dry-run

Recommended next CI/CD additions for this wave:

1. `deploy-staging` on merges to the primary staging branch.
2. `deploy-production` as an explicitly gated workflow.
3. post-deploy smoke checks for:
   - landing page reachable
   - signup endpoint healthy
   - Turnstile path configured
   - API health endpoint healthy
4. optional PR preview deployments if they can be introduced without fragmenting the deployment story.

Recommended deployment guardrails:

- production deploy requires green validation jobs
- production deploy requires environment-scoped secrets
- production deploy should be manually approved until the flow proves stable

## Observability And Monitoring

Minimum operational visibility for this wave:

- Cloudflare request visibility for Pages and Workers
- Workers error monitoring
- Supabase service health awareness
- a smoke-verification checklist after deploy

Recommended metrics and checks:

- landing page availability
- API health endpoint response
- signup endpoint success/error rate
- Turnstile verification failures
- Brevo sync failures
- sudden spikes in duplicate or invalid signups

Recommended first-wave notification approach:

- keep it simple
- use provider dashboards plus a lightweight manual daily check until traffic justifies alerting automation

## Rollback And Recovery Plan

### Frontend Rollback

- redeploy the previous stable Pages artifact or previous stable frontend commit

### Backend Rollback

- redeploy the previous Worker version if the API layer regresses
- avoid destructive schema rollbacks unless absolutely required

### Schema Strategy

- migrations must be additive where possible
- avoid migrations that make rollback operationally expensive in this wave
- keep new landing-page tables isolated from existing catalog/demo flows

### Incident Priorities

1. Stop broken public signup flows quickly.
2. Preserve already-captured data.
3. Restore the landing page even if signup is temporarily disabled.
4. Communicate clearly in the site copy or maintenance state if needed.

## Release Checklist

Before first public release:

- production Cloudflare zone active
- Pages custom domain working
- Workers custom domain working
- Supabase production project reachable
- landing page build deployed
- signup endpoint deployed
- Turnstile configured
- Brevo integration credentials present
- BE aliases forwarding to Gmail
- Gmail send-as aliases working
- smoke test of a real signup completed
- rollback path documented

## Post-Launch Operations

After launch, the DevOps owner should maintain:

- environment variable inventory
- provider-access inventory
- rotation notes for sensitive credentials
- a lightweight release log
- smoke-check results after each deployment

Recommended follow-up work after the landing page is stable:

- production deployment workflow in CI
- explicit secret-template documentation
- optional provider provisioning scripts for Brevo lists/senders/templates
- optional targeted IaC layer if Cloudflare or DNS drift becomes painful

## Reference Links

- Cloudflare Pages: [https://pages.cloudflare.com/](https://pages.cloudflare.com/)
- Cloudflare Workers pricing: [https://developers.cloudflare.com/workers/platform/pricing/](https://developers.cloudflare.com/workers/platform/pricing/)
- Cloudflare Email Routing docs: [https://developers.cloudflare.com/email-routing/](https://developers.cloudflare.com/email-routing/)
- Cloudflare Turnstile plans: [https://developers.cloudflare.com/turnstile/plans/](https://developers.cloudflare.com/turnstile/plans/)
- Supabase billing overview: [https://supabase.com/docs/guides/platform/billing-on-supabase](https://supabase.com/docs/guides/platform/billing-on-supabase)
- Brevo SMTP setup: [https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP)
- Root validation workflow: [`.github/workflows/root-validation.yml`](../.github/workflows/root-validation.yml)
- Root developer CLI: [`docs/developer-cli.md`](../docs/developer-cli.md)
