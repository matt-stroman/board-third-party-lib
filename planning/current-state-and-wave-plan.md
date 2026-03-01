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
- the relational schema and application-owned domain model waves are still planned work

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
- Postman mock-first contract assets for the above endpoints
- backend endpoint unit tests and readiness integration coverage
- developer automation for local bootstrap, Docker dependencies, and test execution

Not yet implemented:

- EF Core persistence model and migrations
- application-owned `users` projection table
- `user_board_profiles` persistence and API CRUD
- organizations, memberships, titles, releases, integrations, commerce, and install-delivery schema
- configured Keycloak brokers for social/game platform SSO in the local realm import

Because those items are not implemented, they should not remain in the maintained current API contract unless they are being actively delivered in the same wave with tests first.

## Wave Realignment

To avoid contract drift, the project should treat the current backend as a foundation phase and start the next schema work from a clean boundary.

### Foundation (implemented)

- Keycloak integration and browser login callback flow
- bearer-token validation and current-user projection from claims
- platform role catalog exposure
- health/readiness automation and test coverage

### Wave 1 (next)

Application identity projection and optional Board profile persistence:

- add EF Core + migrations
- implement `users` keyed by immutable Keycloak subject
- decide whether `user_board_profiles` belongs in Wave 1 or a small Wave 1b immediately after `users`
- only add `/identity/me/board-profile` endpoints back into the maintained contract when failing Postman contract tests and backend persistence tests are in place

### Wave 2

Organizations and memberships.

### Wave 3

Titles and versioned metadata.

### Wave 4

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
