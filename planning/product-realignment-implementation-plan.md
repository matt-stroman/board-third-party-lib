# Product Realignment Implementation Plan

## Table of Contents

- [Purpose](#purpose)
- [Wave 6: Access And Role Realignment](#wave-6-access-and-role-realignment)
- [Wave 7: Developer And Moderation Workflow Console](#wave-7-developer-and-moderation-workflow-console)
- [Wave 8: Unified Commerce And Entitlements](#wave-8-unified-commerce-and-entitlements)
- [Wave 9: Board Install And Delivery](#wave-9-board-install-and-delivery)

## Purpose

This plan defines implementation boundaries that are large enough to keep delivery momentum while still supporting meaningful test gates per chunk.

## Wave 6: Access And Role Realignment

Status: in progress

### Chunk 1: Contract And Role Semantics

- OpenAPI + Postman contract updates for:
  - `GET|POST /identity/me/developer-enrollment`
  - `PUT|DELETE /moderation/developers/{developerSubject}/verified-developer`
- maintain role-catalog contract alignment for the six current platform roles:
  - `player`, `developer`, `verified_developer`, `super_admin`, `admin`, `moderator`
- remove deprecated enrollment workflow, conversation, attachment, and notification contract paths
- test gate:
  - contract lint passes
  - contract collection passes in mock mode and live mode (where credentials are available)

### Chunk 2: Backend Access Model

- replace review workflow service behavior with self-service developer role assignment
- add moderator role mutation behavior for `verified_developer`
- remove deprecated persistence entities and ship migration that drops obsolete workflow tables
- test gate:
  - backend endpoint/unit tests green
  - migration applied and rollback tested in integration workflow

### Chunk 3: Frontend Realignment

- implement self-service “Become a Developer” user action in account settings and the `/develop` gate experience
- remove deprecated dedicated `/account/developer-access` route and menu entry in favor of a single activation surface on `/develop`
- remove deprecated workflow UI paths (notifications, request queue, conversation/reply/cancel screens)
- defer moderator/admin UI surfaces until dedicated product UX decisions are finalized
- test gate:
  - frontend build passes
  - route smoke tests pass with updated content assertions

### Chunk 4: Documentation And Wave Tracking

- update root, backend, and planning docs to reflect current implemented surface and future wave ordering
- test gate:
  - docs reviewed in same PR as code changes

## Wave 7: Developer And Moderation Workflow Console

Status: in progress

### Chunk 1: Develop Workspace Shell

- keep `/develop` as the player-to-developer activation surface
- show minimal onboarding copy and `Become a Developer` action when only `player` access is present
- render developer workflow shell only when developer access is enabled:
  - top domain tabs (`Studios`, `Titles`, `Releases`, `Publishing`)
  - left contextual workflow menu
  - in-place workflow content switching without route changes for primary browse/manage tasks
- test gate:
  - frontend route smoke tests cover player onboarding and developer shell markers

### Chunk 2: Moderation Workspace Shell

- add `/moderate` route for moderation workflows
- add main-header `Moderate` nav item shown only for users with `moderator` role
- mirror `/develop` shell pattern (domain/header + side workflow nav) for moderation UX consistency
- include verified-developer role mutation workflow in moderation UI
- test gate:
  - frontend route smoke tests cover moderator and non-moderator route behavior

### Chunk 3: Moderation API Client Wiring

- wire frontend API client methods for:
  - `PUT /moderation/developers/{developerSubject}/verified-developer`
  - `DELETE /moderation/developers/{developerSubject}/verified-developer`
- keep backend contract and behavior aligned with Wave 6 moderation endpoints
- test gate:
  - frontend test stub coverage updated for new API client methods

## Wave 8: Unified Commerce And Entitlements

Status: planned

- purchase orchestration abstractions across external providers
- durable entitlement model that drives ownership in player library surfaces
- event/audit trail for purchase and entitlement transitions
- test gate:
  - provider-agnostic contract tests
  - entitlement consistency integration tests

## Wave 9: Board Install And Delivery

Status: planned

- secure artifact-delivery handoff for entitled players
- Board-targeted install workflow and install-state tracking
- developer release-to-installability validation pipeline
- test gate:
  - end-to-end entitlement-to-install integration coverage
