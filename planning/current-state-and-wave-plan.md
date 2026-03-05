# Current State And Wave Plan

## Table of Contents

- [Purpose](#purpose)
- [Architecture Decisions Reconfirmed](#architecture-decisions-reconfirmed)
- [Current Implemented State](#current-implemented-state)
- [Wave Plan](#wave-plan)
- [Schema And Identity Boundary](#schema-and-identity-boundary)
- [Delivery Rules For Future Waves](#delivery-rules-for-future-waves)

## Purpose

This document records the currently aligned architecture and delivery plan after completion of the current implemented baseline (foundation plus Waves 1 through 5).

It exists to keep one distinction explicit:

- the repository already implements a usable API/authentication foundation
- Waves 1 through 5 relational work are implemented
- the currently implemented identity workflow still includes review-based developer enrollment and moderator approval
- the next planned implementation boundary is the product realignment program before commerce and install-delivery

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

As of March 5, 2026, the maintained implemented surface is:

- health endpoints: `/`, `/health/live`, `/health/ready`
- Keycloak-backed identity endpoints: `/identity/roles`, `/identity/auth/config`, `/identity/auth/login`, `/identity/auth/callback`, `/identity/me`, `GET|POST /identity/me/developer-enrollment`, `POST /identity/me/developer-enrollment/{requestId}/cancel`, `GET /identity/me/developer-enrollment/{requestId}/conversation`, `POST /identity/me/developer-enrollment/{requestId}/messages`, `GET /identity/me/developer-enrollment/{requestId}/attachments/{attachmentId}`, and `GET /identity/me/notifications`, `POST /identity/me/notifications/{notificationId}/read`
- moderation endpoints: `GET /moderation/developer-enrollment-requests`, `POST /moderation/developer-enrollment-requests/{requestId}/approve`, `POST /moderation/developer-enrollment-requests/{requestId}/reject`, `POST /moderation/developer-enrollment-requests/{requestId}/request-more-information`, `GET /moderation/developer-enrollment-requests/{requestId}/conversation`, and `GET /moderation/developer-enrollment-requests/{requestId}/attachments/{attachmentId}`
- Board profile endpoints: `GET|PUT|DELETE /identity/me/board-profile`
- organization endpoints: public `GET /organizations`, public `GET /organizations/{slug}`, authenticated `POST|PUT|DELETE /organizations...`, and authenticated membership management endpoints
- catalog endpoints: public `GET /catalog`, public `GET /catalog/{organizationSlug}/{titleSlug}`, authenticated title/metadata management endpoints, authenticated media/release/artifact management endpoints, public `GET /supported-publishers`, and authenticated connection/acquisition-binding management endpoints
- EF Core persistence with migrations for `users`, `user_board_profiles`, `organizations`, `organization_memberships`, `titles`, `title_metadata_versions`, `title_media_assets`, `title_releases`, `release_artifacts`, `supported_publishers`, `integration_connections`, and `title_integration_bindings`
- Postman mock-first contract assets for the above endpoints
- backend endpoint unit tests plus Postgres-backed integration coverage for persistence and constraints
- developer automation for local bootstrap, Docker dependencies, and test execution

Not yet implemented:

- Wave 6 access and role realignment (self-service developer enrollment and verified-developer management)
- Wave 7 studio terminology and collaboration model refactor
- Wave 8 title listing/state/verification realignment
- Wave 9 title reporting and moderation-action workflows
- Wave 10 player-library foundation plus unified commerce and entitlements
- Wave 11 Board install-delivery flows
- configured Keycloak brokers for social/game platform SSO in the local realm import

Because those later items are not implemented, they should not remain in the maintained current API contract unless they are being actively delivered in the same wave with tests first.

## Wave Plan

To avoid contract drift, the project should treat the current backend as a completed foundation plus Waves 1 through 5 baseline, then execute the product realignment program before resuming commerce and install-delivery waves.

The detailed realignment execution plan is maintained in [`planning/product-realignment-implementation-plan.md`](product-realignment-implementation-plan.md).

### Foundation (implemented)

- Keycloak integration and browser login callback flow
- bearer-token validation and current-user projection from claims
- platform role catalog exposure
- health/readiness automation and test coverage
- review-based developer enrollment workflow with PostgreSQL-backed request history, moderation messaging/attachments, applicant replies/cancellation, in-app notifications, and moderator approval/rejection/request-more-information endpoints

### Wave 1 (implemented)

Application identity projection and optional Board profile persistence:

- EF Core + migrations
- `users` keyed by immutable Keycloak subject
- `user_board_profiles` for optional Board linkage/cache
- `/identity/me/board-profile` endpoints restored to the maintained contract with backend tests and implementation

### Wave 2 (implemented)

Organizations and memberships.

### Wave 3 (implemented)

Titles and versioned metadata.

Implemented Wave 3 behavior includes:

- storefront-style public routing via `/catalog/{organizationSlug}/{titleSlug}`
- separate lifecycle and visibility controls
- `draft`, `testing`, `published`, and `archived` lifecycle states
- `private`, `unlisted`, and `listed` visibility states
- mutable draft metadata that becomes frozen history once the title leaves draft

See [`backend/docs/title-catalog-schema.md`](../backend/docs/title-catalog-schema.md) for the maintained Wave 3 schema and lifecycle reference.

### Wave 4 (implemented)

Status: implemented on March 2, 2026.

Implemented Wave 4 behavior includes:

- fixed media slots for `card`, `hero`, and `logo`
- semver releases bound to specific metadata snapshots
- explicit `titles.current_release_id` activation/rollback support
- APK artifact metadata stored without delivery URLs
- public catalog detail exposure for media assets and current release summary
- developer endpoints for media, release, publish/activate/withdraw, and artifact management

See [`backend/docs/title-catalog-schema.md`](../backend/docs/title-catalog-schema.md) for the maintained Wave 3 and Wave 4 title/catalog reference.

### Wave 5 (implemented)

Publisher-agnostic external acquisition bindings.

Status: implemented on March 2, 2026.

Implemented Wave 5 behavior includes:

- a platform-managed `supported_publishers` registry surfaced through `GET /supported-publishers`
- reusable organization-scoped `integration_connections` that can reference a supported publisher or organization-owned custom publisher details
- title-scoped `title_integration_bindings` for external acquisition URLs and optional acquisition labels/configuration
- public catalog list exposure of `acquisitionUrl` only
- public catalog detail exposure of the current primary acquisition summary
- enforced primary-binding invariants for enabled title acquisition links

It should also allow a custom publisher/store fallback when no supported registry entry fits, while keeping shared custom-publisher management endpoints out of scope.

### Wave 6 (planned)

Access and role realignment:

- replace review-based developer approval with immediate self-service developer enrollment
- add additive `verified_developer` role assignment/removal managed by moderator and above
- align identity/moderation contract and authorization behavior to the additive role model

### Wave 7 (planned)

Studio domain rename and collaboration model:

- replace `organization` terminology with `studio` in API, business, and documentation surfaces
- enforce owner versus contributor permissions for studio management and title management
- migrate existing persisted data to studio-named schema and route keys

### Wave 8 (planned)

Title listing/state/verification realignment:

- replace visibility state model with listed/unlisted boolean control
- adopt lifecycle states `draft`, `demo`, `early_access`, `published`, `flagged`, and `archived`
- add title verification model tied to releases with carry-forward and reset behavior

### Wave 9 (planned)

Title reporting and moderation actions:

- player title reporting with required issue description and optional attachments
- moderator triage workflows for hide listing, clarification, and flag management
- workflow notifications and auditability for developer/moderator follow-up

### Wave 10 (planned)

Player library foundation, unified commerce, and entitlements.

### Wave 11 (planned)

Board-native download and install delivery.

## Schema And Identity Boundary

The schema boundary is now:

- Keycloak owns credentials, verification, password reset, account linking, external identity brokers, and global platform roles.
- PostgreSQL owns application data and durable references to Keycloak subjects once persistence is introduced.
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
