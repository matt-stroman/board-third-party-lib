# Pre-Production Rebuild Runbook

This runbook creates a brand-new temporary hosted environment at `pre-production.boardenthusiasts.com` so we can validate a clean rebuild without touching the current `staging` stack.

> Temporary environment notice
>
> This environment is intentionally temporary.
> Once it is verified, migrate the validated DNS and routing back onto `staging.boardenthusiasts.com`, then remove the temporary `pre-production` environment from the maintained tooling and platform configuration.

## Scope

- Rebuild a new Supabase project for a second staging-like environment
- Restore the current `staging` data into that new project
- Restore the current `staging` Storage objects into that new project
- Create matching temporary Cloudflare Pages and Workers surfaces
- Point them at:
  - SPA: `https://pre-production.boardenthusiasts.com`
  - API: `https://api.pre-production.boardenthusiasts.com`
- Keep the current `staging` environment intact the entire time

Because the current plan tier does not include downloadable project backups, this runbook uses the logical disaster-recovery bundle created locally from the existing hosted project.

## Prerequisites

- access to Supabase Dashboard for the existing and new projects
- access to Cloudflare Dashboard for the `boardenthusiasts.com` zone
- access to GitHub repo settings for Environments
- a shell with:
  - `npx`
  - Supabase CLI available through `npx --yes supabase`
  - `psql`
- if `psql` is not installed, install current PostgreSQL client tools before you start the restore phase

## What We Already Verified

### Redirect URL drift

The current staging Supabase project includes production redirect URLs because the hosted Supabase config renderer builds redirect URLs from:

- `BOARD_ENTHUSIASTS_SPA_BASE_URL`
- every origin listed in `ALLOWED_WEB_ORIGINS`

That logic lives in:

- [scripts/dev.py](../scripts/dev.py)
  - `build_supabase_auth_redirect_urls(...)`
  - `render_supabase_deploy_config(...)`

So if the staging env file includes production origins in `ALLOWED_WEB_ORIGINS`, staging will also allow production sign-in and recovery callbacks.

That is not the best explanation for the current `1016` outage, because public unauthenticated API routes are failing too, but it absolutely can cause auth confusion and cross-environment redirect mistakes.

For the new pre-production Supabase project:

- do **not** include `https://boardenthusiasts.com`
- do **not** include `https://staging.boardenthusiasts.com`
- include only:
  - `http://localhost:5173`
  - `https://pre-production.boardenthusiasts.com`
  - `https://pre-production.boardenthusiasts.com/auth/signin`
  - `https://pre-production.boardenthusiasts.com/auth/signin?mode=recovery`

### Hosted email templates are versioned in the repo

The maintained Supabase Auth templates are versioned here:

- [backend/supabase/config.toml](../backend/supabase/config.toml)
- [backend/supabase/templates/confirmation.html](../backend/supabase/templates/confirmation.html)
- [backend/supabase/templates/recovery.html](../backend/supabase/templates/recovery.html)
- [backend/supabase/templates/magic-link.html](../backend/supabase/templates/magic-link.html)
- [backend/supabase/templates/invite.html](../backend/supabase/templates/invite.html)
- [backend/supabase/templates/email-change.html](../backend/supabase/templates/email-change.html)
- [backend/supabase/templates/reauthentication.html](../backend/supabase/templates/reauthentication.html)
- [backend/supabase/templates/email-changed-notification.html](../backend/supabase/templates/email-changed-notification.html)
- [backend/supabase/templates/password-changed-notification.html](../backend/supabase/templates/password-changed-notification.html)
- [backend/supabase/templates/mfa-factor-enrolled-notification.html](../backend/supabase/templates/mfa-factor-enrolled-notification.html)
- [backend/supabase/templates/mfa-factor-unenrolled-notification.html](../backend/supabase/templates/mfa-factor-unenrolled-notification.html)

### Backup audit

The disaster-recovery bundle for actual rebuild use is:

- [artifacts/supabase-disaster-recovery-backups/2026-04-17-091011](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011)

Storage backup verification already passed:

- `staging`
  - object manifest entries: `113`
  - files downloaded: `113`
  - bytes in manifest: `92,527,487`
  - bytes on disk: `92,527,487`
- `production`
  - object manifest entries: `57`
  - files downloaded: `57`
  - bytes in manifest: `8,433,537`
  - bytes on disk: `8,433,537`

Use the new disaster-recovery bundle for rebuild work.
Do not rely on the earlier SQL-only bundle by itself.

## Files To Use

### Rebuild source bundle

- [artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/database-logical-full](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/database-logical-full)
- [artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects)
- [artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/project-state](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/project-state)

### Temporary pre-production env templates

- [config/.env.pre-production.example](../config/.env.pre-production.example)
- [config/.env.pre-production](../config/.env.pre-production)

## Naming To Use

Use these names consistently:

- Supabase project display name: `board-enthusiasts-pre-production`
- Supabase app env: `pre-production`
- SPA hostname: `pre-production.boardenthusiasts.com`
- API hostname: `api.pre-production.boardenthusiasts.com`
- GitHub Environment name: `pre-production`
- Suggested Cloudflare Pages project name: `board-enthusiasts-pre-production`
- Suggested Cloudflare Worker name: `board-enthusiasts-api-pre-production`

## Phase 1: Create The New Supabase Project

1. Open Supabase Dashboard.
   - Go to [https://supabase.com/dashboard/projects](https://supabase.com/dashboard/projects)
2. Click `New project`.
3. Choose the same organization that holds the current staging and production projects.
4. In the create-project form:
   - Set `Name` to `board-enthusiasts-pre-production`
   - Choose the same `Region` as the current staging project
   - Set a strong database password and store it securely
5. Click `Create new project`.
6. Wait for the project status to become ready.
7. Click the new project.
8. In the top project switcher, confirm you are inside `board-enthusiasts-pre-production`.

## Phase 2: Collect New Supabase Values

1. In the new pre-production project, click `Connect` in the upper right.
2. Copy and save:
   - `Project URL`
   - `Session pooler` connection string
   - direct connection string if shown and needed later
3. In the left sidebar, go to `Project Settings` -> `API`.
4. Copy and save:
   - `Project URL`
   - `anon` / publishable key
   - `service_role` or new `secret` key, depending on what the dashboard exposes
5. In the left sidebar, go to `Project Settings` -> `Data API` or `API Keys` if the UI label differs.
6. Confirm the project ref from the URL matches the new project.

## Phase 3: Populate The Local Pre-Production Env File

1. Open [config/.env.pre-production](../config/.env.pre-production).
2. Fill in:
   - `BOARD_ENTHUSIASTS_APP_ENV=pre-production`
   - `BOARD_ENTHUSIASTS_SPA_BASE_URL=https://pre-production.boardenthusiasts.com`
   - `BOARD_ENTHUSIASTS_WORKERS_BASE_URL=https://api.pre-production.boardenthusiasts.com`
   - `SUPABASE_PROJECT_REF=<new pre-production project ref>`
   - `SUPABASE_URL=https://<new pre-production project ref>.supabase.co`
   - `SUPABASE_PUBLISHABLE_KEY=<new pre-production publishable key>`
   - `SUPABASE_SECRET_KEY=<new pre-production secret key>`
   - `SUPABASE_DB_PASSWORD=<new pre-production database password>`
   - `SUPABASE_ACCESS_TOKEN=<operator Supabase access token>`
   - `SUPABASE_*_BUCKET` names from the staging backup bundle
   - Cloudflare, Turnstile, Brevo, support, and smoke values when ready
3. Keep `ALLOWED_WEB_ORIGINS` restricted to:
   - `http://localhost:5173`
   - `https://pre-production.boardenthusiasts.com`
4. Do not add production or staging origins to the new pre-production file.

## Phase 4: Restore The Database

### Files to restore

Use these files from the staging disaster-recovery bundle:

- [roles.sql](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/database-logical-full/roles.sql)
- [schema.sql](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/database-logical-full/schema.sql)
- [data.sql](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/database-logical-full/data.sql)
- [managed-schema.sql](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/database-logical-full/managed-schema.sql)
- [managed-data.sql](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/database-logical-full/managed-data.sql)

### Get the connection string

1. In Supabase Dashboard for the new pre-production project, click `Connect`.
2. Copy the `Session pooler` connection string.
3. Replace `[YOUR-PASSWORD]` with the new project database password.

### Run the restore

Run these commands from a shell on your machine.
Replace `<CONNECTION_STRING>` with the session pooler string from the previous step.

```powershell
psql --single-transaction --variable ON_ERROR_STOP=1 --dbname "<CONNECTION_STRING>" --file "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\database-logical-full\roles.sql"
psql --single-transaction --variable ON_ERROR_STOP=1 --dbname "<CONNECTION_STRING>" --file "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\database-logical-full\schema.sql"
psql --single-transaction --variable ON_ERROR_STOP=1 --dbname "<CONNECTION_STRING>" --file "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\database-logical-full\data.sql"
psql --dbname "<CONNECTION_STRING>" --file "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\database-logical-full\managed-schema.sql"
psql --dbname "<CONNECTION_STRING>" --file "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\database-logical-full\managed-data.sql"
```

### Notes for the managed schema files

- The managed files include `auth`, `storage`, and `supabase_migrations` content.
- Because the new Supabase project already has default managed schemas, `managed-schema.sql` may surface some duplicate-object errors.
- If that happens, pause and inspect before retrying.
- Do not skip `managed-data.sql`, because that is the part that restores the managed rows.

## Phase 5: Verify The Restored Database In Supabase UI

1. In the new pre-production Supabase project, open `Table Editor`.
2. Confirm the expected tables exist in `public`.
3. Open `SQL Editor`.
4. Run sanity checks like:

```sql
select count(*) from public.studios;
select count(*) from public.titles;
select count(*) from public.offerings;
select count(*) from auth.users;
select count(*) from storage.objects;
```

5. Compare the results to the restored data you expect from staging.

## Phase 6: Restore Storage Objects

### What was backed up

Use the staging storage bundle here:

- [buckets.json](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects/buckets.json)
- [objects.json](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects/objects.json)
- [download-manifest.json](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects/download-manifest.json)
- [files](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects/files)

### Re-create or verify buckets in Supabase UI

1. In the new pre-production Supabase project, go to `Storage`.
2. Confirm these buckets exist:
   - `avatars`
   - `card-images`
   - `hero-images`
   - `logo-images`
3. If any bucket is missing, click `New bucket`.
4. Create the bucket using the settings from [buckets.json](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects/buckets.json):
   - same bucket name
   - same `public` setting
   - same file-size limit
   - same allowed MIME types

### Upload the backed-up files

Use the Supabase CLI for this part.

1. Open a shell.
2. Log in if needed:

```powershell
npx --yes supabase login
```

3. Link to the new pre-production project:

```powershell
npx --yes supabase init --workdir "C:\Source\board-enthusiasts\board-enthusiasts\.dev-cli-logs\supabase-pre-production-link"
npx --yes supabase link --project-ref "<NEW_PRE_PRODUCTION_PROJECT_REF>" --password "<NEW_PRE_PRODUCTION_DB_PASSWORD>" --workdir "C:\Source\board-enthusiasts\board-enthusiasts\.dev-cli-logs\supabase-pre-production-link"
```

4. Copy each bucket from the backup bundle into the new project:

```powershell
npx --yes supabase storage cp -r "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\storage-objects\files\avatars" ss:///avatars --experimental --workdir "C:\Source\board-enthusiasts\board-enthusiasts\.dev-cli-logs\supabase-pre-production-link"
npx --yes supabase storage cp -r "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\storage-objects\files\card-images" ss:///card-images --experimental --workdir "C:\Source\board-enthusiasts\board-enthusiasts\.dev-cli-logs\supabase-pre-production-link"
npx --yes supabase storage cp -r "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\storage-objects\files\hero-images" ss:///hero-images --experimental --workdir "C:\Source\board-enthusiasts\board-enthusiasts\.dev-cli-logs\supabase-pre-production-link"
npx --yes supabase storage cp -r "C:\Source\board-enthusiasts\board-enthusiasts\artifacts\supabase-disaster-recovery-backups\2026-04-17-091011\staging\storage-objects\files\logo-images" ss:///logo-images --experimental --workdir "C:\Source\board-enthusiasts\board-enthusiasts\.dev-cli-logs\supabase-pre-production-link"
```

### Verify object counts

1. In Supabase Dashboard, go to `Storage`.
2. Check each bucket.
3. Confirm the total objects line up with [objects.json](../artifacts/supabase-disaster-recovery-backups/2026-04-17-091011/staging/storage-objects/objects.json).

Expected total staging object count: `113`

## Phase 7: Configure Auth In The New Supabase Project

### URL Configuration

1. In Supabase Dashboard for the new pre-production project, go to `Authentication` -> `URL Configuration`.
2. Set `Site URL` to:

```text
https://pre-production.boardenthusiasts.com
```

3. In `Redirect URLs`, add exactly:

```text
https://pre-production.boardenthusiasts.com
https://pre-production.boardenthusiasts.com/auth/signin
https://pre-production.boardenthusiasts.com/auth/signin?mode=recovery
http://localhost:5173
http://localhost:5173/auth/signin
http://localhost:5173/auth/signin?mode=recovery
```

4. Remove:
   - `https://boardenthusiasts.com`
   - `https://www.boardenthusiasts.com`
   - `https://staging.boardenthusiasts.com`
   - any production or staging callback path derived from those origins

### Providers

1. Go to `Authentication` -> `Providers`.
2. For each provider you use in staging:
   - GitHub
   - Discord
   - Google
3. Copy the same provider settings into the new project, but make sure the provider-side callback URLs also include the new pre-production Supabase project callback URL.
4. If a provider app has separate allowed origins or redirect URIs, update those in the provider console too.

### Email Templates

1. Go to `Authentication` -> `Email Templates`.
2. For each template type in the UI, copy the content from the matching repo file listed earlier in this document.
3. Use [backend/supabase/config.toml](../backend/supabase/config.toml) as the source of truth for:
   - which templates are maintained
   - intended subjects

### SMTP

For this temporary pre-production environment, mirror the current staging approach and do not configure custom SMTP unless you intentionally need it.

## Phase 8: Create The Temporary Cloudflare Stack

### Cloudflare Pages

1. Open Cloudflare Dashboard.
2. Go to `Workers & Pages`.
3. Click `Create application`.
4. Choose `Pages`.
5. Create or connect a new project named:

```text
board-enthusiasts-pre-production
```

6. If Cloudflare asks for a production branch, use the same branch strategy you use for staging rebuild validation.
7. After the Pages project exists, go to:
   - `Workers & Pages`
   - `board-enthusiasts-pre-production`
   - `Custom domains`
8. Add the custom domain:

```text
pre-production.boardenthusiasts.com
```

### Cloudflare Worker

1. In Cloudflare Dashboard, go to `Workers & Pages`.
2. Click `Create application`.
3. Choose `Workers`.
4. Create a Worker named:

```text
board-enthusiasts-api-pre-production
```

5. After creation, open the Worker.
6. Go to `Settings` -> `Variables and Secrets`.
7. Add the plain-text variables from [config/.env.pre-production](../config/.env.pre-production).
8. Add the secrets from [config/.env.pre-production](../config/.env.pre-production).
9. Go to `Settings` -> `Domains & Routes`.
10. Add the custom domain:

```text
api.pre-production.boardenthusiasts.com
```

## Phase 9: Create The DNS Records

1. In Cloudflare Dashboard, go to the `boardenthusiasts.com` zone.
2. Open `DNS`.
3. Add or update the record for the SPA hostname:
   - Type: `CNAME`
   - Name: `pre-production`
   - Target: the Cloudflare Pages target provided by the Pages project
4. Add or update the record for the API hostname:
   - Type: `CNAME`
   - Name: `api.pre-production`
   - Target: the Worker route target provided by the Worker project
5. Wait until both custom domains show active in Cloudflare.

## Phase 10: Create The GitHub Environment

1. Open GitHub for this repo.
2. Go to `Settings` -> `Environments`.
3. Click `New environment`.
4. Create:

```text
pre-production
```

5. Add repository environment variables and secrets from [config/.env.pre-production](../config/.env.pre-production).
6. Do not overwrite the existing `staging` or `production` environments.

## Phase 11: Deploy The App Stack

At the moment, the root automation recognizes the temporary `pre-production` environment files, but the maintained hosted deploy flow is still primarily wired for the long-lived `staging` and `production` targets.

That means:

- use this runbook as the source of truth for the temporary rebuild
- keep temporary environment-specific changes clearly labeled
- once the stack is validated, fold the environment back into `staging`

If you decide to extend the hosted deploy automation to publish pre-production directly, use the naming in this runbook and keep the TODO note that the target is temporary.

## Phase 12: Verify The New Pre-Production Stack

### Public routes

Confirm these load cleanly:

- `https://pre-production.boardenthusiasts.com`
- `https://pre-production.boardenthusiasts.com/browse`
- `https://pre-production.boardenthusiasts.com/studios`
- `https://api.pre-production.boardenthusiasts.com/health/ready`
- `https://api.pre-production.boardenthusiasts.com/catalog?pageNumber=1&pageSize=4`
- `https://api.pre-production.boardenthusiasts.com/internal/home-offering-spotlights`
- `https://api.pre-production.boardenthusiasts.com/internal/be-home/metrics`

### Auth routes

Confirm:

- email sign-in
- password recovery
- OAuth sign-in for every enabled provider
- `/identity/me` succeeds after sign-in

### Data checks

Confirm:

- the top active-now bar renders
- browse listings render
- studios render
- login works
- notification fetch works
- uploads serve from the restored storage buckets

## Phase 13: Decide Whether To Promote

If the new pre-production environment works and the current staging environment still fails:

1. Treat the pre-production rebuild as the validated replacement staging stack.
2. Repoint the staging DNS and routing onto the validated stack.
3. Remove the temporary `pre-production` resources after cutover.
4. Apply the same rebuild strategy to production only after the temporary environment proves stable.

## References

- Supabase CLI backup/restore guide: https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore
- Supabase backup overview: https://supabase.com/docs/guides/platform/backups
- Supabase restore guide and restore caveats: https://supabase.com/docs/guides/platform/migrating-within-supabase/dashboard-restore
- Supabase storage download/auth guide: https://supabase.com/docs/guides/storage/serving/downloads
