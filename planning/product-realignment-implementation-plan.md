# Product Realignment Implementation Plan

## Table of Contents

- [Purpose](#purpose)
- [Realignment Outcomes](#realignment-outcomes)
- [Delivery Constraints](#delivery-constraints)
- [Wave Sequence](#wave-sequence)
- [Wave 6: Access And Role Realignment](#wave-6-access-and-role-realignment)
- [Wave 7: Studio Domain Rename And Collaboration](#wave-7-studio-domain-rename-and-collaboration)
- [Wave 8: Title Listing, State, And Verification Realignment](#wave-8-title-listing-state-and-verification-realignment)
- [Wave 9: Title Reporting And Moderation Actions](#wave-9-title-reporting-and-moderation-actions)
- [Wave 10 And Beyond](#wave-10-and-beyond)
- [Cross-Wave Release Strategy](#cross-wave-release-strategy)

## Purpose

This document translates the March 2026 product realignment proposal into implementation waves that are large enough to move quickly, but bounded enough to test thoroughly.

The realignment themes are:

- rename `organization` terminology to `studio`
- keep player-facing creator language as `developer`
- move from approval-gated developer enrollment to immediate self-service enrollment
- shift moderation focus from who can become a developer to title visibility and safety
- introduce verified developer/title signals and title reporting workflows

## Realignment Outcomes

After Waves 6 through 9 are complete, the platform should support:

- anonymous public catalog and developer browsing
- default `player` accounts with instant upgrade to `developer`
- additive roles (`player`, `developer`, `moderator`, `admin`, `super_admin`, and `verified_developer`)
- studio ownership/contributor collaboration model
- title listing based on a simple listed/unlisted model
- title lifecycle states aligned to draft/demo/early-access/published/flagged/archived
- moderator-first title safety workflows (unlist, flag, clarification, reports)

## Delivery Constraints

- Maintain API-first and TDD-first ordering for every externally visible change.
- Keep each wave deployable without requiring the next wave to land first.
- Prefer compatibility bridges for one wave when renaming externally visible terms.
- Avoid mixing commerce/install-delivery with this realignment program.

## Wave Sequence

1. Wave 6: Access and role realignment.
2. Wave 7: Studio terminology and contributor permissions.
3. Wave 8: Title listing/state/verification realignment.
4. Wave 9: Title reporting and moderation actions.
5. Wave 10: Player library plus unified commerce and entitlements (moved later).
6. Wave 11: Board-native download/install (moved later).

## Wave 6: Access And Role Realignment

Scope:

- Replace review-based developer enrollment flow with immediate self-service enrollment.
- Add `verified_developer` as an additive role assignable by moderator and above.
- Update identity/me payloads to expose realignment-ready access state.
- Keep anonymous and player access boundaries explicit in API authorization behavior.

Primary contract/back-end work:

- deprecate and then remove developer-enrollment request/conversation endpoints
- add self-service developer enrollment endpoint(s) under `/identity/me`
- add moderator/admin endpoints for verified-developer assignment/removal
- align policy/authorization tests to additive role matrix

Testing boundary:

- contract tests for enrollment, verified-role management, and role-gated access
- endpoint unit tests for authorization and validation
- integration tests confirming role changes propagate correctly through Keycloak-backed flow

Exit criteria:

- no approval queue is required for developer access
- verified-developer state can be toggled by moderator/admin workflows

## Wave 7: Studio Domain Rename And Collaboration

Scope:

- Rename application and API terminology from `organization` to `studio`.
- Align catalog route keys and developer endpoints to `studio` naming.
- Enforce studio ownership and contributor permissions:
  - owner can CRUD studio and manage contributors
  - contributors can CRUD studio titles but cannot update/delete the studio or manage contributors

Primary contract/back-end work:

- introduce studio-named endpoints and payload fields
- migrate persistence naming/constraints from organization tables to studio equivalents
- update title ownership FKs and related services to studio semantics
- provide one-wave compatibility aliases for existing organization endpoints/routes where feasible

Testing boundary:

- migration tests validating data preservation from organizations to studios
- authorization tests for owner vs contributor permission splits
- contract tests for studio endpoints and catalog path changes

Exit criteria:

- maintained contract and docs use `studio` as canonical terminology
- organization compatibility aliases are either removed or clearly marked sunset with date

## Wave 8: Title Listing, State, And Verification Realignment

Scope:

- Replace multi-value visibility model with `isListed` boolean.
- Adopt lifecycle states: `draft`, `demo`, `early_access`, `published`, `flagged`, `archived`.
- Add title verification model with default unverified state.
- Tie verification to releases with carry-forward when previous release was verified.
- Auto-unlist flagged titles.

Primary contract/back-end work:

- schema migration from visibility enum-like field to listed boolean
- lifecycle transition rules and invariants for listability
- moderator endpoints for list/unlist, verify/unverify, and flag/unflag transitions
- public catalog response updates for listed and verified signals

Testing boundary:

- state-machine unit tests for allowed transitions and auto-unlist on `flagged`
- integration tests for release-level verification inheritance/reset behavior
- contract tests for public and developer/moderator title endpoints

Exit criteria:

- listed/unlisted control is the primary moderation lever for title exposure
- lifecycle and verification behavior matches documented rules

## Wave 9: Title Reporting And Moderation Actions

Scope:

- Add player reporting for titles with required issue description.
- Support optional report attachments (screenshots/log files).
- Add moderation workflows for report triage and follow-up actions.
- Add moderation actions planned in the realignment proposal where implemented now:
  - hide listing
  - request clarification
  - developer/title flag indicators

Primary contract/back-end work:

- report submission/retrieval endpoints
- moderation queue endpoints with status transitions and notes
- attachment metadata/storage integration and secure download flow
- notification hooks for developer and moderator follow-up

Testing boundary:

- contract tests for report submission, moderation triage, and attachment retrieval
- integration tests for attachment constraints and moderation status transitions
- authorization tests for anonymous/player/developer/moderator/admin boundaries

Exit criteria:

- moderators can process title safety reports end-to-end in platform
- developers receive actionable moderation feedback through API-visible workflow state

## Wave 10 And Beyond

Wave 10 resumes the previously planned player library plus unified commerce/entitlements work.

Wave 11 remains Board-native download/install delivery, after entitlement and moderation rules are stable.

## Cross-Wave Release Strategy

- Use feature flags for behavior that changes UX semantics across clients.
- Publish deprecation windows in release notes for renamed endpoints and fields.
- Keep per-wave data migrations backward-compatible for at least one rollout window.
- At each wave close, update:
  - OpenAPI and Postman artifacts
  - backend tests and schema docs
  - root and backend planning docs
