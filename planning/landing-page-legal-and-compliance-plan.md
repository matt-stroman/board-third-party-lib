# Production Landing Page Legal And Compliance Plan

## Table of Contents

- [Purpose](#purpose)
- [Important Limitation](#important-limitation)
- [Project Context](#project-context)
- [Compliance Objective](#compliance-objective)
- [Scope For This Wave](#scope-for-this-wave)
- [Baseline Requirements](#baseline-requirements)
- [Email Signup Consent Plan](#email-signup-consent-plan)
- [Privacy Notice Plan](#privacy-notice-plan)
- [Email And Unsubscribe Requirements](#email-and-unsubscribe-requirements)
- [Data Handling And Retention Guidance](#data-handling-and-retention-guidance)
- [Trademark And Public Messaging Guidance](#trademark-and-public-messaging-guidance)
- [Children And Family-Safety Risk Reduction](#children-and-family-safety-risk-reduction)
- [Operational Review Checklist](#operational-review-checklist)
- [Escalation Triggers For Real Counsel Review](#escalation-triggers-for-real-counsel-review)
- [Reference Links](#reference-links)

## Purpose

This document defines a practical legal/compliance planning baseline for the Board Enthusiasts landing-page-only production wave.

It is written so an async reviewer can help keep the public launch posture responsible and consistent with the actual product state.

## Important Limitation

This document is not legal advice and does not replace review by a licensed attorney.

It is a risk-reduction and operations-planning artifact for a small early-stage launch.

## Project Context

Board Enthusiasts (BE) is an independent platform being built for the Board ecosystem.

For this wave, the public product is a landing page that:

- describes BE
- links to Discord and the public BE custom GPT
- collects email addresses for launch updates and future account invites
- routes inbound BE support/contact email to `matt@mattstroman.com`

No public storefront, payment flow, or full user account system is being released in this wave.

## Compliance Objective

The legal/compliance role for this wave should make sure BE launches with:

- truthful public claims
- clear independence from Board
- usable privacy disclosure
- explicit consent handling for email signup
- unsubscribe/suppression handling
- reasonable data minimization

## Scope For This Wave

In scope:

- landing-page copy review
- consent wording review
- privacy notice checklist
- email sender identity and unsubscribe posture
- trademark-safe phrasing and disclaimers
- minimal data retention and deletion expectations

Out of scope for this wave:

- payments law review
- marketplace terms for developers
- tax treatment
- formal partnership agreements
- international expansion analysis beyond basic caution

## Baseline Requirements

Before public launch, BE should have:

- a privacy notice linked from the site footer
- truthful copy that matches actual product availability
- explicit signup consent language
- a clear sender identity in emails
- unsubscribe capability for broadcast email
- internal handling guidance for suppression and deletion requests
- a clear independence disclaimer regarding Board

## Email Signup Consent Plan

Recommended signup posture:

- treat waitlist and update emails as marketing or promotional email for compliance purposes
- do not rely on implied consent
- capture affirmative consent at signup

Recommended signup statement pattern:

- I want email updates from Board Enthusiasts about launch progress, product updates, developer resources, and future invites.

Recommended data to store with each signup:

- email address
- consent timestamp
- consent text version
- signup source
- optional UTM metadata

Recommended UX guidance:

- keep the consent sentence immediately adjacent to the signup CTA
- do not bury it in a distant footer only
- do not pre-check optional boxes if a checkbox is used

## Privacy Notice Plan

The first privacy notice should be simple, readable, and accurate.

Minimum sections to include:

- who operates Board Enthusiasts
- what data is collected in this wave
- why the data is collected
- what third parties process or receive data
- how unsubscribe and deletion requests can be made
- how BE may contact users
- how long data may be retained
- how the notice may change over time

For this wave, the notice should clearly describe:

- email signup data
- site anti-abuse tooling such as Turnstile
- email forwarding/support handling
- providers such as Cloudflare, Supabase, and Brevo

Important rule:

- the privacy notice must describe what actually happens, not what BE might do later

## Email And Unsubscribe Requirements

Broadcast email from BE should follow these operating rules:

- identify BE clearly as the sender
- use accurate subject lines
- include a working unsubscribe path
- honor unsubscribe requests promptly
- keep unsubscribed contacts suppressed from future marketing sends

Operational recommendation:

- use Brevo campaigns for newsletters and announcements
- do not use plain Gmail alias sending for broadcast mail
- keep Gmail aliases for 1:1 contact/support conversations

Suppression handling recommendation:

- store a local suppression state in the BE database
- keep BE database state aligned with Brevo suppression or unsubscribe state

## Data Handling And Retention Guidance

For this wave, BE should follow data minimization.

Recommended rule:

- collect only what the landing-page flow actually needs

That means:

- email required
- first name optional
- no date of birth
- no mailing address
- no phone number
- no sensitive personal data

Retention recommendation:

- keep subscribed contacts while the launch/update purpose remains active
- retain unsubscribe or suppression state long enough to avoid accidental re-mailing
- define a manual review path for deletion requests

Deletion handling recommendation:

- route privacy or deletion requests through `contact@boardenthusiasts.com`
- document an internal process for deleting or suppressing the contact in both the BE database and Brevo

## Trademark And Public Messaging Guidance

BE should consistently present itself as independent from Board.

Recommended practices:

- describe BE as an independent community platform for the Board ecosystem
- use Board only as a referential ecosystem identifier
- avoid any wording that implies endorsement, partnership, or official status unless that becomes true later

Avoid:

- “official Board store”
- “official Board marketplace”
- “from the Board team”
- use of Board logos or copied visual marks

Recommended disclaimer style:

- Board Enthusiasts is an independent community platform and is not the official Board storefront or operator.

## Children And Family-Safety Risk Reduction

Because Board is family-oriented, BE should avoid drifting into child-directed data collection inadvertently.

Risk-reduction guidance for this wave:

- treat the landing page as a general-audience product surface
- avoid child-directed wording in the signup flow
- do not knowingly collect age or birthdate
- if BE later intentionally targets children or collects data from children under 13, require dedicated legal review before launch

## Operational Review Checklist

Before launch:

- privacy notice exists and is linked in the footer
- signup consent wording is present and accurate
- sender identity is clear in outbound mail
- unsubscribe path exists for campaigns
- internal suppression handling is defined
- landing-page copy does not overstate product readiness
- Board independence disclaimer is present
- no copied Board marks or screenshots are used without permission

## Escalation Triggers For Real Counsel Review

Seek real legal review before launch or scale if any of these become true:

- BE begins taking payments
- BE opens to international consumer marketing at meaningful scale
- BE starts targeted children’s features or child-directed messaging
- BE stores materially more personal data than email/name
- BE enters formal commercial arrangements with Board or third-party publishers
- BE plans large-scale outbound campaigns or affiliate/referral programs
- BE receives a trademark complaint, privacy complaint, or platform policy warning

## Reference Links

- FTC CAN-SPAM overview: [https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)
- FTC COPPA overview: [https://www.ftc.gov/business-guidance/privacy-security/childrens-privacy](https://www.ftc.gov/business-guidance/privacy-security/childrens-privacy)
- Board website: [https://board.fun/](https://board.fun/)
- Board SDK docs: [https://docs.dev.board.fun/](https://docs.dev.board.fun/)
- Current BE brand planning doc: [`landing-page-marketing-and-branding-plan.md`](./landing-page-marketing-and-branding-plan.md)
- Current BE implementation planning doc: [`landing-page-implementation-plan.md`](./landing-page-implementation-plan.md)
