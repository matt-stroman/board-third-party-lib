# Wave 1 UX Parity Checklist

This checklist is the authoritative parity gate for later migration waves.

## Navigation

- Header keeps the `Board Enthusiasts` brand lockup and the same top-level route grouping.
- `Browse` remains visible to anonymous users.
- `Play`, `Develop`, and `Moderate` remain gated by auth and role state.
- Footer mirrors the same access-dependent route affordances.
- The user menu preserves the current grouping and action order.

## Route Visibility By Access Level

- Anonymous users can access public browse, studio, title, and sign-in fallback routes.
- Player accounts can access `/player`, `/account`, wishlist, reported titles, and account workflows.
- Developer-capable accounts can access `/develop` and studio/title management workflows.
- Moderator-capable accounts can access `/moderate`.
- Legacy standalone routes that were intentionally retired continue returning not found.

## Layout And Information Scent

- The app shell keeps the same single-header, single-content-column, footer-based structure.
- Page headings, eyebrow labels, and action affordances preserve current information hierarchy.
- Public browse, public studio, public title, and player/developer/moderation shells keep the same primary calls to action.
- Error, empty, loading, and success states remain in-place rather than forcing route changes.

## Filters And Fuzzy Find

- Browse route preserves live filtering by search, genre, content kind, and sort.
- Developer and moderation search workflows preserve fuzzy-find behavior and immediate feedback.
- Search-empty states keep current explanatory messaging.

## Mutation Feedback

- Developer and moderation workflows preserve inline validation and save feedback.
- Success messages remain tied to the active workflow rather than a detached global toast pattern.
- Unsupported or failed auth redirects still route through the dedicated sign-in error surface.

## Empty And Error States

- Wishlist empty state remains explicit and friendly.
- Moderation access denial remains explicit and non-crashing.
- Public not-found routes continue rendering the application shell plus the not-found page.
- Shell resilience remains intact even if current-user bootstrap or notifications fail.

## Performance And Interaction

- Public and authenticated route transitions should stay within the current perceived responsiveness envelope.
- No migration change should introduce extra full-page reloads for in-place workflows that are currently interactive.
