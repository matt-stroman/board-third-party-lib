# Technology Fit Recommendation (Initial Planning)

## Table of Contents

- [1) Goals and constraints recap](#1-goals-and-constraints-recap)
- [2) Updated recommendation summary](#2-updated-recommendation-summary)
- [3) Recommended stack (pragmatic default)](#3-recommended-stack-pragmatic-default)
- [4) Why this is likely better than immediate microservices](#4-why-this-is-likely-better-than-immediate-microservices)
- [5) Domain architecture (initial)](#5-domain-architecture-initial)
- [6) Data model direction](#6-data-model-direction)
- [7) Testing strategy (must-have from day 1)](#7-testing-strategy-must-have-from-day-1)
- [8) Practical guidance for the three low-experience areas](#8-practical-guidance-for-the-three-low-experience-areas)
- [9) 30-day implementation plan (updated)](#9-30-day-implementation-plan-updated)
- [10) Alternatives and contingency paths](#10-alternatives-and-contingency-paths)
- [11) Decision summary](#11-decision-summary)

## 1) Goals and constraints recap

This recommendation optimizes for:

- **$0 / near-$0 startup cost**
- **Strong long-term scaling path** without full rewrites
- **Stability + flexibility** for diverse publishing/payment providers
- **API-first architecture** so developer/player operations are independent of any specific UI
- **Cross-platform client strategy** with a strong path for **native Android/Board** first
- **Automated testing + DevOps** from the start

## 2) Updated recommendation summary

Given the preference for a consistent .NET/C# stack and the likelihood that Board deployment is Android-native, the pragmatic direction is:

- **Backend:** ASP.NET Core 10 + PostgreSQL
- **Client UI:** **.NET MAUI** (native-first, Android/Board prioritized)
- **Architecture style:** **API-first** for both developer and player experiences

This replaces the prior Flutter recommendation as the default frontend direction.

Important caveat:

- **.NET MAUI is not a direct "single codebase web + native" substitute for Flutter.**
- If a browser UI becomes necessary, prefer a separate web UI (likely **Blazor Web App**) backed by the same API contracts.

Current versioning decision (implemented for backend):

- **Backend SDK/tooling:** pin to **.NET SDK 10** (local + CI)
- **Backend target framework:** **`net10.0`**
- **MAUI direction:** align MAUI version/runtime with the chosen .NET major version when the frontend is scaffolded (currently expected to be .NET 10 / MAUI 10)

## 3) Recommended stack (pragmatic default)

### Backend

- **Runtime/framework:** **ASP.NET Core 10 (Web API)**
  - Why: aligns with your current experience; excellent test tooling; high performance; first-class OpenAPI support.
- **Database:** **PostgreSQL**
  - Why: strong relational consistency for purchases/entitlements with JSONB for provider-specific configs.
- **ORM/data access:** **EF Core + targeted Dapper usage** for hot paths.
- **Cache/queue (later):** Redis (optional at first).
- **API style:** REST-first, OpenAPI-described, UI-agnostic application operations.
- **Client contract strategy:** shared DTO contracts and/or generated SDKs for MAUI, web, or other adapters.
- **Auth:** OpenID Connect/JWT-compatible model (start simple; keep identity provider swappable).

### Client UI (Native-first)

- **Primary UI stack:** **.NET MAUI (C#)**
  - Why: technology consistency with backend (.NET/C#) and shared engineering patterns.
  - Why: strong fit for Android-first deployment targets and native device integration.
  - Why: easier organizational fit when backend/client teams share language/runtime knowledge.
- **UI strategy:** thin client(s) over API-backed application workflows for both developer and player surfaces.
- **State management:** choose one MAUI-consistent pattern and standardize early (e.g., MVVM toolkit-based approach).
- **Web UI (optional/later):** separate **Blazor Web App** or equivalent, backed by the same API surface.

### DevOps & delivery

- **Containerization:** Docker + Docker Compose for backend/local dependencies.
- **CI/CD:** GitHub Actions.
- **IaC (later):** Terraform or Pulumi once infra grows.
- **Hosting (free-friendly):**
  - API: Fly.io / Render / Railway-style free tiers (verify current limits).
  - DB: managed Postgres free tier initially.
  - Optional web frontend artifact (later): Cloudflare Pages / Netlify / Vercel free tier.
  - MAUI Android builds: GitHub Actions artifacts + manual/internal distribution at MVP stage.

## 4) Why this is likely better than immediate microservices

Start as a **modular monolith** first, then split by domain when forced by scale/team boundaries.

Benefits now:

- Lower operational complexity
- Faster feature delivery
- Easier local debugging/testing
- Cheaper hosting

Still design for extraction later by enforcing:

- Strict domain boundaries (catalog, developer onboarding, payment orchestration, entitlement, install delivery)
- Async event contracts between modules
- Provider adapter interfaces
- UI/client adapter boundaries (so UI technology choices do not leak into backend domain workflows)

## 5) Domain architecture (initial)

Single deployable backend with internal modules, exposed through an API-first interface used by all clients:

1. **Catalog**: app/game metadata, search tags, visibility rules.
2. **Developer Integrations**: external host configs (itch, Humble, custom URLs).
3. **Payment Orchestration**: provider-neutral checkout abstraction; provider adapters.
4. **Entitlements**: purchase ownership and install permission.
5. **Delivery/Install**: console-compatible install metadata and download handoff.
6. **Identity & Access**: users, developers, admins, roles.

Each module owns its schema segment and public interfaces.

Identity/access direction note (future, not MVP):

- Plan for an API key capability for external application integrations and partner/server-side usage (project/app identification, quotas, revocation, usage tracking).
- Do not use API keys as the primary protection for end-user `/identity/me/*` operations; those should require end-user bearer authentication (and later app/client authorization on top, if needed).

### API-first UI principle (developer + player)

- Treat all business operations as backend application services exposed via API.
- MAUI (and any later UI) should orchestrate user interaction, not own business rules.
- This keeps behavior consistent across developer UI, player UI, and potential admin tools.

### Future rendering adapter direction (note only; not MVP scope)

It is feasible to introduce a UI/rendering abstraction layer later so presentation can be adapted to different runtimes (for example **Blazor**, **Unity**, **Android native**, **Flutter**). This should be treated as a **future framework investment**, not an MVP requirement.

Guardrails for later if pursued:

- Define capability-oriented interfaces (navigation, rendering primitives, input, asset loading) rather than engine-specific APIs.
- Keep domain/application contracts independent from rendering concerns.
- Implement adapters per runtime/engine, with factories/DI wiring at the edge.
- Validate on a small vertical slice before broad framework expansion.
- If Unity participation is introduced, keep shared contracts/plugins Unity-compatible (prefer `netstandard2.1` and a conservative C# feature subset), rather than sharing `net10.0` assemblies directly.

## 6) Data model direction

Use Postgres with hybrid relational + JSONB design:

- Relational tables for core entities: users, developers, products, purchases, entitlements.
- JSONB columns for provider-specific configuration payloads.
- Outbox table for integration events (for reliable async later).

This provides flexibility without sacrificing integrity.

## 7) Testing strategy (must-have from day 1)

- **Backend unit tests:** xUnit + FluentAssertions.
- **Backend integration tests:** Testcontainers (ephemeral Postgres).
- **Contract tests:** provider adapters (payments/content hosts).
- **MAUI client tests:**
  - unit tests for view models/services/state
  - UI/integration tests for critical flows (as tooling matures for chosen targets)
- **Adapter contract tests (later):** if a rendering abstraction layer is introduced, test capability adapters against shared contracts.
- **End-to-end tests:** API integration + selected UI smoke tests in CI.

CI policy:

- block merges if tests/lint/typecheck fail
- collect coverage and enforce a floor
- run migrations in CI validation job

## 8) Practical guidance for the three low-experience areas

### A) Web service hosting

1. Start with one backend service + one MAUI Android app artifact pipeline.
2. Use managed Postgres (free tier) with backup export.
3. Keep secrets in host-managed secret stores (never in repo).
4. Add health endpoints (`/health/live`, `/health/ready`) and log correlation IDs.
5. Add basic dashboards for request rate, error rate, and latency.
6. Add a web frontend deployment only when a browser-based experience is actually needed.

### B) Microservices

Use a staged approach:

- **Stage 1:** modular monolith.
- **Stage 2:** extract first service only when clear pain appears (e.g., payment processor complexity).
- **Stage 3:** add broker/event bus only once async scale warrants it.

Avoid premature microservices; preserve clean boundaries so extraction is mechanical later.

### C) Docker & environment setup

Minimum local stack:

- `api` (ASP.NET Core)
- `db` (Postgres)
- optional `redis`
- MAUI tooling/runtime installed locally for native client work

Tooling baseline (current backend implementation):

- Backend local development and CI use **.NET SDK 10**
- Backend projects target **`net10.0`**

Use `docker-compose.yml` for API/database integration; run MAUI tooling locally in parallel.

## 9) 30-day implementation plan (updated)

1. Create ADRs for backend and frontend decisions.
2. Scaffold backend modular monolith (ASP.NET Core + Postgres + migrations).
3. Scaffold MAUI app shell with API client integration and basic navigation for developer/player flows.
4. Define provider abstraction interfaces (payments + content hosts).
5. Ship first API-first vertical slice:
   - developer registers content host config
   - player browses catalog
6. Add CI: backend tests + MAUI build/test checks + lint/static analysis.
7. Produce Android debug/release pipeline artifacts.
8. Run technical spike(s):
   - validate MAUI app behavior on Board-like Android target
   - assess Unity integration/adapter feasibility only if Board SDK constraints require it

## 10) Alternatives and contingency paths

- **Blazor Web App**: use if browser UI becomes a near-term requirement.
- **Blazor Hybrid (inside MAUI)**: consider if sharing UI components between native shells becomes valuable.
- **Flutter**: still a valid fallback if web + Android single-codebase becomes the top priority later.
- **Unity client/adapter**: treat as a targeted integration path if Board SDK/device deployment constraints force it.

## 11) Decision summary

Given API-first goals, desire for .NET/C# consistency, and likely Android-native Board deployment:

- **Backend:** ASP.NET Core 10 + Postgres (modular monolith)
- **Client UI (default):** .NET MAUI (native-first, Android/Board focused)
- **Web UI:** optional/later, separate client backed by the same API
- **Architecture:** API-first across developer and player experiences; keep room for future UI/rendering adapters without building that framework yet
- **Compatibility guardrail:** Unity (if introduced) should integrate via API and/or Unity-compatible shared contracts, not by consuming backend `net10.0` assemblies directly
- **Ops:** Docker for local backend stack, GitHub Actions CI/CD, free-tier managed hosting until traction
