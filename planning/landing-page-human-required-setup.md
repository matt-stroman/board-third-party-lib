# Landing Page Human-Required Setup

## Table of Contents

- [Purpose](#purpose)
- [Project Context](#project-context)
- [Target Outcome](#target-outcome)
- [Staging-First Rollout](#staging-first-rollout)
- [What Must Stay Manual](#what-must-stay-manual)
- [What Should Be Automated In The Repository](#what-should-be-automated-in-the-repository)
- [Accounts And Access Checklist](#accounts-and-access-checklist)
- [Ordered Manual Setup Steps](#ordered-manual-setup-steps)
- [Post-Setup Validation Checklist](#post-setup-validation-checklist)
- [Known Risks And Recovery Notes](#known-risks-and-recovery-notes)
- [Brevo Attribute Reference](#brevo-attribute-reference)
- [Reference Links](#reference-links)

## Purpose

This document is written for a human operator who needs to stand up the minimum provider accounts and hosted configuration required to launch the first public Board Enthusiasts landing page, validating everything in staging before promoting the same setup to production.

It is intentionally written so it can be handed to another AI agent or human without direct access to this repository.

## Project Context

Board Enthusiasts (BE) is building a public platform for third-party Board developers and players.

Current maintained runtime direction:

- frontend: React + TypeScript SPA
- API: Cloudflare Workers
- auth, relational data, and media: Supabase
- DNS, TLS, static hosting, and email forwarding: Cloudflare

For this wave, production should expose only:

- a public landing page on `boardenthusiasts.com`
- a signup form for release updates and future account invites
- links to the BE Discord and the public BE custom GPT
- email forwarding for `contact@boardenthusiasts.com` and `support@boardenthusiasts.com`
- the ability to send 1:1 email from those BE addresses inside Gmail

Important constraint:

- keep recurring cost at `$0` if possible

## Target Outcome

After this setup is complete, the operator should have:

1. A Cloudflare-managed `boardenthusiasts.com` zone.
2. A hosted Supabase project for staging and a hosted Supabase project for production.
3. A Brevo account authenticated for the BE domain.
4. A Gmail inbox (`matt@mattstroman.com`) receiving forwarded BE email.
5. Gmail configured to send as BE email aliases using Brevo SMTP.
6. A staging environment file (`config/.env.staging`) populated for `python ./scripts/dev.py deploy --staging`.
7. Enough provider credentials and identifiers stored securely to let the repository own repeatable staging and production deploys with minimal manual drift.

## Staging-First Rollout

The maintained deployment path is now:

1. populate `config/.env.staging`
2. run `python ./scripts/dev.py deploy --staging --dry-run-only`
3. run a real staging deploy with `python ./scripts/dev.py deploy --staging`
4. validate the remote staging stack end to end
5. only after staging is healthy, populate `config/.env` for production and promote the same configuration pattern there

Important implementation detail:

- the root CLI is the operator entrypoint
- `config/.env.staging` is the canonical input source for staging deploy values
- `deploy` defaults to production and `--staging` selects the staging target
- the CLI runs preflight and dry-run checks before any real deploy stages
- the CLI applies hosted Supabase migrations and bucket provisioning as part of the deploy stages
- the CLI builds the SPA locally with the public target runtime values
- the CLI syncs Worker secrets from `config/.env.staging` into Cloudflare before a real Workers deploy
- the CLI runs a post-deploy smoke test after hosted publish completes
- bucket names currently remain environment-file values, even though provisioning is repo-owned

## What Must Stay Manual

These steps are expected to require human action in provider UIs:

- creating the Cloudflare account or joining the correct Cloudflare account
- onboarding the `boardenthusiasts.com` DNS zone to Cloudflare
- creating the Supabase organization/project
- creating the Brevo account
- completing any provider verification, CAPTCHA, phone, or email verification steps
- configuring Gmail alias verification and entering SMTP credentials in Gmail
- confirming any domain-verification DNS records when the provider does not expose those actions through existing repo automation

These actions are usually manual because they require ownership proof, login challenges, billing acceptance screens, or provider-issued secrets that should not be generated blindly.

## What Should Be Automated In The Repository

The repository should own as much non-human setup as possible after the initial provider bootstrap:

- Cloudflare Pages and Workers deployment configuration
- Workers environment variables that are safe to keep as checked-in templates
- Supabase schema, policies, email templates, and seed behavior
- API contract, tests, and deployment orchestration
- landing page source, email signup behavior, and bot protection integration
- post-bootstrap provisioning scripts for Brevo contacts/lists/templates where API support exists

Pragmatic guidance:

- prefer provider-native checked-in config and CLI automation already aligned with the repo
- avoid adding a large new IaC stack just to automate a handful of first-wave resources unless the payoff is immediate
- keep the manual bootstrap small, then script everything repeatable after that

## Accounts And Access Checklist

The operator should gather or confirm access to:

- domain registrar access for `boardenthusiasts.com`
- the target Cloudflare account
- the target Supabase account or organization
- the target Brevo account
- the Gmail account `matt@mattstroman.com`
- GitHub repository admin or secret-management access for this repository

Recommended destination aliases to create now:

- `contact@boardenthusiasts.com`
- `support@boardenthusiasts.com`
- `updates@boardenthusiasts.com`

`updates@` is recommended even if it is not used immediately. It keeps marketing traffic separate from support mail.

## Ordered Manual Setup Steps

### 1. Confirm Domain Registrar Access

Goal:

- make sure the operator can change nameservers and DNS records for `boardenthusiasts.com`

Steps:

1. Sign in to the registrar that owns `boardenthusiasts.com`.
2. Open the domain-management page for `boardenthusiasts.com`.
3. Confirm there is no domain-transfer lock or account issue preventing DNS changes.
4. Leave the registrar tab open. You will need it when Cloudflare gives you nameservers.

Success check:

- you can view the current nameservers and edit DNS settings for the domain

### 2. Create Or Access The Cloudflare Account

Goal:

- manage DNS, static hosting, Workers, Turnstile, and Email Routing from one place

Steps:

1. Sign in at [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. If the correct Cloudflare account already exists, switch into it.
3. If not, create the account using an email that the BE team will control long-term.
4. Enable two-factor authentication on the account before continuing.

Success check:

- you can access the Cloudflare dashboard and create/select zones

### 3. Add `boardenthusiasts.com` To Cloudflare

Goal:

- move authoritative DNS for the domain into Cloudflare

Steps:

1. In Cloudflare, select `Add a domain`.
2. Enter `boardenthusiasts.com`.
3. Select the free plan unless Cloudflare presents a newer equivalent free option.
4. Let Cloudflare scan existing DNS records.
5. Review imported DNS records carefully.
6. Keep any existing records you still need.
7. Continue until Cloudflare shows the two nameservers it wants you to use.
8. Return to the domain registrar.
9. Replace the existing nameservers with the two Cloudflare nameservers exactly as shown.
10. Save the change.
11. Return to Cloudflare and wait for the zone to become active.

Success check:

- the Cloudflare zone status becomes active

Notes:

- DNS propagation can take time.
- do not continue with Email Routing or custom domains until the zone is active.

### 4. Create The Production Supabase Project

Goal:

- create the production auth/database/storage backend for BE

Steps:

1. Sign in at [Supabase Dashboard](https://supabase.com/dashboard).
2. Create or select the correct organization.
3. Select `New project`.
4. Choose a clear production name such as `board-enthusiasts-prod`.
5. Choose the region closest to the primary user base.
6. Set a strong database password and store it in your team password manager.
7. Wait for the project to finish provisioning.
8. Open `Project Settings`.
9. Record the following values:
   - project reference
   - project URL
   - publishable key
   - secret key
10. Open the auth configuration area and confirm that email/password auth is enabled.
11. Do not start changing email templates manually if the repo is expected to own them later.

Success check:

- you have the project URL, publishable key, and secret key recorded securely

### 5. Create The Brevo Account

Goal:

- provide subscriber-list management, outbound campaigns, and SMTP for Gmail alias sending

Steps:

1. Sign in at [Brevo](https://app.brevo.com/).
2. Create the account if needed.
3. Complete any account verification steps.
4. Enable two-factor authentication if available.
5. Open the sender or domain-authentication area.
6. Add `boardenthusiasts.com` as a sending domain.
7. Let Brevo show you the DNS records it requires.
8. Do not close this page until the DNS records are copied into Cloudflare.

Success check:

- Brevo is ready to verify the BE domain

### 6. Add Brevo DNS Records In Cloudflare

Goal:

- allow Brevo to send authenticated mail for the BE domain

Steps:

1. In Cloudflare, open the DNS records page for `boardenthusiasts.com`.
2. Add every Brevo-required DNS record exactly as shown.
3. Pay close attention to record type, name, value, and whether the record should be proxied.
4. TXT, MX, DKIM, and SPF-style records should usually be `DNS only`, not proxied.
5. Save each record.
6. Return to Brevo and start or retry verification.

Success check:

- Brevo reports the domain as authenticated or verified

Critical note:

- never create multiple SPF TXT records for the root domain
- if an SPF record already exists, merge the necessary includes into one SPF record rather than adding a second SPF record

### 7. Configure Cloudflare Email Routing

Goal:

- forward inbound email from BE aliases into `matt@mattstroman.com`

Steps:

1. In Cloudflare, open the `Email` or `Email Routing` section for the `boardenthusiasts.com` zone.
2. Enable Email Routing for the domain.
3. Cloudflare may ask to add or confirm required MX/TXT records.
4. If so, add or confirm those DNS records in Cloudflare DNS.
5. Create a destination address pointing to `matt@mattstroman.com`.
6. Watch for the verification email in Gmail.
7. Open the verification email and confirm the destination.
8. In Email Routing, create custom addresses:
   - `contact@boardenthusiasts.com` -> `matt@mattstroman.com`
   - `support@boardenthusiasts.com` -> `matt@mattstroman.com`
   - `updates@boardenthusiasts.com` -> `matt@mattstroman.com`
9. Save the rules.

Success check:

- messages sent to those aliases arrive in `matt@mattstroman.com`

### 8. Create Brevo Senders And Generate SMTP Credentials

Goal:

- make Brevo available as the outbound SMTP server for Gmail aliases

Steps:

1. In Brevo, open the senders area.
2. Add sender identities for:
   - `contact@boardenthusiasts.com`
   - `support@boardenthusiasts.com`
   - `updates@boardenthusiasts.com`
3. If Brevo requires sender verification, complete it.
4. Open the SMTP/API credentials area.
5. Create or reveal the SMTP credentials.
6. Store the SMTP username and password securely.

Success check:

- you have working SMTP credentials and verified BE sender identities

### 8b. Create The Brevo Waitlist And Custom Contact Attributes

Goal:

- create the dedicated Brevo waitlist and contact attributes used by the BE landing-page signup sync

**Waitlist**

The backend syncs every new landing-page signup to a single Brevo list identified by the `BREVO_SIGNUPS_LIST_ID` environment variable.

Steps:

1. In Brevo, open **Contacts -> Lists**.
2. Create a new list named `BE Waitlist`.
3. Copy the numeric list ID shown in the Brevo UI.
4. Store it as `BREVO_SIGNUPS_LIST_ID` in the relevant environment file or deployment secret store.

**Custom contact attributes**

The signup sync writes three Brevo attributes. `FIRSTNAME` is typically built in. `SOURCE`, `BE_LIFECYCLE_STATUS`, and `BE_ROLE_INTEREST` must exist before live signups begin or Brevo will ignore those values.

| Attribute name | Type | Values | Notes |
|---|---|---|---|
| `FIRSTNAME` | Text | any string or blank | Usually built in. Verify it exists. |
| `SOURCE` | Text | `landing_page`, `discord`, etc. | Signup channel. |
| `BE_LIFECYCLE_STATUS` | Text | `waitlisted`, `invited`, `converted` | New signups always start as `waitlisted`. |
| `BE_ROLE_INTEREST` | Text | `none`, `player`, `developer`, `developer,player` | Sorted comma-separated role-interest selection. |

Steps to create custom attributes in Brevo:

1. In Brevo, open **Contacts -> Settings -> Contact attributes**.
2. Select **Add a new attribute**.
3. Enter the attribute name exactly as shown above.
4. Choose type **Text**.
5. Save the attribute before moving to the next one.

Success check:

- the `BE Waitlist` list exists and its numeric ID is recorded
- `SOURCE`, `BE_LIFECYCLE_STATUS`, and `BE_ROLE_INTEREST` appear in Brevo as Text attributes
- `FIRSTNAME` exists as a Text attribute

### 9. Configure Gmail To Send As BE Aliases

Goal:

- send 1:1 support and contact mail from Gmail using BE addresses

Steps:

1. Sign in to Gmail as `matt@mattstroman.com`.
2. Open `Settings` -> `See all settings`.
3. Open `Accounts and Import`.
4. Find `Send mail as`.
5. Select `Add another email address`.
6. Enter the first alias, for example `contact@boardenthusiasts.com`.
7. When Gmail asks whether to treat it as an alias, keep it enabled unless you have a specific reason not to.
8. Choose the option to send through an external SMTP server.
9. Enter the Brevo SMTP settings exactly as provided by Brevo.
10. Save.
11. Gmail will send a verification email to the BE alias.
12. Because Email Routing is already configured, the verification message should arrive in `matt@mattstroman.com`.
13. Open the verification email and approve it.
14. Repeat the process for `support@boardenthusiasts.com`.
15. Repeat the process for `updates@boardenthusiasts.com` if desired.
16. In Gmail settings, enable the option to reply from the same address the message was sent to.

Success check:

- from Gmail compose, you can choose each BE alias in the `From` dropdown

Practical guidance:

- use Gmail aliases for 1:1 communication
- do not use Gmail for newsletter blasts
- use Brevo campaigns for broadcast mail instead

### 10. Create Cloudflare API Token(s)

Goal:

- allow the repository and CI to deploy without full-account credentials

Steps:

1. In Cloudflare, open `My Profile` -> `API Tokens`.
2. Create a token with the minimum permissions needed for:
   - Pages deployment and project management
   - Workers deployment
   - DNS edits if the deployment flow will manage DNS
3. Restrict the token to the `boardenthusiasts.com` account/zone where possible.
4. Copy and store the token securely.

Success check:

- a scoped Cloudflare API token exists and is saved in the team password manager

### 11. Create Supabase Access Tokens Or Service Credentials For CI

Goal:

- let CI and deployment scripts authenticate to Supabase

Steps:

1. In Supabase, create the minimum required token(s) for CLI or management access.
2. Record the project reference.
3. Store the following securely:
   - project reference
   - publishable key
   - secret key
   - any CI access token required by the chosen deployment automation

Success check:

- CI-safe credentials are available for repository secret setup

### 12. Gather Cloudflare Turnstile Site And Secret Keys

Goal:

- protect the signup form from bot abuse

Steps:

1. In Cloudflare, open Turnstile.
2. Create a widget for `boardenthusiasts.com`.
3. Record:
   - site key
   - secret key
4. Store them securely.

Success check:

- you have both Turnstile keys available for deployment

### 13. Add GitHub Environment Variables And Secrets

Goal:

- give the repository enough credentials to deploy and run without storing secrets in source control, including GitHub web-UI-triggered deploys

Steps:

1. Open the GitHub repository settings.
2. Open `Environments`.
3. Create environment `staging`.
4. Create environment `production`.
5. For each environment, add the non-secret deploy values as Environment `vars`.
6. For each environment, add the sensitive deploy values as Environment `secrets`.
7. Use the same variable names that appear in the root `.env` templates so the manual deploy workflow can write the environment file without translation.
8. If production deploys should require an approval step, configure required reviewers on the `production` environment.
9. Optional but recommended: once `config/.env.staging` or `config/.env` is populated locally, publish it into the matching GitHub Environment with:
   - `python ./scripts/dev.py env staging --sync-github-environment`
   - `python ./scripts/dev.py env production --sync-github-environment`
10. Re-run that sync any time you change the local env file before a hosted deploy attempt, because deploy preflight now checks the matching GitHub Environment for drift.
11. Do **not** create manual Cloudflare DNS records for the Worker API hostnames (`api.staging.boardenthusiasts.com`, later `api.boardenthusiasts.com`) when the deploy flow is managing Worker custom domains. The Worker custom domain owns that hostname and Cloudflare will manage the DNS record/certificate attachment.
12. If you created one earlier while bootstrapping staging, delete that DNS record before the first successful Worker custom-domain deploy. Otherwise deploy preflight now fails early with the same conflict you would see in the Cloudflare UI.
13. Do **not** configure the SPA web hostnames (`staging.boardenthusiasts.com`, later `boardenthusiasts.com`) as Cloudflare Email Routing subdomains. Those hostnames are reserved for Cloudflare Pages custom domains.
14. The deploy flow now attaches the Pages custom domain and keeps the proxied CNAME pointed at the current release branch alias automatically. Leave at most one DNS record on the SPA hostname, and make sure it is either absent or a single CNAME that the deploy flow can update.

Recommended Environment `vars`:

- `BOARD_ENTHUSIASTS_SPA_BASE_URL`
- `BOARD_ENTHUSIASTS_WORKERS_BASE_URL`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_AVATARS_BUCKET`
- `SUPABASE_CARD_IMAGES_BUCKET`
- `SUPABASE_HERO_IMAGES_BUCKET`
- `SUPABASE_LOGO_IMAGES_BUCKET`
- `CLOUDFLARE_ACCOUNT_ID`
- `VITE_TURNSTILE_SITE_KEY`
- `BREVO_SIGNUPS_LIST_ID`
- `ALLOWED_WEB_ORIGINS`
- `SUPPORT_REPORT_RECIPIENT`
- `SUPPORT_REPORT_SENDER_EMAIL`
- `SUPPORT_REPORT_SENDER_NAME`
- `VITE_LANDING_MODE`

Recommended Environment `secrets`:

- `SUPABASE_SECRET_KEY`
- `SUPABASE_DB_PASSWORD`
- `SUPABASE_ACCESS_TOKEN`
- `CLOUDFLARE_API_TOKEN`
- `TURNSTILE_SECRET_KEY`
- `BREVO_API_KEY`
- `DEPLOY_SMOKE_SECRET`

Optional future hosted-auth values:

- `SUPABASE_AUTH_GITHUB_CLIENT_ID`
- `SUPABASE_AUTH_GITHUB_CLIENT_SECRET`
- `SUPABASE_AUTH_GOOGLE_CLIENT_ID`
- `SUPABASE_AUTH_GOOGLE_CLIENT_SECRET`

Success check:

- GitHub Environments `staging` and `production` are configured with the required vars/secrets
- the `Manual Deploy` workflow in GitHub Actions can target either environment

### 14. Populate The Root Staging Environment File

Goal:

- prepare the exact operator-owned input file that the maintained root CLI uses for staging deploys

Steps:

1. In the repository root, copy [`config/.env.staging.example`](../config/.env.staging.example) to `config/.env.staging` if that file does not already exist.
2. Populate the staging values gathered during provider setup.
3. Use the current real values for:
   - `BOARD_ENTHUSIASTS_WORKERS_BASE_URL`
   - `SUPABASE_URL` or `SUPABASE_PROJECT_REF`
   - `SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY`
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
   - `VITE_LANDING_MODE=true`
4. Leave future-MVP hosted auth values blank if they are not being validated in this landing-page staging wave:
   - `SUPABASE_AUTH_GITHUB_CLIENT_ID`
   - `SUPABASE_AUTH_GITHUB_CLIENT_SECRET`
   - `SUPABASE_AUTH_GOOGLE_CLIENT_ID`
   - `SUPABASE_AUTH_GOOGLE_CLIENT_SECRET`
5. Keep `replace-me` out of the live file. Use real values or leave optional values blank.

Success check:

- `config/.env.staging` is complete enough that `python ./scripts/dev.py deploy --staging --dry-run-only` can validate without missing-env failures

### 15. Perform A Manual Smoke Test

Goal:

- confirm the provider layer is healthy before implementation work depends on it

Steps:

1. Send an email from a non-Gmail account to `contact@boardenthusiasts.com`.
2. Confirm it arrives in `matt@mattstroman.com`.
3. Reply from Gmail using the `contact@boardenthusiasts.com` alias.
4. Confirm the recipient sees the reply from the BE alias.
5. Repeat the same test for `support@boardenthusiasts.com`.
6. If `updates@` is configured, send a test message from Brevo to a personal inbox.

Success check:

- inbound forwarding and outbound alias sending both work

## Post-Setup Validation Checklist

Before handing off to implementation:

- Cloudflare zone is active
- `boardenthusiasts.com` DNS is managed in Cloudflare
- Supabase staging project exists
- Supabase production project exists
- Brevo domain authentication is green
- Cloudflare Email Routing forwards BE aliases to `matt@mattstroman.com`
- Gmail can send as `contact@` and `support@`
- Turnstile keys exist
- provider secrets are stored securely
- `config/.env.staging` is populated with real staging values
- Brevo waitlist created and its numeric ID is stored as `BREVO_SIGNUPS_LIST_ID`
- Brevo custom attributes `SOURCE`, `BE_LIFECYCLE_STATUS`, and `BE_ROLE_INTEREST` exist as Text type

## Final Preparation Checklist

Run this checklist before the first staging deploy attempt.

### Provider/account readiness

- Cloudflare zone for `boardenthusiasts.com` is active.
- Supabase staging project exists and you have its URL, publishable key, and secret key.
- Supabase production project also exists so the environment split is established up front.
- Brevo domain authentication is green.
- Brevo `BE Waitlist` list exists and its numeric ID is recorded.
- Brevo contact attributes `SOURCE`, `BE_LIFECYCLE_STATUS`, and `BE_ROLE_INTEREST` exist as Text attributes.
- Gmail can send as `contact@boardenthusiasts.com` and `support@boardenthusiasts.com`.
- Cloudflare Email Routing forwards inbound BE aliases into `matt@mattstroman.com`.

### Repository/IaC readiness

- `config/.env.staging` exists and is populated with real values.
- `config/.env.staging` contains the four media bucket names used by the current typed-bucket implementation:
  - `avatars`
  - `card-images`
  - `hero-images`
  - `logo-images`
- `config/.env.staging` also contains the hosted deploy-specific values required by the current automation:
  - `SUPABASE_DB_PASSWORD`
  - `SUPABASE_ACCESS_TOKEN`
  - `DEPLOY_SMOKE_SECRET`
- The root CLI is the planned operator entrypoint:
  - `python ./scripts/dev.py deploy --staging --dry-run-only`
  - `python ./scripts/dev.py deploy --staging`
- Local deploy preflight will now also verify that GitHub Environment `staging` matches the checked-out `config/.env.staging` for vars and secret names.
- The matching GitHub Environment `staging` is populated if you want web-UI-triggered deploys.
- The matching GitHub Environment `production` is populated if you want web-UI-triggered production deploys later.
- You understand which values are repo-built public runtime values versus Worker secrets:
  - SPA build values are injected during the staging build
  - Worker secrets are synced into Cloudflare from the same staging env file during real deploys
- No live `.env` files are committed.

### What the repo already automates

- SPA staging build values from `config/.env.staging`
- Cloudflare Pages staging deploy
- Cloudflare Workers staging deploy
- Cloudflare Worker secret sync for:
  - `SUPABASE_SECRET_KEY`
  - `TURNSTILE_SECRET_KEY`
  - `BREVO_API_KEY`
- Cloudflare Worker secret sync for `DEPLOY_SMOKE_SECRET`
- Supabase schema and storage-bucket provisioning through checked-in migrations/seed/provisioning logic
- landing-page signup sync into Supabase and Brevo using the dedicated waitlist list and required Brevo attributes
- post-deploy smoke verification against the hosted Worker and hosted landing page

### What is still intentionally manual

- provider account creation and verification flows
- DNS zone onboarding and propagation waiting
- Gmail alias verification
- Brevo list and contact-attribute creation
- hosted Supabase social-auth provider setup for future MVP auth flows

### First deployment sequence

1. Run `python ./scripts/dev.py deploy --staging --dry-run-only`.
2. Fix any missing values or provider auth failures that preflight or dry-run expose.
3. Run `python ./scripts/dev.py deploy --staging`.
4. Validate staging end to end:
   - landing page loads
   - signup succeeds
   - Turnstile works remotely
   - Supabase row is created
   - Brevo contact is added to `BE Waitlist`
   - support issue report path works
5. Only after staging is healthy, populate `config/.env` for production and repeat the same pattern there.

GitHub web UI alternative:

1. Open `Actions` in GitHub.
2. Select `Manual Deploy`.
3. Choose target `staging`.
4. Use `dry_run_only` first if desired.
5. Run the workflow once the `staging` GitHub Environment is configured.
6. The workflow now attaches the Cloudflare Pages publish to the triggering Git branch, so launch it from the intended release branch (`staging`, a staging release branch, `production`, or a production release branch) instead of assuming Pages metadata will always point at `main`.

## Known Risks And Recovery Notes

- DNS propagation delays are normal. Wait before assuming a record is broken.
- Multiple SPF records will break email authentication. Keep one merged SPF record.
- Cloudflare Email Routing handles inbound forwarding only. It does not replace SMTP sending.
- Gmail alias verification depends on forwarded email already working.
- Brevo free-plan limits are sufficient for early launch, but broadcast volume is capped. Plan for a future upgrade or provider swap if the audience grows quickly.
- If Gmail shows `on behalf of` in some recipients, re-check SPF, DKIM, DMARC, and sender alignment.
- If Brevo custom attributes are missing when the first signups arrive, lifecycle and role-interest values will be dropped silently.

## Brevo Attribute Reference

This section duplicates the required Brevo signup-sync attributes from [step 8b](#8b-create-the-brevo-waitlist-and-custom-contact-attributes) so operators and future developers can validate the setup quickly.

| Attribute name | Type | Values | Notes |
|---|---|---|---|
| `FIRSTNAME` | Text | any string or blank | Built-in in most Brevo workspaces. |
| `SOURCE` | Text | `landing_page`, `discord`, etc. | Signup channel. |
| `BE_LIFECYCLE_STATUS` | Text | `waitlisted`, `invited`, `converted` | New contacts enter as `waitlisted`. |
| `BE_ROLE_INTEREST` | Text | `none`, `player`, `developer`, `developer,player` | Sorted comma-separated roles from the landing form. |

## Reference Links

- Cloudflare Pages: [https://pages.cloudflare.com/](https://pages.cloudflare.com/)
- Cloudflare Email Routing docs: [https://developers.cloudflare.com/email-routing/](https://developers.cloudflare.com/email-routing/)
- Cloudflare SPF troubleshooting for Email Routing: [https://developers.cloudflare.com/email-routing/troubleshooting/email-routing-spf-records/](https://developers.cloudflare.com/email-routing/troubleshooting/email-routing-spf-records/)
- Cloudflare Turnstile plans: [https://developers.cloudflare.com/turnstile/plans/](https://developers.cloudflare.com/turnstile/plans/)
- Supabase dashboard: [https://supabase.com/dashboard](https://supabase.com/dashboard)
- Supabase billing overview: [https://supabase.com/docs/guides/platform/billing-on-supabase](https://supabase.com/docs/guides/platform/billing-on-supabase)
- Brevo pricing and plan overview: [https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans)
- Brevo free-plan limits: [https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan)
- Brevo SMTP setup: [https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP)
- Brevo contact attribute management: [https://help.brevo.com/hc/en-us/articles/209499585-Manage-contact-attributes](https://help.brevo.com/hc/en-us/articles/209499585-Manage-contact-attributes)
- Gmail send mail as another address: [https://support.google.com/mail/answer/22370?hl=en](https://support.google.com/mail/answer/22370?hl=en)
