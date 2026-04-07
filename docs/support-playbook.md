# Support Playbook

This playbook is the first entry point for anyone offering Board Enthusiasts site support.

Use it when a player, developer, moderator, or operator reports a technical issue with the live site. It is intentionally written for safe support handling rather than deep implementation detail.

Use it together with:

- [docs/production-release-runbook.md](./production-release-runbook.md)
- [docs/data-operations.md](./data-operations.md)
- [docs/analytics.md](./analytics.md)

## Table of Contents

- [Support Goals](#support-goals)
- [Guiding Rules](#guiding-rules)
- [First Response Checklist](#first-response-checklist)
- [Password Recovery](#password-recovery)
- [Sign-In And Account Access](#sign-in-and-account-access)
- [Broken Page Or Site Behavior](#broken-page-or-site-behavior)
- [Catalog, Studio, Or Media Issues](#catalog-studio-or-media-issues)
- [Support Intake And Escalation](#support-intake-and-escalation)

## Support Goals

When supporting users, optimize for:

- restoring access safely
- minimizing further confusion or lockout
- keeping sensitive credentials and tokens out of chat, tickets, and screenshots
- creating a clear handoff record if engineering or operators need to take over

## Guiding Rules

1. Never ask a user to send you their password, one-time code, recovery link, access token, or full auth email contents.
2. Prefer user-driven recovery flows in the BE product over dashboard-only provider actions.
3. If the issue touches live account state, record what happened before changing anything.
4. If a manual operator action is needed, keep it in trusted operator channels and do not paste privileged command lines or secret values into public or shared docs.
5. If the issue might affect more than one user, treat it as a product incident rather than a one-off support request.

## First Response Checklist

Before changing anything, capture:

- environment: `production` or `staging`
- affected route or flow
- affected account email address
- exact user-facing error message
- the approximate time it happened
- whether the issue is reproducible

If the user included a screenshot, make sure it does not expose:

- reset links
- verification codes
- browser devtools data
- access tokens or provider callback URLs

## Password Recovery

This is the first thing to check for account-access issues.

### Expected User Flow

The maintained recovery path is:

1. The user opens [`/auth/signin`](https://boardenthusiasts.com/auth/signin).
2. The user chooses the forgot-password flow inside BE.
3. BE sends the reset request through Supabase with the maintained recovery callback.
4. The reset link returns the user to the BE recovery flow.
5. The user sets a new password in the BE reset-password screen.

### What Support Should Tell The User First

Ask the user to:

1. Start from the BE sign-in page, not from a provider dashboard.
2. Request a fresh password reset from the built-in forgot-password flow.
3. Open the newest reset email only.
4. Use the reset link in the same browser where they requested it, when possible.

### If The User Says The Reset Link Logged Them In Directly

This usually means the reset email was generated outside the maintained BE recovery flow, or it returned to the site root instead of the BE recovery route.

Support guidance:

1. Ask the user to ignore that email link.
2. Have them request a new reset from BE itself at [`/auth/signin`](https://boardenthusiasts.com/auth/signin).
3. Confirm they are using the newest recovery email, not an older one.
4. If the same thing still happens from the BE flow, escalate as an auth-routing bug.

Operator note:

- Do not use dashboard-issued password reset emails as the normal support path for BE users unless you have already confirmed they return to the maintained BE recovery page.

### If The User Does Not Receive The Recovery Email

Check with the user:

1. Did they type the same email address they use to sign in?
2. Did they check spam, junk, promotions, and filtered folders?
3. Did they wait a few minutes before requesting another email?

If the problem continues:

1. Confirm the account exists in the correct environment.
2. Confirm the hosted auth email path is healthy.
3. Check whether a broader mail-delivery issue is affecting other users.

### If The User Can Open The Reset Screen But Cannot Save A New Password

Ask for:

- the exact error text
- whether the password meets BE policy requirements
- whether they are using an expired or older email/code

Then verify:

- the reset session is active
- the user is on the BE reset-password screen, not just signed in normally
- there is no broader auth-provider incident

### Operator-Only Recovery Actions

If a user remains blocked after the normal BE recovery flow:

- use trusted operator access only
- prefer setting up a fresh user-driven recovery path over ad hoc dashboard experimentation
- if a temporary manual account repair is necessary, record it in the support handoff and require the user to change the password again immediately after regaining access

Do not document or share privileged step-by-step operator commands in public support notes.

## Sign-In And Account Access

If the user cannot sign in at all:

1. Confirm they are using the correct environment and URL.
2. Confirm whether the issue is password-based sign-in, social sign-in, or MFA-related.
3. Ask for the exact message shown in the UI.
4. Check whether the issue affects one account or multiple accounts.

Common buckets:

- wrong password or stale recovery state
- email not confirmed
- provider callback or redirect issue
- temporary auth-provider outage
- app projection issue after a valid sign-in

If sign-in succeeds but the account looks incomplete or missing roles, continue with [docs/data-operations.md](./data-operations.md) to investigate Auth versus Postgres projection state.

## Broken Page Or Site Behavior

If a page is broken, blank, or behaving unexpectedly:

1. Capture the exact URL.
2. Ask whether the issue appears signed out, signed in, or both.
3. Ask whether it reproduces in a private browser window.
4. Check whether it is limited to one browser or device.
5. Check whether the issue began after a deploy, content change, or account change.

Escalate immediately if:

- the home page, browse page, sign-in page, or support page is unavailable
- multiple users report the same problem
- the issue suggests data exposure, auth confusion, or broken recovery flows

## Catalog, Studio, Or Media Issues

If a report is about missing or incorrect public content:

1. Determine whether the issue is with titles, studios, releases, links, or media.
2. Confirm whether the content is missing, stale, duplicated, unpublished, or publicly visible when it should not be.
3. Confirm whether the issue exists in both public pages and authenticated workspace views.
4. If media is broken, determine whether the problem is the record, the file, or the rendered page.

Use [docs/data-operations.md](./data-operations.md) when the problem appears to be live data rather than a frontend-only display issue.

## Support Intake And Escalation

Every support case should end with one of these outcomes:

- resolved directly with user guidance
- resolved with a documented operator action
- escalated to engineering with reproduction details
- escalated as an incident because multiple users or core flows are affected

When escalating, include:

- user impact
- affected environment
- affected route or feature
- exact message or symptom
- whether recovery, sign-in, or public browsing is blocked
- what support already tried

If the issue appears to involve logs, delivery failures, or broader operational health, continue with:

- [docs/production-release-runbook.md](./production-release-runbook.md)
- [docs/analytics.md](./analytics.md)
- [docs/data-operations.md](./data-operations.md)
