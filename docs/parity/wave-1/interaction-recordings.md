# Wave 1 Interaction Recordings

Wave 1 records key interactions as scripted browser baselines instead of checked-in video binaries.

## Covered Flows

- Anonymous public route render for home, browse, public studio, and public title.
- Admin-authenticated route render for player, developer, and moderation shells.
- Keycloak-backed sign-in handoff through `/auth/signin`.
- Screenshot baseline capture for the maintained primary routes.

## Why Automated Recordings

- The current app is still changing, so reproducible scripted traces are more maintainable than manual screen captures.
- Browser traces can be regenerated locally from the root CLI without depending on external screen-recording tools.
- The same scripts will be reused in later waves to compare the React SPA against the current Blazor implementation.

## Commands

Generate or refresh the baseline screenshots:

```bash
python ./scripts/dev.py capture-parity-baseline --start-stack
```

Run the smoke and screenshot comparison suite:

```bash
python ./scripts/dev.py parity-test --start-stack
```

## Notes

- The suite uses the seeded local Keycloak realm and deterministic sample data.
- Authenticated parity coverage uses the seeded admin account so player, developer, and moderator surfaces can be exercised from one browser session.
- Playwright trace and HTML report artifacts are generated locally and intentionally not committed.
