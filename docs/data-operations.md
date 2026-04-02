# Data Operations Guide

This guide covers the current Board Enthusiasts approach for:

- handling data issues in `staging` or `production`
- deciding whether staging data should be promoted into production
- moving selected data safely when that decision is made

It is intentionally operational and release-focused rather than developer-onboarding focused.

## Table of Contents

- [Current Data Surface](#current-data-surface)
- [Guiding Rules](#guiding-rules)
- [When Data Looks Wrong](#when-data-looks-wrong)
- [Staging To Production Promotion Options](#staging-to-production-promotion-options)
- [Selective Promotion Checklist](#selective-promotion-checklist)
- [Recommended Tools And References](#recommended-tools-and-references)

## Current Data Surface

Board Enthusiasts currently stores and operates data across several systems:

- Supabase Auth
  - account identities
  - email verification state
  - OAuth identities
  - MFA enrollment state
- Supabase Postgres
  - application data such as users, studios, titles, releases, reports, notifications, marketing contacts, and supporting lookup tables
- Supabase Storage
  - media objects and object metadata for public BE image buckets
- Cloudflare Workers Analytics Engine
  - first-party product analytics events
- Cloudflare Workers Observability
  - API operational logs, failures, latency, and traffic volume

Important boundary:

- the BE application database is not the same thing as the Cloudflare analytics datasets
- selective data promotion must account for Auth, Postgres rows, and Storage objects separately

## Guiding Rules

Use these rules whenever we are dealing with release data:

1. Never treat a dashboard click as the only record of a data fix.
2. Prefer scripted, reviewable SQL or seed/migration scripts over ad hoc manual edits.
3. Always identify whether the issue belongs to Auth, Postgres, Storage, or Analytics before touching anything.
4. Preserve a recoverable snapshot or export before applying destructive fixes.
5. Validate the fix with the maintained app flows and smoke coverage, not only with raw SQL.

## When Data Looks Wrong

### 1. Triage The Scope

Start by answering:

- which environment is affected: `staging` or `production`
- which system is affected: Auth, Postgres, Storage, Analytics, or multiple
- whether the issue is bad data, missing data, duplicate data, or unauthorized data exposure
- whether writes should be paused while we investigate

Examples:

- broken profile names or missing titles: usually Postgres projection data
- users unable to sign in: usually Supabase Auth or hosted redirect/provider configuration
- broken images: usually Supabase Storage object/state problems
- missing traffic reporting: usually Cloudflare Analytics Engine or Worker ingestion

### 2. Capture A Recovery Point First

Before changing live data, capture enough state to recover:

- export the affected rows with SQL or `COPY`
- record the project ref and environment
- record the table names, row identifiers, and timestamps involved
- if the issue is broader than a few rows, use Supabase backup/restore tooling rather than hand-editing large sets blindly

For production-impacting data issues, prefer opening an incident note in the root repo or linking the fix to an issue so the reasoning is preserved.

### 3. Reproduce In A Safe Place

When possible:

- reproduce the problem in `staging`
- or reproduce it locally by resetting and seeding a local stack, then replaying the relevant API calls

If the problem depends on hosted data:

- export the affected staging rows
- import only what is needed into a local scratch database or use a hosted staging branch/project for deeper testing

### 4. Fix Through A Reviewable Path

Preferred order:

1. checked-in migration or repair script
2. checked-in SQL runbook snippet attached to an issue or PR
3. manual SQL in Supabase SQL editor only if the exact statement is preserved in the issue or PR

Avoid:

- silent dashboard-only edits with no replayable record
- deleting rows without first exporting them
- changing Auth-linked application rows without confirming the `auth_user_id` still points to a real Auth user

### 5. Validate The Repair

After the data fix:

- re-run the affected user flow in the UI
- re-run targeted backend or frontend tests if the issue exposed a logic bug
- re-run `python ./scripts/dev.py contract-smoke --start-workers` if the change touched maintained API behavior
- re-run `python ./scripts/dev.py workers-smoke --start-stack` if the change touched worker-side ownership, CRUD, or media flows

## Staging To Production Promotion Options

There are two realistic paths.

### Option A: Fresh Production, No Data Promotion

Use this when:

- staging mostly contains smoke or test data
- the cost of re-entering content is low
- we want the cleanest production start

This is the safest option.

### Option B: Promote Staging Data Into Production

Use this only when staging contains enough real setup work that re-entry would be painful.

Important caution:

- staging-to-production promotion is not a one-click BE feature right now
- Auth users, Postgres rows, and Storage objects must be considered together

There are two sub-options.

#### B1. Promote The Whole Staging Database Shape

This is the least error-prone promotion path if production has not launched yet and we want staging to become the baseline.

What this usually means:

- restore or clone the staging database state into the future production project
- then re-apply production-specific configuration such as domains, secrets, allowed origins, and provider settings

Important limitation:

- Storage objects and some hosted project settings may still need separate handling
- treat this as an environment-promotion exercise, not only a table copy

#### B2. Promote Only Selected Data

Use this when:

- only certain studios, titles, releases, or user-owned records should move
- staging also contains test noise we do not want in production

This is more delicate, because relational integrity matters.

## Selective Promotion Checklist

If we choose selective promotion, follow this order.

### 1. Decide Exactly What Is In Scope

Create a promotion inventory:

- which users must exist in production
- which studios belong to those users
- which titles belong to those studios
- which releases, metadata versions, media rows, links, notifications, or reports should move with them
- which rows are test-only and must stay behind

### 2. Confirm Auth Identity Strategy

Application rows depend on Supabase Auth user IDs.

That means one of these must be true before importing app rows:

- the matching Auth users already exist in production with the same `auth.users.id` values
- or Auth users are imported first as part of a whole-project restore/clone path

If the Auth user IDs do not line up, rows in `public.app_users`, studio memberships, reports, notifications, and ownership-sensitive tables will break.

### 3. Export Postgres Rows In Dependency Order

Typical dependency order:

1. lookup tables only if production does not already have the same reference data
2. `public.app_users`
3. `public.app_user_roles`
4. `public.studios`
5. `public.studio_memberships`
6. `public.studio_links`
7. `public.titles`
8. `public.title_metadata_versions`
9. `public.title_metadata_version_genres`
10. `public.title_media_assets`
11. `public.title_releases`
12. player- or moderation-owned records only if they are intentionally part of the promotion

Prefer exporting with explicit row filters by ID instead of table-wide dumps when doing selective promotion.

### 4. Copy Storage Objects Separately

If promoted rows reference BE-hosted media:

- export or copy the referenced bucket objects
- preserve the object paths expected by the promoted Postgres rows
- validate public URLs after the copy

If the staging media should not be reused, update the promoted rows to production-ready media instead.

### 5. Import Into Production In A Controlled Window

Recommended sequence:

1. freeze relevant writes in staging if you need a consistent cut
2. export the selected staging data
3. verify Auth user prerequisites in production
4. import Postgres rows in dependency order
5. copy referenced Storage objects
6. run targeted validation queries
7. validate through the live UI and maintained smoke flows

### 6. Validate Promotion Success

Minimum checks:

- promoted users can sign in
- promoted studios and titles appear in browse
- promoted developer workspaces can still manage the imported content
- promoted media renders correctly
- no foreign-key or ownership breaks are visible in the API flows

## Recommended Tools And References

Primary project references:

- [docs/maintained-stack.md](./maintained-stack.md)
- [docs/staging-release-runbook.md](./staging-release-runbook.md)
- [docs/analytics.md](./analytics.md)
- [backend/docs/storage-buckets.md](../backend/docs/storage-buckets.md)
- [planning/mvp-release-audit.md](../planning/mvp-release-audit.md)

Supabase references:

- [Backups](https://supabase.com/docs/guides/platform/backups)
- [Restore from backups](https://supabase.com/docs/guides/platform/backups#restore-from-a-backup)
- [Branching](https://supabase.com/docs/guides/deployment/branching)

## Current Recommendation For MVP Launch

For the initial staging-to-production decision:

- prefer a clean production launch unless staging accumulates enough real creator setup work to justify promotion
- if promotion is needed, prefer a whole-environment baseline promotion over ad hoc row copying
- use selective promotion only when we have a clearly scoped inventory and a recorded import plan
