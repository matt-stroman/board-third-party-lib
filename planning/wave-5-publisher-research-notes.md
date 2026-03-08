# Wave 5 Publisher Research Notes

## Purpose

This document captures early research used to shape Wave 5 planning before implementation starts.

It is intentionally focused on what known third-party publisher/store platforms appear to support from accessible official documentation, and how that should influence the Board Enthusiasts design.

## Current Planning Conclusion

Wave 5 should ship as publisher-agnostic external acquisition binding.

That means:

- the library stores where a player should go to acquire a title
- the library remains agnostic to which publisher/store the developer chose
- the library does not yet assume it can execute payment, download, or installation itself

This keeps Wave 5 compatible with platforms that only expose a normal store page URL, while still leaving room for deeper integrations later.

It should also include a platform-managed supported publisher registry so known providers can be presented consistently while still allowing a custom fallback for unsupported or self-hosted publishers.

## Platform Findings

### itch.io

Official docs reviewed:

- [itch.io API](https://itch.io/docs/api/overview)
- [API Keys](https://itch.io/docs/api/keys)
- [OAuth Applications](https://itch.io/docs/api/oauth-apps)
- [Widgets](https://itch.io/docs/creators/widgets)

What this suggests:

- itch.io has an official API surface rather than being link-only
- itch.io supports API keys and OAuth applications, which makes richer future integration plausible
- itch.io also supports embeddable widgets, which reinforces that link-out or embedded acquisition UX is normal on the platform

Design implication:

- Wave 5 can safely support itch.io through a generic acquisition URL
- a future wave could explore deeper itch.io-specific purchase/ownership/download integration if the real use case justifies it

### Humble Bundle

Official references reviewed:

- [Humble Bundle Developer FAQ](https://support.humblebundle.com/hc/en-us/sections/200515154-Developer-FAQ)

What this suggests:

- Humble Bundle should remain a supported publisher/store target from a product perspective
- this planning pass did not confirm a public self-serve API/integration surface from accessible official documentation

Design implication:

- Wave 5 should treat Humble-compatible titles as generic external acquisition bindings unless a partner-facing API is later confirmed and worth supporting

### Game Jolt

Official docs reviewed:

- [Game API](https://ssr.gamejolt.net/game-api)
- [Sell games on Game Jolt](https://ssr.gamejolt.net/marketplace/sell)

What this suggests:

- Game Jolt exposes an official API, but it is oriented around game-side integration concerns
- the documented capabilities center on achievements/trophies, scores, sessions, data storage, friends, and package retrieval rather than a general-purpose storefront checkout abstraction

Design implication:

- Game Jolt is a useful reminder that some platforms expose game/runtime APIs without exposing the kind of purchase/install API the library would need
- Wave 5 should not assume that "has an API" means "supports unified commerce/install integration"

## Near-Term Design Guidance

Wave 5 should prefer these capabilities:

- a platform-managed `supported_publishers` registry for standardized publisher identity and display metadata
- studio-level reusable external publisher/store connection records
- optional connection linkage to a supported publisher registry row
- custom publisher details on the connection itself when no supported publisher fits
- title-level acquisition binding records
- required external acquisition URL per active binding
- optional provider-specific `jsonb` configuration without requiring it

Wave 5 should avoid these assumptions:

- first-party checkout inside the library
- first-party entitlement issuance
- first-party download hosting
- first-party installation orchestration on Board
- public API creation of new shared supported-publisher registry entries

Those belong in later waves once the commerce and Board-device models are better defined.

## Recommended Wave Split

Recommended upcoming delivery order:

1. Wave 5: external acquisition bindings
2. Wave 6: unified commerce and entitlements
3. Wave 7: Board-native delivery and install

This sequence keeps the first next wave shippable while preserving room for richer integrations where official platform capabilities actually exist.

