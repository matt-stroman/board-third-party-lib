# Board Enthusiasts

This repository is intended to house a full solution (database, business logic, web API, and front end user interface) for an index which exposes third party games and apps for the [Board](https://board.fun/) ecosystem to players.

## Background

The Board console is very new and the team behind it has released an SDK for developing games on it and opened it to third parties. On the Board console, they have provided an app which acts as a library for *first party* games. However, as of yet they have not provided a unified solution for a place where third party developers can host and expose their game(s) and/or app(s) to the public. A group of third party developers have come together and agreed that we want to create such a unified solution so that players have a smooth experience very similar to what Board provides for its first party content.

Board has also not yet provided a monetization solution for third party developers (e.g. a store-front like Steam or the Epic Games Store). They have said that, for now, developers are intended to host their own content and handle their own monetization (i.e. method for players to purchase the content). Once purchased, players can sideload the downloaded APK(s) onto the console via their `bdb` CLI (similar to Android's `adb`, but much more limited). This method is cumbersome for both developers and players:

- Different developers will likely be choosing different publishing websites, content hosts, and payment processors to handle their content, so the experience for players will be fractured.
- Many players are not technical, particularly since the platform is geared toward families, so sideloading via `bdb` is not an acceptable option.

## Requirements

- Third party developers must be able to
  - host their content with the publishing platform of their choosing (e.g. itch.io, HumbleBundle)
  - if not already included with their publishing platform, handle payments for their content via the processor of their choosing (e.g. Stripe, Square)
  - perform CRUD operations for these configurations in the index via either web API or light web UI

- Players/users must be able to
  - view and/or query registered index content (i.e. view via any front end UI that may be developed or query via the web API)
  - pay for new content, ideally via a single unified experience rather than having to go to an external website
  - download and install content directly on Board without having to connecting USB and use `bdb`

## Supplemental Documentation

- [Board website](https://board.fun/)
- [Board User FAQ](https://board.fun/pages/support?hcUrl=%2Fen-US)
- [Board SDK Docs](https://docs.dev.board.fun/)
- [itch.io Creator FAQ](https://itch.io/docs/creators/faq)
- [Humble Bundle Developer FAQ](https://support.humblebundle.com/hc/en-us/sections/200515154-Developer-FAQ)

## Repository Structure

This repository houses the API, backend, and frontend for the Board Enthusiasts index as git submodules:

### API

Path: `api/`

A [Postman](https://learning.postman.com/docs/design-apis/overview) API-first design using Postman collections and environments.

### Backend

Path: `backend/`

A Cloudflare Workers API with Supabase-backed auth, database, and storage.

### Frontend

Path `frontend/`

A React + TypeScript SPA built with Vite.

## Technologies, Documentation, and Planning

- Developer-facing documentation lives in the [docs folder](docs/).
- Planning, recommendations, and implementation-tracking artifacts live in the [planning folder](planning/).

## Current Architecture Alignment

- Keep the maintained API contract aligned only to behavior that is implemented or being actively delivered in the same change set.
- Supabase Auth owns the maintained authentication lifecycle concerns for the stack.
- The application database should own only application data and local projections keyed to Supabase auth user identifiers.
- New externally visible features must follow API-first and TDD order: contract/examples/tests first, implementation second.

## Coding Standard

- Prefer abstractions and interfaces for modular implementations that can easily be swapped out with dependency injection.
- Unit and integration tests must be written to public API/interface only. Never make assumptions based on implementation details or members/types that are not accessible. Always consider and cover edge and unexpected input cases in addtion to expected path tests.
- New code will not be accepted without corresponding unit and integration tests.
- New API endpoints must start with OpenAPI and Postman mock/contract coverage before backend implementation begins.
- New backend behavior must start with failing unit/integration tests before production code is added.
- When refactoring, do not leave commented out code or stale/unused code. That can always be recovered via version history. Prefer keeping the codebase current and clean.
- Root developer automation must be exposed through `python ./scripts/dev.py ...`; do not require contributors to use ad hoc submodule-local entrypoints for routine setup, test, or sync workflows.
- Keep the maintained stack rooted in the active workspace and submodule layout: backend-owned runtime code in `backend/`, frontend-owned runtime code in `frontend/`, and shared root orchestration in `python ./scripts/dev.py ...`.
- Avoid divergent code paths for different environments whenever reasonably possible. Prefer configuring local and other non-production environments to emulate production behavior closely. Add environment-specific code only when there is no practical way to align the environment itself with production expectations.
- All non-private members and types must be clearly documented with applicable and appropriate tagging (e.g. XML docs for C#, Javadoc for JS, etc.)
- In docs, when providing links, do so with the `[]()` link syntax so that they are proper clickable links. Also add any anchors and such so that users can easily navigate through the documents. Favor doc usability, with good use of markdown syntax (including, but not limited to, blocks, quotes, inline code and code blocks, info/warning/notice boxes, etc.)
- Keep repository concerns separated: project-wide docs/planning/scripts/config belong in the root repository, while backend-only/frontend-only docs/planning/scripts/config belong in their respective submodule folders (e.g. `backend/docs`, `backend/planning`, `frontend/docs`, submodule-local compose/config files).
- You may update `AGENTS.md` files (root and submodules) as needed to improve project context, clarify standards, and preserve useful working guidance as the project evolves.

## Expected Worfklow for Waves

Never commit directly to the `main` branch. Always work via GitHub feature branches for new features, and regular branches for bug fixes or developer-facing changes such as documentation or dev scripts.

1. Fetch and pull latest from `main`
2. Create a new branch for your work
3. Unless change is documentation or dev-facing-scripts only, always run all tests before committing changes.
4. Iterate on the Wave, keeping commits as small and compartmentalized as possible (e.g. targeted in logical sets), with markdown-friendly concise commit summary and clear general explanation of changes in the commit description. No need to mention file names and line numbers unless particularly applicable, as those are already readily visible in the changes.
5. Create PR for merge into `main` only when the Wave is feature complete and fully tested.
6. Do not block locally waiting for remote checks.
7. Branches from branches are okay if moving to a dependent Wave before another is merged to `main`, but prefer to keep this branch dependency structure thin. Prefer to finish getting things merged to `main` first, if possible.
