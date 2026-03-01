# Current State And Wave Plan

## Table of Contents

- [Purpose](#purpose)
- [Architecture Decisions Reconfirmed](#architecture-decisions-reconfirmed)
- [Current Implemented State](#current-implemented-state)
- [Wave Realignment](#wave-realignment)
- [Schema And Identity Boundary](#schema-and-identity-boundary)
- [Delivery Rules For Future Waves](#delivery-rules-for-future-waves)

## Purpose

This document records the currently aligned architecture and delivery plan before the next implementation wave begins.

It exists to make one distinction explicit:

- the repository already implements a usable API/authentication foundation
- Wave 1 application-owned identity persistence is implemented
- Wave 2 organizations and memberships are now implemented
- Wave 3 titles and versioned metadata are now implemented
- later relational media/release/integration waves still remain planned work

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

As of March 1, 2026, the maintained implemented surface is:

- health endpoints: `/`, `/health/live`, `/health/ready`
- Keycloak-backed identity endpoints: `/identity/roles`, `/identity/auth/config`, `/identity/auth/login`, `/identity/auth/callback`, `/identity/me`
- Board profile endpoints: `GET|PUT|DELETE /identity/me/board-profile`
- organization endpoints: public `GET /organizations`, public `GET /organizations/{slug}`, authenticated `POST|PUT|DELETE /organizations...`, and authenticated membership management endpoints
- catalog endpoints: public `GET /catalog`, public `GET /catalog/{organizationSlug}/{titleSlug}`, and authenticated title/metadata management endpoints
- EF Core persistence with migrations for `users`, `user_board_profiles`, `organizations`, `organization_memberships`, `titles`, and `title_metadata_versions`
- Postman mock-first contract assets for the above endpoints
- backend endpoint unit tests plus Postgres-backed integration coverage for persistence and constraints
- developer automation for local bootstrap, Docker dependencies, and test execution

Not yet implemented:

- media assets, releases, integrations, commerce, and install-delivery schema
- configured Keycloak brokers for social/game platform SSO in the local realm import

Because those later items are not implemented, they should not remain in the maintained current API contract unless they are being actively delivered in the same wave with tests first.

## Wave Realignment

To avoid contract drift, the project should treat the current backend as a completed foundation plus Wave 1 baseline and start the next schema work from a clean boundary.

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

### Wave 4 (next)

Media, releases, and APK artifacts.

### Wave 5

External integration connections and bindings for content hosting, with commerce still deferred unless explicitly pulled forward.

## Schema And Identity Boundary

The schema boundary is now:

- Keycloak owns credentials, verification, password reset, account linking, external identity brokers, and global platform roles.
- PostgreSQL owns application data and durable references to Keycloak subjects once persistence is introduced.
- Cached identity fields in PostgreSQL are snapshots only and must not replace Keycloak as the source of truth.
- Brokered SSO provider metadata may be surfaced via API configuration endpoints, but provider setup remains a Keycloak realm concern.

## Delivery Rules For Future Waves

For every new externally visible capability:

1. Update the OpenAPI contract first.
2. Add or update Postman mock examples and executable contract tests.
3. Add failing backend unit and integration tests.
4. Implement production code and migrations.
5. Run automated backend and contract test suites.
6. Update the maintained docs and agent guidance in the same change set.
