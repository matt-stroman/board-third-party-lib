---
name: AI Agent Handoff
about: Structured implementation brief for Codex/Copilot-style issue assignment
title: "[AI] "
labels: []
assignees: []
---

## Summary
Describe the requested implementation in 2-5 sentences.

This section should answer:
- what needs to be built or changed
- why the change is needed now
- what outcome counts as success

## Intended AI Agent
We're using @Codex.

## Repository Context
Provide enough context so the implementing agent does not need prior conversational history.

Include:
- the relevant repo/submodule(s): `root`, `frontend`, `backend`, `api`
- the current product wave/initiative/feature
- any related branches, PRs, issues, or planning docs

Useful references:
- planning docs:
- design docs:
- related issues:
- related PRs:

## Problem Statement
Explain the current gap, bug, or missing capability.

Cover:
- current behavior
- desired behavior
- why the current state is insufficient

## Scope
List exactly what is in scope for this issue.

Examples:
- frontend form changes
- backend API behavior
- schema/migration changes
- CI or deployment automation
- docs and operator setup

## Out Of Scope
List anything that should explicitly **not** be changed as part of this issue.

Examples:
- broader redesigns
- unrelated refactors
- future-MVP follow-ups
- provider-account setup outside the current wave

## Product And UX Requirements
Describe the required user-facing behavior and copy.

Include:
- final wording, if already decided
- field labels, button text, empty/error states
- accessibility or responsive behavior requirements
- any accepted/rejected UX alternatives

## Technical Requirements
Describe the required implementation constraints.

Include as applicable:
- preferred abstractions/interfaces
- data modeling expectations
- enum/value constraints
- environment/config requirements
- integration/provider behavior
- public API posture

## Data Model Expectations
If the issue touches persistence, specify the intended data shape.

Include:
- required entities/tables
- enum values or constrained types
- migration expectations
- compatibility/default/backfill behavior

## Provider / External Service Expectations
Document any interaction with external providers.

Examples:
- Supabase
- Cloudflare
- Brevo
- GitHub OAuth
- Google OAuth

For each provider, specify:
- what is already configured
- what must be added in code
- what must remain manual, if anything

## Implementation Notes
Add practical guidance for the implementing agent.

Useful content:
- known good entrypoints such as `python ./scripts/dev.py ...`
- files likely to need changes
- known pitfalls from prior waves
- current temporary workarounds that should be preserved or removed

## Testing Requirements
List the exact tests expected for acceptance.

Cover:
- frontend tests
- backend tests
- contract tests
- CLI/tests/docs validation
- manual verification steps if necessary

## Acceptance Criteria
Provide a flat, concrete checklist of done conditions.

Example format:
- [ ] New signup field is captured in the frontend and sent in the request payload.
- [ ] Backend persists the new field with constrained validation.
- [ ] Brevo sync includes the new attribute.
- [ ] Docs explain any required provider-side setup.
- [ ] All required tests are added and passing.

## Deliverables
State what the final implementation should include.

Examples:
- code changes
- migrations
- tests
- docs
- follow-up issue(s), if a known defer is expected

## Open Questions
List any unresolved questions that the implementing agent should either:
- answer during implementation, or
- raise back to a human if they become blocking

## Suggested Handoff Comment
Optional text to paste as the first issue comment after assigning the AI agent:

> Implement end-to-end within the current maintained stack. Preserve current repo standards, add tests/docs, and keep any public API exposure aligned to the documented requirements in this issue.
