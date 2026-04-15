# Board Enthusiasts Analytics Guide

This guide describes the analytics slice currently in place for the initial staging launch, where the data lands, how to query it, and which of the original product questions are answerable now.

The short version:

- Product-behavior events are recorded through the Workers API into Cloudflare Workers Analytics Engine.
- Developer-facing studio and title analytics are stored separately in Supabase Postgres as event definitions plus timestamped event rows.
- API traffic and endpoint usage are monitored through Cloudflare Workers observability.
- Developers can now build saved analytics views with per-card date ranges and derived metrics such as conversion rates and net-change cards.
- Developer notifications, richer API-consumer attribution, hover-expand tracking, and a unified cross-product dashboard are intentionally deferred into follow-up issues.

## What Exists Today

### Product Event Capture

Board Enthusiasts currently records the following first-party product events:

- `page_view`
- `oauth_started`
- `oauth_completed`
- `account_created`
- `browse_filters_applied`
- `title_quick_view_opened`
- `title_detail_viewed`
- `title_get_clicked`

These events are posted from the SPA to the Workers API and written into a Cloudflare Workers Analytics Engine dataset.

Relevant implementation files:

- [frontend/src/app-core/analytics.ts](../frontend/src/app-core/analytics.ts)
- [frontend/src/app-core/shells.tsx](../frontend/src/app-core/shells.tsx)
- [frontend/src/auth.tsx](../frontend/src/auth.tsx)
- [frontend/src/browse/pages.tsx](../frontend/src/browse/pages.tsx)
- [frontend/src/app-core/modals.tsx](../frontend/src/app-core/modals.tsx)
- [backend/apps/workers-api/src/worker.ts](../backend/apps/workers-api/src/worker.ts)
- [backend/apps/workers-api/src/service-boundary.ts](../backend/apps/workers-api/src/service-boundary.ts)
- [backend/cloudflare/workers/wrangler.template.jsonc](../backend/cloudflare/workers/wrangler.template.jsonc)

### Developer Analytics Event Model

Board Enthusiasts also maintains a separate developer-facing analytics model inside Supabase Postgres.

This slice exists so studio and title analytics can support:

- timestamped historical event tracking for developer-relevant actions
- data-driven metric definitions for both studio and title analytics
- saved analytics views per developer account
- calculated metrics that are derived from tracked events instead of being written as raw events themselves

The current model is split between:

- `public.analytics_event_types`
  - metric catalog rows
  - one shared definition table for both studio and title metrics
  - stores descriptor, display copy, scope, aggregation behavior, metric kind, formatting metadata, and optional calculation config
- `public.analytics_events`
  - timestamped event rows for tracked analytics actions
  - scoped to either a studio or a title depending on the metric definition
- `public.developer_analytics_saved_views`
  - per-account saved analytics panel configurations

Important boundary:

- Cloudflare Workers Analytics Engine is still the source for broad product-behavior and route-level reporting
- Supabase Postgres is now the source for developer-facing studio/title analytics cards and saved analytics views
- the developer analytics catalog contains both tracked metrics and calculated metrics, but only tracked metrics write rows into `analytics_events`

Relevant implementation files:

- [backend/supabase/migrations/20260414100000_add_developer_analytics_event_model.sql](../backend/supabase/migrations/20260414100000_add_developer_analytics_event_model.sql)
- [backend/supabase/migrations/20260414113000_backfill_analytics_events_from_current_state.sql](../backend/supabase/migrations/20260414113000_backfill_analytics_events_from_current_state.sql)
- [backend/supabase/migrations/20260415110000_add_developer_analytics_saved_views.sql](../backend/supabase/migrations/20260415110000_add_developer_analytics_saved_views.sql)
- [backend/supabase/migrations/20260415133000_add_developer_analytics_derived_metrics.sql](../backend/supabase/migrations/20260415133000_add_developer_analytics_derived_metrics.sql)
- [backend/apps/workers-api/src/service-boundary.ts](../backend/apps/workers-api/src/service-boundary.ts)
- [frontend/src/developer/develop-workspace.tsx](../frontend/src/developer/develop-workspace.tsx)
- [packages/migration-contract/src/models.ts](../packages/migration-contract/src/models.ts)

### Internal Event Intake Route

The Worker uses `POST /analytics/events` as an internal runtime ingestion route for BE-owned analytics collection.

Important note:

- this route is intentionally not part of the maintained public API contract
- it should not be added to the API-first/Postman/OpenAPI documentation set unless the product explicitly decides to support external analytics ingestion in the future
- it is reachable from the web app because the SPA needs to send analytics to it, but it is treated as an internal implementation route, not a public integration surface

### Environment Separation

Analytics is environment-aware.

- `staging` events write to `board_enthusiasts_events_staging`
- `production` events write to `board_enthusiasts_events_production`

The Worker also stores the environment name inside each recorded event row, so queries can double-check environment even if a dataset is exported or combined later.

### Local Verification

Local verification is available, but with an important limitation:

- We can verify locally that the frontend is emitting analytics events and that the Workers API is accepting them.
- We cannot treat local development as a full end-to-end proof that data landed in the deployed Cloudflare dataset, because Cloudflare notes that local development sessions typically do not contribute data directly to production Analytics Engine.

What we can verify locally today:

1. Unit and integration tests
   - [frontend/src/app-core/analytics.test.tsx](../frontend/src/app-core/analytics.test.tsx)
   - [backend/apps/workers-api/src/worker.test.ts](../backend/apps/workers-api/src/worker.test.ts)
   - [backend/apps/workers-api/src/service-boundary.test.ts](../backend/apps/workers-api/src/service-boundary.test.ts)
2. Browser network activity
   - open the app locally
   - perform the instrumented action
   - confirm a `POST` request is sent to `/analytics/events`
   - confirm the request returns `202`
3. Local Worker behavior
   - confirm the Worker route accepts the payload shape and does not throw or reject the event

What still requires a deployed environment:

- confirming that rows are actually written into `board_enthusiasts_events_staging`
- validating Cloudflare-side queries against real stored rows
- checking Workers observability in the Cloudflare dashboard

For staging launch validation, the recommended path is:

1. deploy to `staging`
2. exercise a few known flows manually
3. query `board_enthusiasts_events_staging`
4. confirm the expected rows are present

### API Observability

Workers observability is enabled for the API deployment, which gives us request-level operational visibility for:

- request volume
- endpoint usage
- failures
- latency

Relevant config files:

- [backend/cloudflare/workers/wrangler.template.jsonc](../backend/cloudflare/workers/wrangler.template.jsonc)
- [backend/apps/workers-api/wrangler.jsonc](../backend/apps/workers-api/wrangler.jsonc)

## How The Analytics Event Rows Are Shaped

Cloudflare Workers Analytics Engine currently gives us one `index` value plus `blob` and `double` columns. BE uses the columns below consistently:

### `index1`

- sampling key in the form ``<env>:<event>``
- example: `staging:title_get_clicked`

### `blob` columns

- `blob1`: environment
- `blob2`: event name
- `blob3`: current path
- `blob4`: auth state
- `blob5`: OAuth provider
- `blob6`: studio slug
- `blob7`: title slug
- `blob8`: surface
- `blob9`: content kind
- `blob10`: anonymous session id
- `blob11`: anonymous visitor id
- `blob12`: previous in-app path / referrer path
- `blob13`: metadata JSON

### `double` columns

- `double1`: event-specific numeric value
- `double2`: second event-specific numeric value

When a value is not used, the app records `null` for blob fields and `-1` for numeric fields.

## Where To Check Each Type Of Data

### Product Analytics

Use Cloudflare Workers Analytics Engine for:

- page order
- page popularity
- OAuth starts and completions
- email/password account creation
- browse filter usage
- quick view vs detail usage
- `Get Title` clicks

Primary datasets:

- `board_enthusiasts_events_staging`
- `board_enthusiasts_events_production`

These are Cloudflare-managed Analytics Engine datasets, not tables inside the BE application database and not part of Supabase Postgres.

Suggested access paths:

1. Cloudflare dashboard for the BE account, then the Analytics Engine query tools for the dataset.
2. Cloudflare Analytics Engine SQL API if you want repeatable scripted reports.

BE-specific access steps:

1. Sign in to the BE Cloudflare account.
2. Open the Analytics Engine dataset tooling in the Cloudflare dashboard.
3. Choose the environment dataset:
   - `board_enthusiasts_events_staging`
   - `board_enthusiasts_events_production`
4. Run the query you need against that dataset.

If you want scripted or repeatable access instead of the dashboard:

1. Get the Cloudflare account ID from the dashboard.
2. Create an API token with `Account | Account Analytics | Read`.
3. Send SQL queries to:
   - `https://api.cloudflare.com/client/v4/accounts/<account_id>/analytics_engine/sql`
4. Use `SHOW TABLES` first if you want to confirm the dataset table exists.

Reference docs:

- [Cloudflare Analytics Engine getting started](https://developers.cloudflare.com/analytics/analytics-engine/get-started/)
- [Cloudflare Analytics Engine SQL API](https://developers.cloudflare.com/analytics/analytics-engine/sql-api/)

### API Usage

Use Cloudflare Workers observability for:

- inbound API traffic
- endpoint/request counts
- failures
- latency
- suspicious or unusual external API usage patterns

Reference docs:

- [Cloudflare Workers logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
- [Cloudflare Workers metrics and analytics](https://developers.cloudflare.com/workers/observability/metrics-and-analytics/)

### Auth Cross-Check

The launch analytics slice tracks `oauth_started` itself, but Supabase Auth audit logs are still useful as a secondary cross-check for auth-provider behavior.

Unlike the Cloudflare analytics datasets above, Supabase Auth audit logs can also be stored in your Supabase Postgres project under `auth.audit_log_entries`.

Reference docs:

- [Supabase Auth audit logs](https://supabase.com/docs/guides/auth/audit-logs)

## Mapping Back To The Original Product Questions

### 1. Which OAuth options are being favored or used most?

Current status: `Available now`

Use `oauth_completed` grouped by `blob5` (provider) for the best view of successful provider usage. `oauth_started` is still useful as a funnel input for comparison.

Sample query:

```sql
SELECT
  blob5 AS provider,
  COUNT(*) AS completions
FROM board_enthusiasts_events_staging
WHERE blob2 = 'oauth_completed'
GROUP BY provider
ORDER BY completions DESC;
```

Important nuance:

- `oauth_started` still matters if you want to compare starts versus completions by provider
- local email/password account creation is tracked separately through `account_created`

To compare starts versus completions:

```sql
SELECT
  blob2 AS event_name,
  blob5 AS provider,
  COUNT(*) AS total
FROM board_enthusiasts_events_staging
WHERE blob2 IN ('oauth_started', 'oauth_completed')
GROUP BY event_name, provider
ORDER BY provider, event_name;
```

### 2. What pages are users visiting first, and in what order as they are new to the site?

Current status: `Available now`

Use `page_view`, grouped by `blob11` (visitor id) and ordered by event timestamp. `blob12` stores the previous in-app path when available.

Sample query:

```sql
SELECT
  timestamp,
  blob11 AS visitor_id,
  blob10 AS session_id,
  blob3 AS path,
  blob12 AS previous_path,
  blob13 AS metadata_json
FROM board_enthusiasts_events_staging
WHERE blob2 = 'page_view'
ORDER BY timestamp DESC;
```

Notes:

- `metadata_json` includes `isNewVisitor`
- the visitor and session ids are anonymous BE-generated ids, not account ids

### 3. What pages are drawing the most traffic?

Current status: `Available now`

Use `page_view`, grouped by `blob3` (path).

Sample query:

```sql
SELECT
  blob3 AS path,
  COUNT(*) AS visits
FROM board_enthusiasts_events_staging
WHERE blob2 = 'page_view'
GROUP BY path
ORDER BY visits DESC;
```

### 4. What search criteria filters are users using most often?

Current status: `Available now`

Use `browse_filters_applied`. The filter state is stored in `blob13` as JSON and the filtered result count is stored in `double1`.

Sample query:

```sql
SELECT
  blob3 AS path,
  blob13 AS filter_state_json,
  COUNT(*) AS uses,
  AVG(double1) AS avg_results_after_filter
FROM board_enthusiasts_events_staging
WHERE blob2 = 'browse_filters_applied'
GROUP BY path, filter_state_json
ORDER BY uses DESC;
```

Important nuance:

- the current implementation only records when the user has applied at least one non-default filter or search term
- default browse state is intentionally not counted in this event stream

### 5. Are users only using quick view, or are they going to the full title details page?

Current status: `Available now`

Compare:

- `title_quick_view_opened`
- `title_detail_viewed`

Sample query:

```sql
SELECT
  blob2 AS event_name,
  COUNT(*) AS total
FROM board_enthusiasts_events_staging
WHERE blob2 IN ('title_quick_view_opened', 'title_detail_viewed')
GROUP BY event_name
ORDER BY total DESC;
```

### 6. How many clicks or visits are each studio and title getting?

Current status: `Partially available now`

Available today:

- studio page visits: `page_view` filtered to studio detail paths in `blob3`
- title detail visits: `title_detail_viewed`
- title quick views: `title_quick_view_opened`
- `Get Title` clicks: `title_get_clicked`
- developer studio analytics cards for follows, unfollows, and follower net change
- developer title analytics cards for tracked actions, saved views, and derived metrics such as wishlist conversion, library conversion, and net-change cards

Still deferred:

- hover-expand counts
- broader cross-product analytics dashboards beyond the current developer workspace cards

Sample query for title interactions:

```sql
SELECT
  blob6 AS studio_slug,
  blob7 AS title_slug,
  blob2 AS event_name,
  COUNT(*) AS total
FROM board_enthusiasts_events_staging
WHERE blob2 IN ('title_quick_view_opened', 'title_detail_viewed', 'title_get_clicked')
GROUP BY studio_slug, title_slug, event_name
ORDER BY total DESC;
```

### 7. Can we notify developers when a user clicks `Get Title`?

Current status: `Deferred`

We now record `title_get_clicked`, which gives us the event source needed for this feature, but the actual notification workflow is not yet implemented.

Follow-up ticket:

- to be handled under the analytics follow-up GitHub issues created from this wave

### 8. Can we monitor web API usage and know when external parties are accessing it?

Current status: `Partially available now`

Available today:

- endpoint usage
- request volume
- failures
- latency

Available later:

- reliable attribution of named external consumers
- per-consumer reporting
- rate limiting by issued API key

Why only partial today:

- without BE-issued API keys or registered consumers, we can see traffic patterns but not confidently identify who a consumer is

### 9. Are people creating new raw accounts instead of using OAuth?

Current status: `Available now`

Use `account_created` for first-party email/password account creation counts.

Sample query:

```sql
SELECT
  COUNT(*) AS raw_accounts_created
FROM board_enthusiasts_events_staging
WHERE blob2 = 'account_created';
```

To compare email/password account creation against OAuth completion:

```sql
SELECT
  COALESCE(blob5, 'email') AS auth_method,
  blob2 AS event_name,
  COUNT(*) AS total
FROM board_enthusiasts_events_staging
WHERE blob2 IN ('oauth_completed', 'account_created')
GROUP BY auth_method, event_name
ORDER BY total DESC;
```

## Current Launch-Phase Event Definitions

This section covers the Cloudflare product-behavior event stream only.

Developer analytics tracked in Supabase use a separate event model and are not represented as Analytics Engine rows.

### `page_view`

When it fires:

- route/view changes in the live shell

Why it matters:

- first page visited
- navigation order
- most-visited pages
- studio page visits

### `oauth_started`

When it fires:

- user chooses Google, GitHub, or Discord sign-in/sign-up

Why it matters:

- compare OAuth provider preference

### `oauth_completed`

When it fires:

- social auth returns successfully and the user session is established

Why it matters:

- compare successful provider usage instead of only starts
- estimate provider dropoff by comparing against `oauth_started`

### `account_created`

When it fires:

- direct email/password signup succeeds

Why it matters:

- measure raw BE account creation separate from OAuth
- compare direct signup usage against OAuth completion

### `browse_filters_applied`

When it fires:

- user applies non-default browse criteria

Why it matters:

- understand which filters and search patterns are actually being used

### `title_quick_view_opened`

When it fires:

- quick view modal opens and loads a title successfully

Why it matters:

- compare quick-view behavior against deeper detail-page behavior

### `title_detail_viewed`

When it fires:

- full title detail page loads successfully

Why it matters:

- title detail traffic
- compare against quick view behavior

### `title_get_clicked`

When it fires:

- user clicks `Get Title` from either quick view or full details

Why it matters:

- strongest current launch signal of external acquisition intent
- future foundation for developer notifications and email alerts

## What Is Intentionally Deferred

These items are not part of the current launch slice:

- developer in-app notifications tied to analytics thresholds such as `Get Title`
- optional developer email alerts tied to analytics thresholds such as `Get Title`
- hover-expand analytics
- external API consumer attribution via API keys
- a single combined analytics dashboard
- deep auth funnel reporting beyond the current start/completion/account-created slice
- peak active player analytics on title cards
- custom developer-selected comparison ranges beyond the current automatic previous-range comparison on derived comparison cards

Those items should be tracked in the root GitHub analytics follow-up issues created alongside this wave.

## Suggested Near-Term Workflow

For staging, the most practical operating rhythm is:

1. Use Workers Analytics Engine for product behavior.
2. Use Workers observability for API traffic and failures.
3. Export or save the SQL queries that matter most for launch reviews.
4. Fold the later analytics work into a dedicated dashboard only after we confirm which reports we keep using repeatedly.

## Long-Term Direction

The preferred end state is a single internal BE analytics dashboard that combines:

- product behavior
- API usage
- developer-facing title/studio reporting
- notification triggers
- environment filtering

This guide is written to make that later consolidation easier instead of inventing one-off reports that we cannot carry forward.
