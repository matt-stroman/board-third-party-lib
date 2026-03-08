# Wave 1 Route Inventory

This inventory freezes the minimum maintained UX surface for the migration staging demo.

## Public Routes

| Route | Purpose | Primary marker |
| --- | --- | --- |
| `/` | Landing page and top-level entry | `Board Enthusiasts` |
| `/browse` | Public catalog browse surface | `Browse` |
| `/studios/blue-harbor-games` | Public studio profile page | `Blue Harbor Games` |
| `/browse/blue-harbor-games/lantern-drift` | Public title detail page | `Lantern Drift` |
| `/signin?error=identity-provider-unavailable` | Sign-in failure fallback | `Sign in is unavailable right now` |

## Authenticated Routes

| Route | Access level | Purpose | Primary marker |
| --- | --- | --- | --- |
| `/player` | player | My Games workspace shell | `My Games` |
| `/player/wishlist` | player | Wishlist empty-state path | `No wishlist items yet` |
| `/player?workflow=reported-titles` | player | Player title reports workflow | `Reported Titles` |
| `/player?workflow=account-profile` | player | Board profile workflow | `Save profile` |
| `/player?workflow=account-settings` | player | Identity/account settings workflow | `Account Settings` |
| `/develop` | developer | Developer console overview | `Studio Overview` |
| `/develop/studios/11111111-1111-1111-1111-111111111111/titles` | developer | Studio title list workflow | `Manage title metadata` |
| `/develop/studios/11111111-1111-1111-1111-111111111111/titles/new` | developer | Title creation workflow | `Create title` |
| `/develop/titles/33333333-3333-3333-3333-333333333333` | developer | Title settings workflow | `Save title settings` |
| `/develop/titles/33333333-3333-3333-3333-333333333333/metadata` | developer | Title metadata workflow | `Save metadata` |
| `/develop/titles/33333333-3333-3333-3333-333333333333/media` | developer | Title media workflow | `Configure card, hero, and logo media` |
| `/develop/titles/33333333-3333-3333-3333-333333333333/releases` | developer | Release management workflow | `Create release` |
| `/develop/titles/33333333-3333-3333-3333-333333333333/acquisition` | developer | Acquisition bindings workflow | `Current bindings` |
| `/moderate` | moderator | Moderation workspace | `Verify Developers` |
| `/account` | player | Account entry route | `Player library access` |

## Explicit Not-Found Routes

These routes must remain unavailable because the current UX has already collapsed them into other workflows.

| Route | Expected behavior |
| --- | --- |
| `/develop/studios/new` | `404` / not found page |
| `/develop/studios/11111111-1111-1111-1111-111111111111` | `404` / not found page |
| `/develop/studios/11111111-1111-1111-1111-111111111111/settings` | `404` / not found page |
| `/account/developer-access` | `404` / not found page |
| `/games` | `404` / not found page |
| `/account/settings` | `404` / not found page |
| `/player/settings` | `404` / not found page |
| `/player/profile` | `404` / not found page |

## Navigation Structure

Primary navigation in the current shell:

- Public: `Browse`, `Install`
- Authenticated: `Play`, `Develop`, and conditionally `Moderate`
- User menu: `Profile`, `My Games`, `Wishlist`, `Reported Titles`, `Developer Console`, `Moderate`, `Account Settings`, `Sign Out`

Footer navigation mirrors the same access model and route grouping.
