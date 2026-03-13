# Production Landing Page Marketing And Branding Plan

## Table of Contents

- [Purpose](#purpose)
- [Project Context](#project-context)
- [Brand Objective](#brand-objective)
- [Current Brand Direction To Preserve](#current-brand-direction-to-preserve)
- [Board-Adjacent Positioning Without Infringement](#board-adjacent-positioning-without-infringement)
- [Recommended Brand Foundations](#recommended-brand-foundations)
- [Public-Surface Consistency Plan](#public-surface-consistency-plan)
- [Channel-Specific Guidance](#channel-specific-guidance)
- [Content And Editorial Plan](#content-and-editorial-plan)
- [Email And Blog Guidance](#email-and-blog-guidance)
- [Launch Messaging Recommendations](#launch-messaging-recommendations)
- [Governance And Review Workflow](#governance-and-review-workflow)
- [Reference Links](#reference-links)

## Purpose

This document is written as a standalone briefing for a marketing or branding consultant working asynchronously from the repository.

It defines how Board Enthusiasts should present itself across public touchpoints while preserving the current product direction already reflected in the frontend.

## Project Context

Board Enthusiasts (BE) is building a third-party discovery and publishing surface for the Board ecosystem.

Current public surfaces already in motion:

- BE Discord community
- a public custom GPT focused on the live Board SDK docs
- a frontend codebase whose visual style already establishes a strong design direction

Near-term goal:

- launch `boardenthusiasts.com` as a landing-page-only production site
- collect interested email signups for future MVP invites and updates
- make public-facing BE touchpoints feel like one coherent brand system

Longer-term goal:

- evolve the landing page into the full Board Enthusiasts product site without a visual reset

## Brand Objective

BE should feel:

- clearly related to the Board ecosystem
- credible and technically useful to third-party developers
- welcoming to players and families
- distinctive enough to stand on its own as an independent community platform

The brand should not feel:

- unofficial-but-pretending-to-be-official
- overly corporate
- visually generic
- like a direct copy of Board’s branding, voice, or product language

## Current Brand Direction To Preserve

The existing frontend already contains a clear visual language and should remain the source of truth for the brand foundation.

Observed foundations in the current frontend:

- dark atmospheric backgrounds with layered gradients
- bright accent colors anchored around cyan, gold, orange, and blue
- display typography using `Syne`
- body typography using `Public Sans`
- rounded panels, soft glows, and playful but not childish spacing
- friendly-but-technical tone

Existing assets and references:

- BE favicon/logo at [`frontend/public/favicon.png`](../frontend/public/favicon.png)
- brand tokens in [`frontend/src/styles.css`](../frontend/src/styles.css)

Recommendation:

- do not redesign the BE visual system for the landing page
- treat the current frontend styling as the seed of the long-term brand system

## Board-Adjacent Positioning Without Infringement

Inference from the public Board site and docs:

- Board presents a polished, playful, hardware-adjacent experience
- the ecosystem emphasis is approachable, family-friendly, and social
- the product tone leans modern and optimistic rather than retro or aggressively gamer-centric

BE should echo the ecosystem mood without copying protected elements.

Safe ways to be reminiscent:

- emphasize community, discovery, play, and creator support
- use modern motion, soft depth, and premium-feeling dark surfaces
- speak in terms of “for Board players and developers”
- build a visual bridge through atmosphere and pacing, not imitation

Avoid:

- copying Board’s logos, iconography, product screenshots, or unique mark shapes
- using “official” or any wording that implies BE is operated by Board
- duplicating hero copy structure or specific messaging from Board marketing pages
- matching Board’s exact palette too closely if it becomes visually derivative

Recommended disclaimer pattern:

- Board Enthusiasts is an independent community platform for the Board ecosystem.

## Recommended Brand Foundations

### 1. Positioning

Working position:

- the independent home for Board developers and curious players

Meaning:

- for developers, BE lowers friction to building and sharing for Board
- for players, BE will become the easiest place to discover and install third-party content

### 2. Audience Segments

Primary near-term audience:

- third-party developers exploring the Board SDK

Secondary near-term audience:

- early-adopter players interested in third-party Board content

Tertiary audience:

- community members, collaborators, and ecosystem watchers

### 3. Brand Personality

Recommended traits:

- curious
- capable
- welcoming
- independent
- practical
- optimistic

Traits to avoid:

- snarky
- loud
- edgy-for-its-own-sake
- sterile enterprise language

### 4. Voice And Tone

Voice rules:

- explain clearly
- sound like builders, not marketers first
- be enthusiastic without hype inflation
- keep copy concrete and specific
- avoid buzzword stacks

Tone by channel:

- website: concise, confident, helpful
- Discord: warm, direct, collaborative
- GPT listing: practical, documentation-aware, builder-friendly
- email updates: brief, useful, human
- blog posts: educational, transparent, ecosystem-focused

### 5. Messaging Pillars

Recommended public pillars:

- easier Board development
- better discovery for independent Board content
- one place to track what is coming
- community-built, not gatekept

## Public-Surface Consistency Plan

Every public channel should reuse the same four layers:

1. Same visual identity.
2. Same one-sentence positioning.
3. Same core CTA hierarchy.
4. Same voice rules.

Minimum shared elements to standardize now:

- logo usage
- color palette
- typography pair
- primary CTA phrasing
- short product description
- social/about blurb
- footer disclaimer language

Recommended shared short description:

- Board Enthusiasts is an independent community platform for discovering, tracking, and eventually installing third-party Board games and apps.

Recommended short CTA set:

- Join the Discord
- Get launch updates
- Explore the Board dev helper GPT

## Channel-Specific Guidance

### Website

The landing page should:

- lead with one clear promise
- present BE as real and active, not speculative
- direct visitors to three actions only
- avoid exposing incomplete product navigation

Recommended sections:

1. Hero
2. Short “what BE is” section
3. Why this matters for developers and players
4. Email signup
5. Discord and GPT section
6. Light “what’s coming” roadmap
7. Footer with independence disclaimer

### Discord

Discord should visually and verbally match the site:

- reuse the same logo/avatar
- align channel descriptions with site language
- pin a short welcome message matching the landing page positioning
- avoid casual copy drift in server descriptions and invites

### Public GPT Listing

The GPT listing should:

- clearly describe it as a Board SDK helper for third-party developers
- link back to BE as the independent ecosystem community
- use the same short description and tone as the site

### Email Templates

Email templates should visually echo the site:

- dark background
- soft gradient accents
- same logo
- same cyan-led CTA treatment
- same concise tone

The checked-in Supabase invite template already points in the right direction and should inform future email styling.

## Content And Editorial Plan

The biggest branding mistake at this stage would be inconsistency, not lack of volume.

Recommendation:

- publish less, but make every public artifact look like it came from the same system

Short-term content buckets:

- launch updates
- ecosystem explainers
- developer-start-here guides
- progress posts
- new community/tool announcements

Editorial rules:

- one primary takeaway per post
- one CTA per message
- avoid walls of text
- use screenshots, diagrams, or concrete examples when relevant
- always clarify what is available now versus planned later

## Email And Blog Guidance

Use email and blog as a pair:

- the website hosts the canonical post or update
- email sends the short version and links back

This keeps:

- archive control inside the product surface
- email content reusable
- message history publicly visible over time

Recommended initial email categories:

- launch updates
- developer tooling updates
- ecosystem/community posts

Recommended sender split:

- `updates@boardenthusiasts.com` for newsletters and announcements
- `contact@boardenthusiasts.com` for general responses
- `support@boardenthusiasts.com` for support/help

## Launch Messaging Recommendations

Recommended hero-message direction:

- independent Board discovery and developer support, starting now

Recommended proof points:

- active Discord
- public Board-focused GPT
- clear plan for catalog, installs, and developer visibility

Copy guidance:

- do not claim finished install/purchase workflows yet
- do claim that BE is the place to follow progress and get invited early

Useful messaging pattern:

- what BE is
- why it matters
- what is live now
- what is coming next
- where to join

## Governance And Review Workflow

To keep async contributors aligned, create and maintain a lightweight brand kit containing:

- approved logo files
- approved color tokens
- approved font pair
- three approved short descriptions
- primary CTA list
- approved disclaimer language
- example hero copy
- example Discord/about copy
- example email header/footer block

Recommended review rule:

- no public-facing asset ships without a quick brand pass against the current frontend tokens and voice rules

## Reference Links

- Board website: [https://board.fun/](https://board.fun/)
- Board support/FAQ: [https://board.fun/pages/support?hcUrl=%2Fen-US](https://board.fun/pages/support?hcUrl=%2Fen-US)
- Board SDK docs: [https://docs.dev.board.fun/](https://docs.dev.board.fun/)
- Current BE favicon/logo asset: [`frontend/public/favicon.png`](../frontend/public/favicon.png)
- Current BE frontend styling tokens: [`frontend/src/styles.css`](../frontend/src/styles.css)
