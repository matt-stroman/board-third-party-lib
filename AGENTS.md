# Board Third Party Library

This repository is intended to house a full solution (database, business logic, web API, and front end user interface) for a library which exposes third party games and apps for the [Board](https://board.fun/) ecosystem to players.

## Background

The Board console is very new and the team behind it has released an SDK for developing games on it and opened it to third parties. On the Board console, they have provided an app which acts as a library for *first party* games. However, as of yet they have not provided a unified solution for a place where third party developers can host and expose their game(s) and/or app(s) to the public. A group of third party developers have come together and agreed that we want to create such a unified solution so that players have a smooth experience very similar to what Board provides for its first party content.

Board has also not yet provided a monetization solution for third party developers (e.g. a store-front like Steam or the Epic Games Store). They have said that, for now, developers are intended to host their own content and handle their own monetization (i.e. method for players to purchase the content). Once purchased, players can sideload the downloaded APK(s) onto the console via their `bdb` CLI (similar to Android's `adb`, but much more limited). This method is cumbersome for both developers and players:

- Different developers will likely be choosing different publishing websites, content hosts, and payment processors to handle their content, so the experience for players will be fractured.
- Many players are not technical, particularly since the platform is geared toward families, so sideloading via `bdb` is not an acceptable option.

## Requirements

- Third party developers must be able to
  - host their content with the publishing platform of their choosing (e.g. itch.io, HumbleBundle)
  - if not already included with their publishing platform, handle payments for their content via the processor of their choosing (e.g. Stripe, Square)
  - perform CRUD operations for these configurations in the library via either web API or light web UI

- Players/users must be able to
  - view and/or query registered library content (i.e. view via any front end UI that may be developed or query via the web API)
  - pay for new content, ideally via a single unified experience rather than having to go to an external website
  - download and install content directly on Board without having to connecting USB and use `bdb`

## Supplemental Documentation

Board website: https://board.fun/
Board User FAQ: https://board.fun/pages/support?hcUrl=%2Fen-US
Board SDK Docs: https://docs.dev.board.fun/
itch.io Creator FAQ: https://itch.io/docs/creators/faq
Humble Bundle FAQ: https://support.humblebundle.com/hc/en-us/sections/200515154-Developer-FAQ

## Repository Structure

This repository houses both the backend and frontend for the Board Third Party Library as git submodules:

Backend path: /backend
Frontend path /frontend

## Technologies and Architecture

TBD