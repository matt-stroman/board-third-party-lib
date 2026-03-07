# Current State And Wave Plan

## Table of Contents

- [Purpose](#purpose)
- [Architecture Decisions Reconfirmed](#architecture-decisions-reconfirmed)
- [Current Implemented State](#current-implemented-state)
- [Wave Realignment](#wave-realignment)
- [Schema And Identity Boundary](#schema-and-identity-boundary)
- [Delivery Rules For Future Waves](#delivery-rules-for-future-waves)

## Purpose

This document records the currently aligned architecture and delivery plan after Wave 8 player personalization and title-report implementation.

It exists to make one distinction explicit:

- the repository already implements a usable API/authentication foundation
- Wave 1 application-owned identity persistence is implemented
- Wave 2 studios and memberships are implemented
- Wave 3 titles and versioned metadata are implemented
- Wave 4 media, releases, and APK artifact metadata are implemented
- Wave 5 supported publishers and external acquisition bindings are implemented
- Wave 6 self-service developer access and verified-developer role moderation is implemented
- Wave 7 workspace-shell and catalog realignment is implemented
- Wave 8 player library, wishlist, reporting, and notification workflows are implemented
- later commerce, entitlement, and Board install-delivery waves remain planned work

Use this document when deciding whether something belongs in the maintained current contract or in a future wave plan.

## Architecture Decisions Reconfirmed

The project remains aligned to these decisions:

- API-first: externally visible behavior starts in the OpenAPI contract and Postman mock/contract assets before backend implementation.
- TDD for backend work: new implementation starts with failing contract tests and backend tests before production code.
- Automation-first: local bootstrap, dependency startup, backend test runs, and repeatable auth infrastructure should stay scriptable with minimal manual steps.
- UI-agnostic backend: the backend exposes application behavior through API so MAUI, web, Board-native, or other clients can consume the same workflows.
- Keycloak-owned identity lifecycle: self-registration, password reset, email verification, brokered identity linking, and platform-role assignment belong to Keycloak, not PostgreSQL.
- Brokered SSO direction: Google, Facebook, Steam, Epic Games, and similar providers should be integrated through Keycloak identity brokering when enabled, not through application-owned credential tables.

## Current Implemented State

As of March 7, 2026, the maintained implemented surface is:

- health endpoints: `/`, `/health/live`, `/health/ready`
- Keycloak-backed identity endpoints: `/identity/roles`, `/identity/auth/config`, `/identity/auth/login`, `/identity/auth/callback`, `/identity/me`, `GET /identity/me/notifications`, `POST /identity/me/notifications/{notificationId}/read`, `GET|PUT /identity/me/profile`, `PUT /identity/me/profile/avatar-url`, `POST /identity/me/profile/avatar-upload`, `DELETE /identity/me/profile/avatar`, `GET|POST /identity/me/developer-enrollment`, and `GET|PUT|DELETE /identity/me/board-profile`
- moderation endpoints: `GET /moderation/developers`, `GET /moderation/developers/{developerIdentifier}/verification`, and `PUT|DELETE /moderation/developers/{developerSubject}/verified-developer`
- player endpoints: `GET /player/library`, `PUT|DELETE /player/library/titles/{titleId}`, `GET /player/wishlist`, `PUT|DELETE /player/wishlist/titles/{titleId}`, `GET|POST /player/reports`, `GET /player/reports/{reportId}`, and `POST /player/reports/{reportId}/messages`
- moderation title-report endpoints: `GET /moderation/title-reports`, `GET /moderation/title-reports/{reportId}`, `POST /moderation/title-reports/{reportId}/messages`, and `POST /moderation/title-reports/{reportId}/validate|invalidate`
- developer title-report endpoints: `GET /developer/titles/{titleId}/reports`, `GET /developer/titles/{titleId}/reports/{reportId}`, and `POST /developer/titles/{titleId}/reports/{reportId}/messages`
- studio endpoints: public `GET /studios`, public `GET /studios/{slug}`, authenticated `POST|PUT|DELETE /studios...`, authenticated membership management endpoints, authenticated studio link CRUD endpoints, and authenticated studio logo/banner upload endpoints
- catalog endpoints: public `GET /catalog`, public `GET /catalog/{studioSlug}/{titleSlug}`, authenticated title/metadata management endpoints, authenticated media/release/artifact management endpoints, public `GET /supported-publishers`, and authenticated connection/acquisition-binding management endpoints; public catalog payloads now expose whether a title has an active report
- EF Core persistence with migrations for `users`, `user_board_profiles`, `studios`, `studio_memberships`, `studio_links`, `titles`, `title_metadata_versions`, `title_media_assets`, `title_releases`, `release_artifacts`, `supported_publishers`, `integration_connections`, `title_integration_bindings`, `player_owned_titles`, `player_wishlist_entries`, `title_reports`, `title_report_messages`, `user_notifications`, and `user_platform_roles`
- Postman mock-first contract assets for the above endpoints
- backend endpoint unit tests plus Postgres-backed integration coverage for persistence and constraints
- developer automation for local bootstrap, Docker dependencies, and test execution
- deterministic local seed automation via `python ./scripts/dev.py seed-data`

Not yet implemented:

- Wave 9 unified commerce and entitlements
- Wave 10 Board install-delivery flows
- configured Keycloak brokers for social/game platform SSO in the local realm import

Because those later items are not implemented, they should not remain in the maintained current API contract unless they are being actively delivered in the same wave with tests first.

## Wave Realignment

To avoid contract drift, the project should treat the current backend as a completed foundation plus Waves 1 through 8 baseline and start the next schema work from the Wave 9 boundary.

### Foundation (implemented)

- Keycloak integration and browser login callback flow
- bearer-token validation and current-user projection from claims
- platform role catalog exposure
- health/readiness automation and test coverage

### Wave 1 (implemented)

Application identity projection and optional Board profile persistence:

- EF Core + migrations
- `users` keyed by immutable Keycloak subject
- `user_board_profiles` for optional Board linkage/cache
- `/identity/me/board-profile` endpoints in the maintained contract with backend tests and implementation

### Wave 2 (implemented)

Studios and memberships.

### Wave 3 (implemented)

Titles and versioned metadata.

### Wave 4 (implemented)

Media slots, semver releases, current-release activation, and APK artifact metadata.

### Wave 5 (implemented)

Publisher-agnostic external acquisition bindings.

### Wave 6 (implemented)

Status: implemented on March 5, 2026.

Implemented Wave 6 behavior includes:

- self-service developer enrollment via `POST /identity/me/developer-enrollment`
- enrollment state read model via `GET /identity/me/developer-enrollment`
- moderator role-mutation endpoints for `verified_developer` assignment/removal on developer accounts
- developer-access checks that tolerate stale bearer role claims by rechecking Keycloak
- removal of deprecated enrollment workflow persistence and API/UI surfaces (request queues, workflow conversations/attachments, and in-app notifications)

### Wave 7 (implemented)

Status: implemented on March 7, 2026.

Developer, moderation, player, and public-catalog workflow-shell realignment.

Implemented Wave 7 behavior includes:

- keep `/develop` as a shared player/developer entry where players can self-enable developer access
- show minimal onboarding UX on `/develop` for player-only accounts
- render developer console workflows in-place on `/develop` with top domain tabs and contextual side navigation
- expand the Studios workflow with in-place studio overview, create, and settings mutation flows (no primary route change required)
- add `/moderate` workspace plus a header-level `Moderate` nav item shown only for moderator-role users
- mirror the same workflow-shell pattern between `/develop` and `/moderate` for consistent navigation
- wire moderation workspace to user-directory + verification-state APIs with fuzzy account selection and a single verified toggle workflow
- normalize workspace shell layout behavior across `/player`, `/develop`, and `/moderate`
- remove obsolete standalone `/develop/studios/...` pages once their create/overview/settings behavior is superseded by the in-place `/develop` studio workflows
- add deterministic Wave 7 seed data for auth/catalog/workspace validation through `python ./scripts/dev.py seed-data`
- extend studio management with public link CRUD plus studio logo/banner upload and URL support
- render studio branding and studio links on public studio pages, including icon affordances for common social hosts
- align `/browse` and `/studios/{studio-slug}` around the same live client-side search/filter/results interaction model

### Wave 8 (implemented)

Status: implemented on March 7, 2026.

Player personalization, title reporting, and in-app moderation follow-up workflows.

Implemented Wave 8 behavior includes:

- player-owned `My Games` and wishlist read/write endpoints plus frontend workflows
- player-submitted title reports with open-conflict prevention
- public active-report indicators on catalog and title detail surfaces
- moderator title-report inbox, targeted follow-up messaging, and resolution actions
- developer title-report threads for moderated follow-up
- player report-thread inbox and reply workflow
- in-app notifications with unread badge state and workflow deep links for moderation/report activity

### Wave 9 (planned)

Unified commerce and entitlements.

This wave must introduce purchase orchestration and entitlement-state delivery on top of the already-implemented player library foundation.

### Wave 10 (planned)

Board install-delivery flows.

## Schema And Identity Boundary

The schema boundary is:

- Keycloak owns credentials, verification, password reset, account linking, external identity brokers, and global platform roles.
- PostgreSQL owns application data and durable references to Keycloak subjects.
- Cached identity fields in PostgreSQL are snapshots only and must not replace Keycloak as the source of truth.
- Brokered SSO provider metadata may be surfaced via API configuration endpoints, but provider setup remains a Keycloak realm concern.
- Platform roles may still exist in Keycloak and bearer claims, but player-facing surfaces should describe access state in UI terms instead of exposing raw role codes directly.

## Delivery Rules For Future Waves

For every new externally visible capability:

1. Update the OpenAPI contract first.
2. Add or update Postman mock examples and executable contract tests.
3. Add failing backend unit and integration tests.
4. Implement production code and migrations.
5. Run automated backend and contract test suites.
6. Update the maintained docs and agent guidance in the same change set.


